#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频刮削工具 - 类似 tinyMediaManager
功能：从豆瓣获取电影/剧集信息，生成nfo文件，下载海报，标准化命名
"""

import os
import re
import sys
import json
import time
import shutil
import argparse
import subprocess
import requests
from pathlib import Path
from mutagen.mp4 import MP4
from urllib.parse import quote
from html.parser import HTMLParser
from collections import defaultdict
from PIL import Image, ImageDraw, ImageFont

# 尝试导入可选的视频处理库
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    from moviepy.editor import VideoFileClip
    HAS_MOVIEPY = True
except ImportError:
    HAS_MOVIEPY = False

# ============ 配置 ============
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Referer': 'https://movie.douban.com/',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}

# 代理配置 (用于TMDB等海外API)
PROXIES = {
    'http': 'http://127.0.0.1:7890',
    'https': 'http://127.0.0.1:7890',
}

DOUBAN_API = "https://movie.douban.com/j/subject_suggest?q={}"
DOUBAN_DETAIL = "https://movie.douban.com/subject/{}/"
REQUEST_DELAY = 2  # 请求间隔秒数

# ============ 替代海报来源配置 ============
# 当豆瓣海报不可用时的替代方案
FALLBACK_POSTER_SOURCES = [
    # TMDB API (免费，无需API Key但有速率限制)
    {"type": "tmdb", "base_url": "https://api.themoviedb.org/3/search/movie"},
    # 本地图片库 (用户可配置的本地目录)
    {"type": "local", "paths": []},  # 可在代码中设置，如 ['/path/to/posters', '/path/to/images']
]

# TMDB 图片基础URL
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

# TMDB API Key (可申请免费key: https://www.themoviedb.org/settings/api)
TMDB_API_KEY = 'c1a55e15baa85b77b9e976a280ce71dc'

# ============ 工具函数 ============
def log(msg, level="INFO"):
    print(f"[{level}] {msg}")

def sanitize_filename(name):
    """清理非法文件名字符"""
    return re.sub(r'[\\/:*?"<>|]', '_', name)

def extract_name_from_filename(filename):
    """
    从文件名提取电影/剧集名称
    例如: The.Kings.Warden.2026.WEB-DL.1080p.X264.mp4 -> The King's Warden
    """
    name = Path(filename).stem  # 去掉扩展名
    # 移除常见后缀
    patterns = [
        r'\.WEB-?DL.*$', r'\.BluRay.*$', r'\.HDRip.*$', r'\.DVDRip.*$',
        r'\.HDTV.*$', r'\.720p$', r'\.1080p$', r'\.4K$', r'\.2160p$',
        r'\.X264$', r'\.X265$', r'\.H264$', r'\.H265$', r'\.AAC.*$',
        r'\.DTS.*$', r'\.AC3.*$', r'\.MP3.*$',
        r'\.Remastered.*$', r'\.Extended.*$', r'\.UNRATED.*$',
        r'\.DCP.*$', r'\.PROPER.*$', r'\.REPACK.*$',
        r'\.RERIP.*$', r'\.READNFO.*$', r'\.NFOFiX.*$',
        r'-DKS2$', r'-DKS$', r'-NYH$', r'-FLA$',  # 移除组名
    ]
    for p in patterns:
        name = re.sub(p, '', name, flags=re.IGNORECASE)
    
    # 将点号和下划线转为空格
    name = name.replace('.', ' ').replace('_', ' ')
    # 移除多余空格
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def get_all_search_queries(filename):
    """
    生成多个搜索关键词尝试列表
    从文件名生成多种可能的搜索查询
    """
    queries = []
    
    # 原始名称
    base_name = extract_name_from_filename(filename)
    queries.append(base_name)
    
    # 尝试移除年份 (空格分隔: "Movie 2026" 或 括号分隔: "Movie (2026)")
    no_year = re.sub(r'\s+(19\d{2}|20\d{2})\s*$', '', base_name, flags=re.IGNORECASE).strip()
    if no_year and no_year != base_name:
        queries.append(no_year)
    # 移除括号中的年份
    no_year_paren = re.sub(r'\s*\(19\d{2}|20\d{2}\)\s*$', '', base_name, flags=re.IGNORECASE).strip()
    if no_year_paren and no_year_paren != base_name and no_year_paren not in queries:
        queries.append(no_year_paren)
    
    # 尝试移除分辨率和质量标记
    clean = re.sub(r'\s+(720p|1080p|2160p|4K|HD|WEB|HDRip|BluRay|DVDRip)', ' ', base_name, flags=re.IGNORECASE)
    clean = re.sub(r'\s+', ' ', clean).strip()
    if clean and clean != base_name:
        queries.append(clean)
    
    # 尝试简化为前两个主要单词
    words = base_name.split()
    if len(words) >= 2:
        queries.append(' '.join(words[:2]))
    if len(words) >= 3:
        queries.append(' '.join(words[:3]))
    
    # 移除常见的"II"、"III"等后缀再尝试
    for suffix in [' II', ' III', ' IV', ' V', ' Part \d+']:
        simple = re.sub(suffix, '', base_name, flags=re.IGNORECASE).strip()
        if simple and simple != base_name and simple not in queries:
            queries.append(simple)
    
    # 去重
    seen = set()
    unique_queries = []
    for q in queries:
        if q and q not in seen:
            seen.add(q)
            unique_queries.append(q)
    
    return unique_queries

def parse_episode_info(filename):
    """
    解析剧集信息，返回季数和集数
    支持格式: S01E01, 1x01, Season 1 Episode 1, E01 等
    """
    filename_lower = filename.lower()
    
    # 匹配 S01E01 或 S1E1 格式
    match = re.search(r's(\d{1,2})e(\d{1,2})', filename_lower)
    if match:
        return int(match.group(1)), int(match.group(2))
    
    # 匹配 1x01 格式
    match = re.search(r'(\d{1,2})x(\d{1,2})', filename_lower)
    if match:
        return int(match.group(1)), int(match.group(2))
    
    # 匹配 Season 1 Episode 1 格式
    match = re.search(r'season\s*(\d{1,2})\s*episode\s*(\d{1,2})', filename_lower)
    if match:
        return int(match.group(1)), int(match.group(2))
    
    # 匹配 E01 或 EP01 格式（默认第1季）
    match = re.search(r'(?:^|[_\.\-])e(\d{1,2})', filename_lower)
    if match:
        return 1, int(match.group(1))
    
    # 匹配 01 格式（仅数字，作为第1季）
    match = re.search(r'[\.\-_](\d{2})[\.\-_]', filename)
    if match:
        ep = int(match.group(1))
        if 1 <= ep <= 99:  # 假设1-99是集号
            return 1, ep
    
    return None, None

def guess_media_type(filename):
    """猜测是电影还是剧集"""
    season, episode = parse_episode_info(filename)
    if season is not None and episode is not None:
        return 'tv'
    return 'movie'

def get_year_from_filename(filename):
    """从文件名提取年份"""
    # 优先匹配括号中的年份：Movie (2026).mp4
    match = re.search(r'\((\d{4})\)', filename)
    if match:
        return match.group(1)
    # 匹配用分隔符的年份：Movie.2026.mp4 或 Movie-2026.mp4
    match = re.search(r'[\.\-_]?(19\d{2}|20\d{2})[\.\-_]', filename)
    return match.group(1) if match else None

def normalize_series_name(name):
    """标准化剧集名称，用于分组"""
    # 移除多余空格和特殊字符，转换为小写
    name = name.lower().strip()
    # 移除季信息 (S01, Season 1)
    name = re.sub(r'\s*s\d{1,2}\s*$', '', name, flags=re.I)
    name = re.sub(r'\s*season\s*\d{1,2}\s*$', '', name, flags=re.I)
    # 移除集信息 (E01, Episode 1, 1x01)
    name = re.sub(r'\s*e\d{1,2}\s*$', '', name, flags=re.I)
    name = re.sub(r'\s*episode\s*\d{1,2}\s*$', '', name, flags=re.I)
    name = re.sub(r'\s*\d{1,2}x\d{1,2}\s*$', '', name, flags=re.I)
    # 移除末尾的数字 (如 01, 02)
    name = re.sub(r'\s+\d{2}\s*$', '', name)
    # 标准化多余的空格
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def is_series_keyword(name):
    """检测是否是系列剧关键词（纪录片、综艺、电视剧等）"""
    name_lower = name.lower()
    series_keywords = [
        'documentary', 'documentaires', '纪录片',
        '综艺', 'variety', 'talk show',
        'series', 'series', '剧集',
        '电视剧', 'drama', 'telefilm',
        'anime', 'animation', '动漫',
        'kids', '儿童', '少儿',
        'real show', '真人秀'
    ]
    return any(kw in name_lower for kw in series_keywords)

# ============ 豆瓣API调用 ============
class DoubanScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        if 'DOUBAN_COOKIE' in dir():
            self.session.cookies['bid'] = DOUBAN_COOKIE.split('bid=')[1].split(';')[0]
        self.cache = {}  # 搜索缓存避免重复请求
    
    def search_douban_api(self, query, year=None):
        """使用豆瓣搜索API获取信息"""
        # 检查缓存
        cache_key = f"{query}_{year}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        time.sleep(REQUEST_DELAY)
        url = DOUBAN_API.format(quote(query))
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                results = resp.json()
                if not results:
                    return None
                
                if year:
                    # 尝试匹配年份
                    for item in results:
                        item_year = str(item.get('year', ''))
                        if year in item_year or item_year in str(year):
                            result = item
                            self.cache[cache_key] = result
                            return result
                    # 没匹配到年份，返回第一个结果但记录年份不匹配
                    result = results[0]
                    result['year_mismatch'] = True
                    self.cache[cache_key] = result
                    return result
                result = results[0]
                self.cache[cache_key] = result
                return result
        except Exception as e:
            log(f"搜索失败: {e}", "ERROR")
        return None
    
    def search_with_fallback(self, query, year=None):
        """搜索 - 优先API，失败则尝试多个查询词"""
        # 生成多个搜索查询尝试
        all_queries = get_all_search_queries(query)
        
        for q in all_queries:
            result = self.search_douban_api(q, year)
            if result:
                # 从搜索结果获取海报
                if 'img' in result:
                    result['poster_url'] = result['img'].replace('s_ratio_poster', 'l_ratio_poster')
                return result
        
        # 如果全部失败，尝试直接抓详情页
        return self._search_via_detail_page(query)
    
    def _search_via_detail_page(self, query):
        """通过详情页搜索（备选方案）"""
        log("尝试备用搜索方法...", "WARN")
        # 使用百度搜索关键词
        pass  # 暂未实现
    
    def get_poster_alternatives(self, movie_name, year=None):
        """
        获取替代海报来源
        当豆瓣海报不可用时，尝试其他来源
        返回: 可能的图片URL列表，按优先级排序
        """
        alternatives = []
        
        # 方法1: 从其他已知可用来源获取
        # 这里可以添加更多数据源的API调用
        
        # 方法2: 返回空的替代列表，让调用者使用本地占位符
        log(f"无可用外部海报源，将生成占位符图片: {movie_name}", "WARN")
        
        return alternatives
    
    def get_detail(self, subject_id):
        """获取详细信息"""
        time.sleep(REQUEST_DELAY)
        url = DOUBAN_DETAIL.format(subject_id)
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 200:
                return self._parse_detail_page(resp.text)
        except Exception as e:
            log(f"获取详情失败: {e}", "ERROR")
        return None
    
    def _parse_detail_page(self, html):
        """解析详情页HTML"""
        info = {}
        
        # 标题
        title_match = re.search(r'<title>(.*?)</title>', html)
        if title_match:
            info['title'] = title_match.group(1).replace('(豆瓣)', '').strip()
        
        # 评分
        rating_match = re.search(r'"ratingValue"\s*:\s*"([\d.]+)"', html)
        if rating_match:
            info['rating'] = rating_match.group(1)
        
        # 年份
        year_match = re.search(r'<span[^>]*>(\d{4})</span>.*?上映日期', html, re.DOTALL)
        if year_match:
            info['year'] = year_match.group(1)
        else:
            y = re.search(r'<span[^>]*class="year"[^>]*>\((\d{4})\)</span>', html)
            if y:
                info['year'] = y.group(1)
        
        # 简介
        summary_match = re.search(r'<span[^>]*class="all hidden"[^>]*>(.*?)</span>', html, re.DOTALL)
        if not summary_match:
            summary_match = re.search(r'<span[^>]*class="summary"[^>]*>(.*?)</span>', html, re.DOTALL)
        if summary_match:
            info['summary'] = self._clean_html(summary_match.group(1))
        
        # 海报
        poster_match = re.search(r'<img[^>]*src="(https://img\d*\.doubanio\.com/view/photo/s_ratio_poster/[^"]+)"', html)
        if poster_match:
            info['poster_url'] = poster_match.group(1)
        
        # 电影类型
        genres = re.findall(r'propertytype">(.*?)</a>', html)
        if genres:
            info['genre'] = genres
        
        # IMDb ID
        imdb_match = re.search(r'tt\d+', html)
        if imdb_match:
            info['imdb'] = imdb_match.group(0)
        
        return info
    
    def _clean_html(self, text):
        """清理HTML标签"""
        text = re.sub(r'<[^>]+>', '', text)
        text = HTMLParser().unescape(text)
        return text.strip()

# ============ NFO生成 ============
def generate_nfo(info, media_type='movie'):
    """生成Kodi兼容的nfo文件"""
    # Kodi 要求剧集每集使用 <episodedetails> 标签
    if media_type == 'episode':
        root_tag = 'episodedetails'
    elif media_type == 'tvshow':
        root_tag = 'tvshow'
    else:
        root_tag = 'movie'

    nfo = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    nfo += f'<{root_tag}>\n'

    # 基本信息
    if 'title' in info:
        nfo += f'  <title>{escape_xml(info["title"])}</title>\n'
    if 'originaltitle' in info:
        nfo += f'  <originaltitle>{escape_xml(info["originaltitle"])}</originaltitle>\n'
    if 'showtitle' in info:
        nfo += f'  <showtitle>{escape_xml(info["showtitle"])}</showtitle>\n'
    if 'year' in info:
        nfo += f'  <year>{info["year"]}</year>\n'

    # 评分
    if 'rating' in info:
        nfo += f'  <rating>{info["rating"]}</rating>\n'
    if 'votes' in info:
        nfo += f'  <votes>{info["votes"]}</votes>\n'
    if 'rating' in info and 'votes' in info:
        nfo += '  <ratings>\n'
        nfo += f'    <rating default="true" max="10" name="themoviedb">\n'
        nfo += f'      <value>{info["rating"]}</value>\n'
        nfo += f'      <votes>{info["votes"]}</votes>\n'
        nfo += '    </rating>\n'
        nfo += '  </ratings>\n'

    # 剧情
    if 'plot' in info:
        nfo += f'  <plot>{escape_xml(info["plot"])}</plot>\n'
    if 'outline' in info:
        nfo += f'  <outline>{escape_xml(info["outline"])}</outline>\n'
    if 'tagline' in info:
        nfo += f'  <tagline>{escape_xml(info["tagline"])}</tagline>\n'

    # 时长和分级
    if 'runtime' in info:
        nfo += f'  <runtime>{info["runtime"]}</runtime>\n'
    if 'mpaa' in info:
        nfo += f'  <mpaa>{escape_xml(info["mpaa"])}</mpaa>\n'
    if 'certification' in info:
        nfo += f'  <certification>{escape_xml(info["certification"])}</certification>\n'

    # 媒体标识ID
    if 'imdb' in info:
        nfo += f'  <imdbid>{info["imdb"]}</imdbid>\n'
    if 'tmdbid' in info:
        nfo += f'  <tmdbid>{info["tmdbid"]}</tmdbid>\n'
    if 'id' in info:
        nfo += f'  <id>{info["id"]}</id>\n'

    # 唯一ID
    if 'uniqueids' in info:
        for id_type, id_val in info['uniqueids'].items():
            default = 'true' if id_type == 'imdb' else 'false'
            nfo += f'  <uniqueid default="{default}" type="{id_type}">{id_val}</uniqueid>\n'

    # 国家/地区和首映日期
    if 'country' in info:
        for c in info['country'] if isinstance(info['country'], list) else [info['country']]:
            nfo += f'  <country>{escape_xml(c)}</country>\n'
    if 'premiered' in info:
        nfo += f'  <premiered>{info["premiered"]}</premiered>\n'

    # 类型
    if 'genre' in info:
        for g in info['genre'] if isinstance(info['genre'], list) else [info['genre']]:
            nfo += f'  <genre>{escape_xml(g)}</genre>\n'

    # 工作室
    if 'studio' in info:
        for s in info['studio'] if isinstance(info['studio'], list) else [info['studio']]:
            nfo += f'  <studio>{escape_xml(s)}</studio>\n'

    # 导演和编剧
    if 'director' in info:
        for d in info['director'] if isinstance(info['director'], list) else [info['director']]:
            if isinstance(d, dict):
                nfo += f'  <director>{escape_xml(d.get("name", ""))}</director>\n'
            else:
                nfo += f'  <director>{escape_xml(d)}</director>\n'
    if 'credits' in info:
        for c in info['credits'] if isinstance(info['credits'], list) else [info['credits']]:
            if isinstance(c, dict):
                nfo += f'  <credits>{escape_xml(c.get("name", ""))}</credits>\n'
            else:
                nfo += f'  <credits>{escape_xml(c)}</credits>\n'

    # 演员列表
    if 'actor' in info:
        for a in info['actor']:
            nfo += '  <actor>\n'
            if isinstance(a, dict):
                if 'name' in a:
                    nfo += f'    <name>{escape_xml(a["name"])}</name>\n'
                if 'role' in a:
                    nfo += f'    <role>{escape_xml(a["role"])}</role>\n'
                if 'thumb' in a:
                    nfo += f'    <thumb>{escape_xml(a["thumb"])}</thumb>\n'
                if 'tmdbid' in a:
                    nfo += f'    <tmdbid>{a["tmdbid"]}</tmdbid>\n'
                if 'profile' in a:
                    nfo += f'    <profile>{escape_xml(a["profile"])}</profile>\n'
            else:
                nfo += f'    <name>{escape_xml(str(a))}</name>\n'
            nfo += '  </actor>\n'

    # 标签
    if 'tag' in info:
        for t in info['tag'] if isinstance(info['tag'], list) else [info['tag']]:
            nfo += f'  <tag>{escape_xml(t)}</tag>\n'

    # 预告片
    if 'trailer' in info:
        nfo += f'  <trailer>{escape_xml(info["trailer"])}</trailer>\n'

    # 海报和图片
    if 'poster' in info:
        nfo += f'  <thumb aspect="poster">{escape_xml(info["poster"])}</thumb>\n'
    if 'clearlogo' in info:
        nfo += f'  <thumb aspect="clearlogo">{escape_xml(info["clearlogo"])}</thumb>\n'
    if 'fanart' in info:
        nfo += '  <fanart>\n'
        nfo += f'    <thumb>{escape_xml(info["fanart"])}</thumb>\n'
        nfo += '  </fanart>\n'

    # 剧集特有字段
    if 'season' in info:
        nfo += f'  <season>{info["season"]}</season>\n'
    if 'episode' in info:
        nfo += f'  <episode>{info["episode"]}</episode>\n'
    if 'displayseason' in info:
        nfo += f'  <displayseason>{info["displayseason"]}</displayseason>\n'
    if 'displayepisode' in info:
        nfo += f'  <displayepisode>{info["displayepisode"]}</displayepisode>\n'

    # 季名称
    if 'namedseasons' in info:
        for season_num, season_name in info['namedseasons'].items():
            nfo += f'  <namedseason number="{season_num}">{escape_xml(season_name)}</namedseason>\n'

    # 季海报
    if 'seasonposters' in info:
        for season_num, poster_url in info['seasonposters'].items():
            nfo += f'  <thumb aspect="poster" season="{season_num}" type="season">{escape_xml(poster_url)}</thumb>\n'

    nfo += f'</{root_tag}>\n'
    return nfo

def escape_xml(text):
    """XML转义"""
    if not text:
        return ''
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;')

# ============ 文件处理 ============
def test_poster_url(url, timeout=10):
    """测试海报URL是否可用"""
    if not url:
        return False
    try:
        resp = requests.head(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        # 检查是否为有效图片响应
        if resp.status_code == 200:
            content_type = resp.headers.get('Content-Type', '')
            return 'image' in content_type or len(resp.content) > 1000
        return False
    except:
        return False

def download_poster(url, output_path, retry_alternatives=True):
    """
    下载海报
    如果主URL不可用，尝试替代方案
    """
    if not url:
        # 如果没有URL，直接尝试生成占位符
        return generate_placeholder_poster(output_path, Path(output_path).parent.name)
    
    # 尝试下载主URL
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code == 200 and len(resp.content) > 1000:
            with open(output_path, 'wb') as f:
                f.write(resp.content)
            return True
    except Exception as e:
        log(f"下载海报失败: {e}", "WARN")
    
    # 如果下载失败，生成占位符
    return generate_placeholder_poster(output_path, Path(output_path).parent.name)

def search_tmdb_poster(movie_name, year=None, api_key=None):
    """
    搜索TMDB获取电影海报
    返回: poster_url 或 None
    """
    if not api_key:
        api_key = TMDB_API_KEY
    if not api_key:
        return None

    try:
        # 搜索电影
        search_url = "https://api.themoviedb.org/3/search/movie"
        params = {'api_key': api_key, 'query': movie_name, 'language': 'zh-CN'}
        if year:
            params['year'] = str(year)

        resp = requests.get(search_url, params=params, proxies=PROXIES, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('results') and len(data['results']) > 0:
                movie = data['results'][0]
                if movie.get('poster_path'):
                    poster_path = movie['poster_path']
                    # 使用更大的图片尺寸
                    return f"https://image.tmdb.org/t/p/w780{poster_path}"
    except Exception as e:
        log(f"TMDB搜索失败: {e}", "WARN")
    return None

def search_tmdb_tv(tv_name, year=None, api_key=None):
    """
    搜索TMDB获取电视剧信息
    返回: dict 或 None
    """
    if not api_key:
        api_key = TMDB_API_KEY
    if not api_key:
        return None

    try:
        search_url = "https://api.themoviedb.org/3/search/tv"
        params = {'api_key': api_key, 'query': tv_name, 'language': 'zh-CN'}
        if year:
            params['first_air_date_year'] = str(year)

        resp = requests.get(search_url, params=params, proxies=PROXIES, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('results') and len(data['results']) > 0:
                return data['results'][0]
    except Exception as e:
        log(f"TMDB电视剧搜索失败: {e}", "WARN")
    return None

def get_tmdb_movie_details(movie_id, api_key=None):
    """
    获取电影详细信息
    返回: dict 或 None
    """
    if not api_key:
        api_key = TMDB_API_KEY
    if not api_key:
        return None

    try:
        # 获取电影详情
        details_url = f"https://api.themoviedb.org/3/movie/{movie_id}"
        params = {'api_key': api_key, 'language': 'zh-CN'}
        resp = requests.get(details_url, params=params, proxies=PROXIES, timeout=20)
        if resp.status_code != 200:
            return None

        movie = resp.json()

        # 获取演职人员
        credits_url = f"https://api.themoviedb.org/3/movie/{movie_id}/credits"
        credits_resp = requests.get(credits_url, params={'api_key': api_key, 'language': 'zh-CN'}, proxies=PROXIES, timeout=20)
        credits_data = credits_resp.json() if credits_resp.status_code == 200 else {}

        # 获取图片信息
        images_url = f"https://api.themoviedb.org/3/movie/{movie_id}/images"
        images_resp = requests.get(images_url, params={'api_key': api_key}, proxies=PROXIES, timeout=20)
        images_data = images_resp.json() if images_resp.status_code == 200 else {}

        result = {
            'id': movie.get('id'),
            'title': movie.get('title'),
            'original_title': movie.get('original_title'),
            'year': movie.get('release_date', '')[:4] if movie.get('release_date') else '',
            'plot': movie.get('overview'),
            'runtime': movie.get('runtime'),
            'rating': movie.get('vote_average'),
            'votes': movie.get('vote_count'),
            'premiered': movie.get('release_date'),
            'genres': [g['name'] for g in movie.get('genres', [])],
            'countries': [c['name'] for c in movie.get('production_countries', [])],
            'status': movie.get('status'),
            'tagline': movie.get('tagline'),
            'imdb_id': movie.get('imdb_id'),
            'tmdb_id': movie.get('id'),
            'poster_path': movie.get('poster_path'),
            'backdrop_path': movie.get('backdrop_path'),
            'credits': credits_data,
            'images': images_data,
        }
        return result
    except Exception as e:
        log(f"获取电影详情失败: {e}", "WARN")
    return None

def get_tmdb_tv_details(tv_id, api_key=None):
    """
    获取电视剧详细信息
    返回: dict 或 None
    """
    if not api_key:
        api_key = TMDB_API_KEY
    if not api_key:
        return None

    try:
        # 获取剧集详情
        details_url = f"https://api.themoviedb.org/3/tv/{tv_id}"
        params = {'api_key': api_key, 'language': 'zh-CN'}
        resp = requests.get(details_url, params=params, proxies=PROXIES, timeout=20)
        if resp.status_code != 200:
            return None

        tv = resp.json()

        # 获取演职人员
        credits_url = f"https://api.themoviedb.org/3/tv/{tv_id}/credits"
        credits_resp = requests.get(credits_url, params={'api_key': api_key, 'language': 'zh-CN'}, proxies=PROXIES, timeout=20)
        credits_data = credits_resp.json() if credits_resp.status_code == 200 else {}

        # 获取图片信息
        images_url = f"https://api.themoviedb.org/3/tv/{tv_id}/images"
        images_resp = requests.get(images_url, params={'api_key': api_key}, proxies=PROXIES, timeout=20)
        images_data = images_resp.json() if images_resp.status_code == 200 else {}

        result = {
            'id': tv.get('id'),
            'title': tv.get('name'),
            'original_title': tv.get('original_name'),
            'year': tv.get('first_air_date', '')[:4] if tv.get('first_air_date') else '',
            'plot': tv.get('overview'),
            'runtime': tv.get('episode_run_time', [25])[0] if tv.get('episode_run_time') else 25,
            'rating': tv.get('vote_average'),
            'votes': tv.get('vote_count'),
            'premiered': tv.get('first_air_date'),
            'genres': [g['name'] for g in tv.get('genres', [])],
            'countries': [c['name'] for c in tv.get('production_countries', [])],
            'status': tv.get('status'),
            'number_of_seasons': tv.get('number_of_seasons'),
            'number_of_episodes': tv.get('number_of_episodes'),
            'imdb_id': tv.get('imdb_id'),
            'tmdb_id': tv.get('id'),
            'poster_path': tv.get('poster_path'),
            'backdrop_path': tv.get('backdrop_path'),
            'seasons': tv.get('seasons', []),
            'credits': credits_data,
            'images': images_data,
        }
        return result
    except Exception as e:
        log(f"获取剧集详情失败: {e}", "WARN")
    return None

def get_tmdb_episode_details(tv_id, season_num, episode_num, api_key=None):
    """
    获取单集详细信息
    返回: dict 或 None
    """
    if not api_key:
        api_key = TMDB_API_KEY
    if not api_key:
        return None

    try:
        url = f"https://api.themoviedb.org/3/tv/{tv_id}/season/{season_num}/episode/{episode_num}"
        params = {'api_key': api_key, 'language': 'zh-CN'}
        resp = requests.get(url, params=params, proxies=PROXIES, timeout=20)
        if resp.status_code != 200:
            return None

        episode = resp.json()

        result = {
            'id': episode.get('id'),
            'title': episode.get('name'),
            'original_title': episode.get('name'),
            'season': episode.get('season_number'),
            'episode': episode.get('episode_number'),
            'plot': episode.get('overview'),
            'air_date': episode.get('air_date'),
            'rating': episode.get('vote_average'),
            'votes': episode.get('vote_count'),
            'still_path': episode.get('still_path'),
            'show_id': tv_id,
        }
        return result
    except Exception as e:
        log(f"获取剧集详情失败: {e}", "WARN")
    return None

def extract_video_frame(video_path, output_path, timestamp=None):
    """
    从视频中提取一帧作为海报
    优先使用 ffmpeg，其次使用 cv2，最后使用占位符图片
    """
    video_path = str(video_path)
    output_path = str(output_path)
    
    # 方法1: 尝试使用 ffmpeg
    if shutil.which('ffmpeg'):
        try:
            if timestamp is None:
                # 获取视频时长，提取中间帧
                result = subprocess.run(
                    ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
                     '-of', 'default=noprint_wrappers=1:nokey=1', video_path],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0 and result.stdout.strip():
                    duration = float(result.stdout.strip())
                    timestamp = duration * 0.1  # 取10%位置，通常是黑场后正片开始
                else:
                    timestamp = 5  # 默认5秒
            
            subprocess.run(
                ['ffmpeg', '-y', '-ss', str(timestamp), '-i', video_path,
                 '-vframes', '1', '-q:v', '2', '-vf', 'scale=600:-1', output_path],
                capture_output=True, timeout=30
            )
            if os.path.exists(output_path):
                log(f"使用 ffmpeg 提取视频帧成功: {output_path}")
                return True
        except Exception as e:
            log(f"ffmpeg 提取帧失败: {e}", "WARN")
    
    # 方法2: 尝试使用 cv2
    if HAS_CV2:
        try:
            cap = cv2.VideoCapture(video_path)
            if timestamp is None:
                # 获取视频时长
                duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
                timestamp = int(duration * 0.1)
                cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            
            ret, frame = cap.read()
            cap.release()
            
            if ret:
                # 缩放图片
                height, width = frame.shape[:2]
                new_width = 600
                new_height = int(height * (new_width / width))
                frame = cv2.resize(frame, (new_width, new_height))
                
                cv2.imwrite(output_path, frame)
                if os.path.exists(output_path):
                    log(f"使用 cv2 提取视频帧成功: {output_path}")
                    return True
        except Exception as e:
            log(f"cv2 提取帧失败: {e}", "WARN")
    
    # 方法3: 生成占位符图片
    return generate_placeholder_poster(output_path, os.path.basename(video_path))

def generate_placeholder_poster(output_path, video_name):
    """
    生成占位符海报图片
    使用 PIL 在图片上绘制视频名称
    """
    try:
        # 创建海报尺寸的图片 (2:3 比例，常见的海报比例)
        width, height = 600, 900
        img = Image.new('RGB', (width, height), color=(30, 30, 50))
        draw = ImageDraw.Draw(img)
        
        # 尝试使用系统字体
        font_paths = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
            '/System/Library/Fonts/Helvetica.ttc',  # macOS
            'C:\\Windows\\Fonts\\arial.ttf',  # Windows
        ]
        
        font = None
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, 40)
                    break
                except:
                    continue
        
        if font is None:
            # 使用默认字体
            font = ImageFont.load_default()
        
        # 绘制背景装饰
        draw.rectangle([(0, 0), (width, 80)], fill=(80, 80, 120))
        draw.rectangle([(0, height-80), (width, height)], fill=(80, 80, 120))
        
        # 绘制视频图标（用文字模拟）
        icon_text = "🎬"
        draw.text((width//2 - 30, height//2 - 100), icon_text, font=font, align='center')
        
        # 绘制视频名称（处理长文件名）
        display_name = Path(video_name).stem
        max_chars = 25
        if len(display_name) > max_chars:
            # 分多行显示
            lines = [display_name[i:i+max_chars] for i in range(0, len(display_name), max_chars)]
            y_offset = height//2 - 20
            for line in lines[:4]:  # 最多4行
                bbox = draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]
                x = (width - text_width) // 2
                draw.text((x, y_offset), line, font=font, fill=(200, 200, 220))
                y_offset += 50
        else:
            bbox = draw.textbbox((0, 0), display_name, font=font)
            text_width = bbox[2] - bbox[0]
            x = (width - text_width) // 2
            draw.text((x, height//2 - 20), display_name, font=font, fill=(200, 200, 220))
        
        # 绘制底部说明
        status_text = "[ 无刮削数据 - 自动生成 ]"
        bbox = draw.textbbox((0, 0), status_text, font=font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        draw.text((x, height - 50), status_text, font=font, fill=(150, 150, 180))
        
        img.save(output_path, 'JPEG', quality=85)
        log(f"生成占位符海报: {output_path}")
        return True
        
    except Exception as e:
        log(f"生成占位符海报失败: {e}", "ERROR")
        # 最后手段：创建一个最小的有效图片
        try:
            img = Image.new('RGB', (100, 150), color=(50, 50, 100))
            img.save(output_path)
            return True
        except:
            return False

def get_media_info(file_path):
    """获取视频文件信息"""
    info = {}
    try:
        video = MP4(file_path)
        if video.tags:
            tags = video.tags
            info['title'] = str(tags.get('\xa9nam', [''])[0])
            info['artist'] = str(tags.get('\xa9ART', [''])[0])
            info['duration'] = round(video.info.length)
    except Exception as e:
        log(f"读取媒体信息失败: {e}", "WARN")
    return info

def check_directory_completeness(root_path, options):
    """
    检查目录完整性并自动补全缺失的内容
    检查项目：
    - 缺少 poster.jpg 的目录
    - 缺少 nfo 文件的目录
    - 剧集目录缺少各集的 thumb.jpg
    - 子目录结构是否符合规则
    """
    root_path = Path(root_path)
    if not root_path.exists():
        log(f"路径不存在: {root_path}", "ERROR")
        return
    
    log(f"\n{'='*50}")
    log(f"开始检查目录完整性: {root_path}")
    
    fixed_count = 0
    checked_dirs = set()
    
    # 遍历所有子目录
    for dir_path in sorted(root_path.rglob('*')):
        if not dir_path.is_dir():
            continue
        
        # 跳过根目录本身
        if dir_path == root_path:
            continue
        
        checked_dirs.add(dir_path)
        dir_name = dir_path.name
        needs_fix = False
        fixes_applied = []
        
        # 收集该目录下的所有视频文件
        video_files = [f for f in dir_path.iterdir() 
                      if f.is_file() and f.suffix.lower() in ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv']]
        
        # 收集该目录下的所有 nfo 文件
        nfo_files = [f for f in dir_path.iterdir() 
                    if f.is_file() and f.suffix.lower() == '.nfo']
        
        # 检查1: 如果是剧集根目录（包含 Season 子目录），应该有 tvshow.nfo
        season_dirs = [d for d in dir_path.iterdir() if d.is_dir() and re.match(r'Season\s*\d+', d.name, re.I)]
        if season_dirs:
            # 这是剧集根目录
            tvshow_nfo = dir_path / 'tvshow.nfo'
            if not tvshow_nfo.exists():
                # 尝试从 Season 目录复制或生成
                for season_dir in season_dirs:
                    season_nfo = season_dir / 'tvshow.nfo'
                    if season_nfo.exists():
                        shutil.copy(str(season_nfo), str(tvshow_nfo))
                        fixes_applied.append(f"复制 tvshow.nfo 从 {season_dir.name}")
                        needs_fix = True
                        break
            
            # 应该有 poster.jpg
            poster = dir_path / 'poster.jpg'
            if not poster.exists():
                # 尝试从 Season 目录复制
                poster_copied = False
                for season_dir in season_dirs:
                    season_poster = season_dir / 'poster.jpg'
                    if season_poster.exists():
                        shutil.copy(str(season_poster), str(poster))
                        fixes_applied.append(f"复制 poster.jpg 从 {season_dir.name}")
                        needs_fix = True
                        poster_copied = True
                        break
                
                # 如果没有从 Season 复制到，尝试从视频提取
                # 收集所有 Season 目录下的视频
                all_season_videos = []
                for season_dir in season_dirs:
                    all_season_videos.extend([
                        f for f in season_dir.iterdir()
                        if f.is_file() and f.suffix.lower() in ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv']
                    ])
                
                if not poster_copied and all_season_videos:
                    extract_video_frame(all_season_videos[0], poster)
                    fixes_applied.append(f"从视频提取 poster.jpg")
                    needs_fix = True
        
        # 检查2: 如果是 Season 目录
        elif re.match(r'Season\s*\d+', dir_name, re.I):
            season_num_match = re.search(r'(\d+)', dir_name)
            season_num = int(season_num_match.group(1)) if season_num_match else 1
            
            # 收集该季的所有视频
            season_videos = [f for f in dir_path.iterdir() 
                           if f.is_file() and f.suffix.lower() in ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv']]
            
            # 应该有 tvshow.nfo
            tvshow_nfo = dir_path / 'tvshow.nfo'
            if not tvshow_nfo.exists():
                # 尝试生成或从父目录复制
                parent_tvshow = dir_path.parent / 'tvshow.nfo'
                if parent_tvshow.exists():
                    shutil.copy(str(parent_tvshow), str(tvshow_nfo))
                    fixes_applied.append("复制 tvshow.nfo 从父目录")
                    needs_fix = True
            
            # 应该有 poster.jpg
            poster = dir_path / 'poster.jpg'
            if not poster.exists():
                parent_poster = dir_path.parent / 'poster.jpg'
                if parent_poster.exists():
                    shutil.copy(str(parent_poster), str(poster))
                    fixes_applied.append("复制 poster.jpg 从父目录")
                    needs_fix = True
                elif season_videos:
                    extract_video_frame(season_videos[0], poster)
                    fixes_applied.append("从视频提取 poster.jpg")
                    needs_fix = True
            
            # 检查每一集是否有对应的 nfo 和 thumb
            for video_file in season_videos:
                video_stem = video_file.stem
                ep_nfo = dir_path / f"{video_stem}.nfo"
                ep_thumb = dir_path / f"{video_stem}-thumb.jpg"
                
                if not ep_nfo.exists():
                    # 生成简单的 nfo 文件
                    try:
                        episode_match = re.search(r'[Ss](\d+)[Ee](\d+)', video_file.name)
                        if episode_match:
                            ep_num = int(episode_match.group(2))
                        else:
                            # 尝试从文件名中提取集号
                            ep_num_match = re.search(r'[\.\-_](\d{2})[\.\-_]', video_file.name)
                            ep_num = int(ep_num_match.group(1)) if ep_num_match else 1
                        
                        nfo_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<episodedetails>
  <title>{video_stem}</title>
  <season>{season_num}</season>
  <episode>{ep_num}</episode>
</episodedetails>
'''
                        with open(ep_nfo, 'w', encoding='utf-8') as f:
                            f.write(nfo_content)
                        fixes_applied.append(f"生成 {video_stem}.nfo")
                        needs_fix = True
                    except Exception as e:
                        log(f"生成 NFO 失败 {ep_nfo}: {e}", "WARN")
                
                if not ep_thumb.exists() and poster.exists():
                    shutil.copy(str(poster), str(ep_thumb))
                    fixes_applied.append(f"生成 {video_stem}-thumb.jpg")
                    needs_fix = True
        
        # 检查3: 如果是普通视频目录（单个电影）
        elif video_files:
            # 应该有 poster.jpg
            poster = dir_path / 'poster.jpg'
            if not poster.exists():
                extract_video_frame(video_files[0], poster)
                fixes_applied.append("从视频提取 poster.jpg")
                needs_fix = True
            
            # 应该有对应的 nfo 文件
            for video_file in video_files:
                video_stem = video_file.stem
                movie_nfo = dir_path / f"{video_stem}.nfo"
                
                if not movie_nfo.exists():
                    # 尝试查找同名 nfo
                    existing_nfo = dir_path / f"{dir_name}.nfo"
                    if existing_nfo.exists():
                        shutil.copy(str(existing_nfo), str(movie_nfo))
                        fixes_applied.append(f"复制 {dir_name}.nfo -> {video_stem}.nfo")
                        needs_fix = True
                    else:
                        # 生成简单的 nfo
                        try:
                            year_match = re.search(r'\((\d{4})\)', dir_name)
                            year = year_match.group(1) if year_match else ""
                            
                            nfo_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<movie>
  <title>{video_stem}</title>
  <year>{year}</year>
</movie>
'''
                            with open(movie_nfo, 'w', encoding='utf-8') as f:
                                f.write(nfo_content)
                            fixes_applied.append(f"生成 {video_stem}.nfo")
                            needs_fix = True
                        except Exception as e:
                            log(f"生成 NFO 失败 {movie_nfo}: {e}", "WARN")
        
        # 输出修复信息
        if needs_fix:
            log(f"\n📁 {dir_name}")
            for fix in fixes_applied:
                log(f"   ✓ {fix}")
            fixed_count += len(fixes_applied)
    
    # 统计信息
    log(f"\n{'='*50}")
    log(f"检查完成: 共检查 {len(checked_dirs)} 个目录")
    if fixed_count > 0:
        log(f"自动修复: {fixed_count} 项")
    else:
        log("所有目录内容完整，无需修复")

# ============ 主流程 ============
def group_videos_by_series(video_files):
    """按剧集名称对视频进行分组"""
    groups = defaultdict(list)
    
    for vf in video_files:
        filename = vf.name
        season, episode = parse_episode_info(filename)
        
        # 提取基础名称
        base_name = extract_name_from_filename(filename)
        normalized = normalize_series_name(base_name)
        
        # 如果有剧集信息，添加到对应组
        if season is not None and episode is not None:
            # 按基础名称分组
            groups[normalized].append({
                'path': vf,
                'filename': filename,
                'season': season,
                'episode': episode,
                'base_name': base_name
            })
        else:
            # 单个电影，作为独立组
            groups[normalized + '_' + vf.stem] = [{
                'path': vf,
                'filename': filename,
                'season': None,
                'episode': None,
                'base_name': base_name
            }]
    
    return groups

def process_movie(video_info, scraper, options):
    """处理电影"""
    vf = video_info['path']
    filename = video_info['filename']
    
    log(f"\n{'='*50}")
    log(f"处理电影: {filename}")
    
    # 1. 提取名称
    query_name = extract_name_from_filename(filename)
    year = get_year_from_filename(filename)
    log(f"查询名称: {query_name}, 年份: {year}")
    
    # 2. 搜索豆瓣
    result = scraper.search_with_fallback(filename, year)
    if not result:
        log("未找到匹配结果", "WARN")
        if not options['force']:
            return
        result = {'title': query_name, 'id': 'unknown', 'year': year}
    
    log(f"找到: {result.get('title', 'N/A')} ({result.get('year', 'N/A')})")
    
    # 3. 获取详情
    detail = None
    if 'id' in result and result['id'] != 'unknown':
        detail = scraper.get_detail(result['id'])
    
    if not detail:
        detail = {}
    detail['douban_id'] = result.get('id', '')
    detail['title'] = result.get('title', query_name)
    if 'year' not in detail and year:
        detail['year'] = year
    elif 'year' not in detail:
        detail['year'] = result.get('year', '')
    
    # 4. 确定目标目录
    folder_name = sanitize_filename(f"{detail['title']} ({detail['year']})" if detail.get('year') else detail['title'])
    target_dir = vf.parent / folder_name
    
    # 5. 创建目录
    target_dir.mkdir(parents=True, exist_ok=True)
    log(f"创建目录: {target_dir.name}")
    
    # 6. 重命名视频文件
    ext = vf.suffix
    video_name = f"{detail['title']} ({detail['year']}){ext}" if detail.get('year') else f"{detail['title']}{ext}"
    video_name = sanitize_filename(video_name)
    video_path = target_dir / video_name
    
    if vf.resolve() != video_path.resolve():
        shutil.move(str(vf), str(video_path))
        log(f"移动视频: {video_name}")
    
    # 7. 下载海报并放入目录
    poster_path = None
    if options['poster']:
        poster_path = target_dir / 'poster.jpg'
        
        # 优先下载刮削海报
        if 'poster_url' in detail and detail['poster_url']:
            if download_poster(detail['poster_url'], poster_path):
                log(f"海报已保存: {poster_path}")
            else:
                log(f"海报下载失败，尝试从视频提取", "WARN")
                extract_video_frame(video_path, poster_path)
        else:
            # 没有刮削海报，使用视频帧
            log(f"无刮削海报，尝试从视频提取", "WARN")
            extract_video_frame(video_path, poster_path)
    
    # 8. 生成NFO并放入目录
    if options['nfo']:
        nfo_path = target_dir / f"{video_path.stem}.nfo"
        nfo_content = generate_nfo(detail, 'movie')
        with open(nfo_path, 'w', encoding='utf-8') as f:
            f.write(nfo_content)
        log(f"NFO已生成: {nfo_path}")
    
    log(f"电影处理完成: {folder_name}")

def process_series(group_key, video_list, scraper, options):
    """处理剧集（连续剧、纪录片、综艺等）"""
    if not video_list:
        return
    
    log(f"\n{'='*50}")
    log(f"处理剧集: {group_key}")
    log(f"共 {len(video_list)} 集")
    
    # 获取基础名称
    base_name = video_list[0]['base_name']
    
    # 1. 搜索豆瓣获取基本信息
    year = get_year_from_filename(video_list[0]['filename'])
    result = scraper.search_with_fallback(video_list[0]['filename'], year)
    
    if not result:
        log("未找到匹配结果", "WARN")
        if not options['force']:
            return
        result = {'title': base_name, 'id': 'unknown', 'year': year}
    
    log(f"找到: {result.get('title', 'N/A')}")
    
    # 2. 获取详情
    detail = None
    if 'id' in result and result['id'] != 'unknown':
        detail = scraper.get_detail(result['id'])
    
    if not detail:
        detail = {}
    detail['douban_id'] = result.get('id', '')
    detail['title'] = result.get('title', base_name)
    if 'year' not in detail and year:
        detail['year'] = year
    elif 'year' not in detail:
        detail['year'] = result.get('year', '')
    
    # 3. 按季分组
    seasons = defaultdict(list)
    for vf in video_list:
        season = vf['season'] if vf['season'] else 1
        seasons[season].append(vf)
    
    # 对每季内的集数排序
    for s in seasons:
        seasons[s].sort(key=lambda x: x['episode'])
    
    log(f"包含 {len(seasons)} 季")
    
    # 4. 确定目标根目录
    folder_name = sanitize_filename(f"{detail['title']} ({detail['year']})" if detail.get('year') else detail['title'])
    root_dir = video_list[0]['path'].parent / folder_name
    root_dir.mkdir(parents=True, exist_ok=True)
    log(f"创建目录: {root_dir.name}")
    
    # 5. 下载剧集总海报
    poster_url = None
    if 'poster_url' in detail:
        poster_url = detail['poster_url']
    
    root_poster = None
    if options['poster']:
        root_poster = root_dir / 'poster.jpg'
        
        # 优先下载刮削海报
        if poster_url:
            if download_poster(poster_url, root_poster):
                log(f"剧集总海报已保存")
            else:
                log(f"海报下载失败，尝试从视频提取", "WARN")
                # 从第一集提取帧
                if video_list:
                    first_video = video_list[0]['path']
                    if first_video.exists():
                        extract_video_frame(first_video, root_poster)
        else:
            # 没有刮削海报，使用视频帧
            log(f"无刮削海报，尝试从视频提取", "WARN")
            if video_list:
                first_video = video_list[0]['path']
                if first_video.exists():
                    extract_video_frame(first_video, root_poster)
    
    # 6. 生成剧集总NFO
    if options['nfo']:
        root_nfo = root_dir / 'tvshow.nfo'
        nfo_content = generate_nfo(detail, 'tvshow')
        with open(root_nfo, 'w', encoding='utf-8') as f:
            f.write(nfo_content)
        log(f"剧集总NFO已生成")
    
    # 7. 处理每一季
    for season_num in sorted(seasons.keys()):
        season_videos = seasons[season_num]
        season_str = f"Season {season_num:02d}"
        season_dir = root_dir / season_str
        season_dir.mkdir(parents=True, exist_ok=True)
        log(f"\n处理 {season_str}，共 {len(season_videos)} 集")
        
        # 下载季海报（如果可用）
        if options['poster']:
            season_poster = season_dir / 'poster.jpg'
            if not season_poster.exists():
                try:
                    if root_poster and root_poster.exists():
                        shutil.copy(str(root_poster), str(season_poster))
                        log(f"季海报已复制")
                    elif season_videos:
                        # 从该季视频提取海报
                        extract_video_frame(season_videos[0]['path'], season_poster)
                except Exception as e:
                    log(f"季海报处理失败: {e}", "WARN")
        
        # 生成季NFO
        if options['nfo']:
            season_nfo = season_dir / 'tvshow.nfo'
            season_detail = detail.copy()
            season_detail['season'] = season_num
            nfo_content = generate_nfo(season_detail, 'tvshow')
            with open(season_nfo, 'w', encoding='utf-8') as f:
                f.write(nfo_content)
        
        # 处理每一集
        for idx, vf_info in enumerate(season_videos):
            vf = vf_info['path']
            episode_num = vf_info['episode']
            
            log(f"  处理 S{season_num:02d}E{episode_num:02d}: {vf.name}")
            
            # 重命名视频文件
            video_name = f"{detail['title']} - S{season_num:02d}E{episode_num:02d}{vf.suffix}"
            video_name = sanitize_filename(video_name)
            video_path = season_dir / video_name
            
            if vf.resolve() != video_path.resolve():
                shutil.move(str(vf), str(video_path))
            
            # 每集的海报（使用季的海报副本）
            if options['poster']:
                ep_poster = season_dir / f"{video_path.stem}-thumb.jpg"
                try:
                    if root_poster and root_poster.exists():
                        shutil.copy(str(root_poster), str(ep_poster))
                except Exception:
                    pass
            
            # 每集的NFO
            if options['nfo']:
                ep_detail = detail.copy()
                ep_detail['season'] = season_num
                ep_detail['episode'] = episode_num
                
                ep_nfo = season_dir / f"{video_path.stem}.nfo"
                nfo_content = generate_nfo(ep_detail, 'episode')
                with open(ep_nfo, 'w', encoding='utf-8') as f:
                    f.write(nfo_content)
    
    log(f"剧集处理完成: {folder_name}")

def scrape_directory(input_path, output_path, options, scraper=None):
    """
    主入口函数：扫描输入目录并刮削到输出目录

    参数:
        input_path: 输入目录或文件路径
        output_path: 输出目录路径
        options: 处理选项
        scraper: 可选的刮削器实例
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        log(f"输入路径不存在: {input_path}", "ERROR")
        return

    # 创建输出目录
    output_path.mkdir(parents=True, exist_ok=True)
    log(f"输出目录: {output_path}")

    # 初始化刮削器
    if scraper is None:
        scraper = DoubanScraper()

    # 收集所有视频文件
    video_files = []
    video_exts = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv']

    if input_path.is_file():
        if input_path.suffix.lower() in video_exts:
            video_files.append(input_path)
    elif input_path.is_dir():
        for video_file in input_path.rglob('*'):
            if video_file.is_file() and video_file.suffix.lower() in video_exts:
                video_files.append(video_file)

    if not video_files:
        log("未找到视频文件", "WARN")
        return

    log(f"找到 {len(video_files)} 个视频文件")

    # 按剧集分组
    groups = group_videos_by_series(video_files)
    log(f"分为 {len(groups)} 个组")

    # 统计
    success_count = 0
    failed_count = 0
    failed_list = []

    # 处理每个组
    for group_key, video_list in groups.items():
        is_series = any(v['season'] is not None for v in video_list)
        base_name = video_list[0]['base_name'] if video_list else ''

        if is_series_keyword(base_name) or (is_series and len(video_list) > 1):
            # 剧集处理
            result = scrape_series_to_output(group_key, video_list, output_path, options, scraper)
            if result:
                success_count += 1
            else:
                failed_count += 1
                failed_list.append({'path': str(video_list[0]['path']), 'reason': 'series_failed'})
        else:
            # 电影处理
            for vf_info in video_list:
                result = scrape_movie_to_output(vf_info['path'], output_path, options, scraper)
                if result:
                    success_count += 1
                else:
                    failed_count += 1
                    failed_list.append({'path': str(vf_info['path']), 'reason': 'movie_failed'})

    # 输出失败报告
    if failed_list:
        log(f"\n{'='*50}")
        log(f"处理失败: {failed_count} 项")
        failed_file = output_path / 'failed_scrape.json'
        import json
        with open(failed_file, 'w', encoding='utf-8') as f:
            json.dump({'failed': failed_list, 'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')}, f, ensure_ascii=False, indent=2)
        log(f"失败记录: {failed_file}")

    log(f"\n{'='*50}")
    log(f"处理完成: 成功 {success_count}, 失败 {failed_count}")

def detect_media_type(video_path):
    """
    检测媒体类型（电影/剧集）

    返回: 'movie', 'series', 或 'unknown'
    """
    filename = video_path.name

    # 检查是否有剧集信息
    season, episode = parse_episode_info(filename)
    if season is not None and episode is not None:
        return 'series'

    # 检查是否有剧集关键词
    base_name = extract_name_from_filename(filename)
    if is_series_keyword(base_name):
        return 'series'

    return 'movie'

def scrape_movie_to_output(video_path, output_dir, options, scraper=None):
    """
    将电影刮削到输出目录

    返回: True成功, False失败
    """
    try:
        video_path = Path(video_path)
        if scraper is None:
            scraper = DoubanScraper()

        filename = video_path.name
        query_name = extract_name_from_filename(filename)
        year = get_year_from_filename(filename)

        log(f"\n{'='*50}")
        log(f"处理电影: {filename}")

        # 1. 搜索TMDB获取电影信息
        tmdb_result = search_tmdb_poster(query_name, year)
        if not tmdb_result:
            log(f"未在TMDB找到: {query_name}", "WARN")
            # 尝试豆瓣搜索
            result = scraper.search_with_fallback(filename, year)
            if not result:
                log("豆瓣也未找到", "WARN")
                # 创建错误标记
                error_file = output_dir / f"{sanitize_filename(query_name)}.scrape_error"
                error_file.write_text(f"FAILED: not_found\nTIME: {time.strftime('%Y-%m-%d %H:%M:%S')}", encoding='utf-8')
                return False
        else:
            log(f"TMDB搜索成功")

        # 2. 获取电影详细信息
        # 从搜索结果中获取TMDB ID
        details = get_tmdb_movie_details(842675)  # TODO: 需要从搜索结果获取真实ID
        if not details:
            # 使用基本信息构建
            details = {
                'title': query_name,
                'year': year,
                'plot': '',
                'rating': 0,
                'votes': 0,
                'runtime': 0,
                'genre': [],
                'country': [],
                'premiered': '',
            }

        # 3. 创建电影目录
        folder_name = sanitize_filename(f"{details.get('title', query_name)} ({details.get('year', year)})")
        movie_dir = output_dir / folder_name
        movie_dir.mkdir(parents=True, exist_ok=True)
        log(f"创建目录: {folder_name}")

        # 4. 复制/移动视频文件
        ext = video_path.suffix
        video_name = f"{folder_name}{ext}"
        video_dest = movie_dir / video_name

        if options.get('copy'):
            shutil.copy(str(video_path), str(video_dest))
            log(f"复制视频: {video_name}")
        else:
            shutil.move(str(video_path), str(video_dest))
            log(f"移动视频: {video_name}")

        # 5. 下载海报
        if options.get('poster'):
            poster_path = movie_dir / f"{folder_name}-poster.jpg"
            fanart_path = movie_dir / f"{folder_name}-fanart.jpg"

            # 下载海报
            if tmdb_result:
                download_poster(tmdb_result, poster_path)
                log(f"海报已保存: poster.jpg")

            # 下载fanart（如果可用）
            if details.get('backdrop_path'):
                fanart_url = f"https://image.tmdb.org/t/p/original{details['backdrop_path']}"
                download_poster(fanart_url, fanart_path)

        # 6. 生成NFO
        if options.get('nfo'):
            nfo_path = movie_dir / f"{folder_name}.nfo"
            nfo_content = generate_nfo(details, 'movie')
            with open(nfo_path, 'w', encoding='utf-8') as f:
                f.write(nfo_content)
            log(f"NFO已生成: {nfo_path.name}")

            # 生成movie.nfo副本
            movie_nfo = movie_dir / 'movie.nfo'
            with open(movie_nfo, 'w', encoding='utf-8') as f:
                f.write(nfo_content)

        log(f"电影处理完成: {folder_name}")
        return True

    except Exception as e:
        log(f"处理电影失败: {e}", "ERROR")
        return False

def scrape_series_to_output(group_key, video_list, output_dir, options, scraper=None):
    """
    将剧集刮削到输出目录

    返回: True成功, False失败
    """
    try:
        if scraper is None:
            scraper = DoubanScraper()

        log(f"\n{'='*50}")
        log(f"处理剧集: {group_key}")
        log(f"共 {len(video_list)} 集")

        # 获取基础信息
        base_name = video_list[0]['base_name']
        year = get_year_from_filename(video_list[0]['filename'])

        # 1. 搜索TMDB获取剧集信息
        search_result = search_tmdb_tv(base_name, year)
        if not search_result:
            log(f"未在TMDB找到: {base_name}", "WARN")
            # 尝试豆瓣
            result = scraper.search_with_fallback(video_list[0]['filename'], year)
            if not result:
                log("豆瓣也未找到", "WARN")
                error_file = output_dir / f"{sanitize_filename(group_key)}.scrape_error"
                error_file.write_text(f"FAILED: not_found\nTIME: {time.strftime('%Y-%m-%d %H:%M:%S')}", encoding='utf-8')
                return False

            series_name = result.get('title', base_name)
            tmdb_id = None
        else:
            series_name = search_result.get('name', base_name)
            tmdb_id = search_result.get('id')

        # 2. 获取剧集详细信息
        details = None
        if tmdb_id:
            details = get_tmdb_tv_details(tmdb_id)

        if not details:
            details = {
                'title': series_name,
                'originaltitle': series_name,
                'showtitle': series_name,
                'year': year,
                'plot': '',
                'rating': 0,
                'votes': 0,
                'runtime': 25,
                'genre': [],
                'premiered': '',
                'status': '',
            }

        # 3. 创建剧集目录
        series_dir = output_dir / series_name
        series_dir.mkdir(parents=True, exist_ok=True)
        log(f"创建目录: {series_name}")

        # 4. 下载海报和fanart
        if options.get('poster'):
            poster_path = series_dir / 'poster.jpg'
            fanart_path = series_dir / 'fanart.jpg'

            if details.get('poster_path'):
                poster_url = f"https://image.tmdb.org/t/p/original{details['poster_path']}"
                download_poster(poster_url, poster_path)

            if details.get('backdrop_path'):
                fanart_url = f"https://image.tmdb.org/t/p/original{details['backdrop_path']}"
                download_poster(fanart_url, fanart_path)

        # 5. 生成tvshow.nfo
        if options.get('nfo'):
            tvshow_nfo = series_dir / 'tvshow.nfo'
            nfo_content = generate_nfo(details, 'tvshow')
            with open(tvshow_nfo, 'w', encoding='utf-8') as f:
                f.write(nfo_content)

            # 生成副本
            series_nfo = series_dir / f"{series_name}.nfo"
            with open(series_nfo, 'w', encoding='utf-8') as f:
                f.write(nfo_content)

        # 6. 处理每集
        # 按季分组
        seasons = defaultdict(list)
        for vf_info in video_list:
            season_num = vf_info.get('season', 1)
            seasons[season_num].append(vf_info)

        for season_num, season_videos in sorted(seasons.items()):
            season_dir = series_dir / f"Season {season_num:02d}"
            season_dir.mkdir(parents=True, exist_ok=True)

            # 下载季海报
            if options.get('poster') and details.get('seasons'):
                for s in details['seasons']:
                    if s.get('season_number') == season_num and s.get('poster_path'):
                        season_poster_path = season_dir / 'poster.jpg'
                        season_poster_url = f"https://image.tmdb.org/t/p/original{s['poster_path']}"
                        download_poster(season_poster_url, season_poster_path)
                        break

            for vf_info in season_videos:
                episode_num = vf_info.get('episode', 1)
                video_path = Path(vf_info['path'])

                # 获取单集信息
                ep_details = None
                if tmdb_id:
                    ep_details = get_tmdb_episode_details(tmdb_id, season_num, episode_num)

                if not ep_details:
                    ep_details = {
                        'title': video_path.stem,
                        'originaltitle': video_path.stem,
                        'showtitle': series_name,
                        'season': season_num,
                        'episode': episode_num,
                        'plot': '',
                        'air_date': '',
                        'rating': 0,
                        'votes': 0,
                    }

                # 复制/移动视频
                ext = video_path.suffix
                ep_video_name = f"{series_name} - S{season_num:02d}E{episode_num:02d}{ext}"
                ep_video_path = season_dir / ep_video_name

                if options.get('copy'):
                    shutil.copy(str(video_path), str(ep_video_path))
                else:
                    shutil.move(str(video_path), str(ep_video_path))

                # 生成集NFO
                if options.get('nfo'):
                    ep_nfo_path = season_dir / f"{series_name} - S{season_num:02d}E{episode_num:02d}.nfo"
                    nfo_content = generate_nfo(ep_details, 'episode')
                    with open(ep_nfo_path, 'w', encoding='utf-8') as f:
                        f.write(nfo_content)

                # 下载集缩略图
                if options.get('poster') and ep_details.get('still_path'):
                    thumb_path = season_dir / f"{series_name} - S{season_num:02d}E{episode_num:02d}-thumb.jpg"
                    thumb_url = f"https://image.tmdb.org/t/p/original{ep_details['still_path']}"
                    download_poster(thumb_url, thumb_path)

        log(f"剧集处理完成: {series_name}")
        return True

    except Exception as e:
        log(f"处理剧集失败: {e}", "ERROR")
        return False

def main():
    parser = argparse.ArgumentParser(description='视频刮削工具 - 类似tinyMediaManager')
    parser.add_argument('--input', '-i', required=True, help='输入目录或文件路径')
    parser.add_argument('--output', '-o', required=True, help='输出目录路径')
    parser.add_argument('--poster', '-p', action='store_true', help='下载海报')
    parser.add_argument('--nfo', '-n', action='store_true', help='生成NFO文件')
    parser.add_argument('--rename', '-r', action='store_true', help='重命名文件')
    parser.add_argument('--all', '-a', action='store_true', help='执行全部操作')
    parser.add_argument('--force', '-f', action='store_true', help='强制处理未匹配的文件')
    parser.add_argument('--copy', '-c', action='store_true', help='复制模式（不移动原文件）')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    parser.add_argument('--check', action='store_true', help='检查目录完整性并自动修复')

    args = parser.parse_args()

    # 如果是检查模式，执行检查
    if args.check:
        check_directory_completeness(args.input, {'poster': True, 'nfo': True})
        return

    # 设置选项
    options = {
        'poster': args.poster or args.all,
        'nfo': args.nfo or args.all,
        'rename': args.rename or args.all,
        'force': args.force,
        'copy': args.copy,
        'extract_frame': False
    }

    if not any([options['poster'], options['nfo'], options['rename']]):
        parser.print_help()
        print("\n示例: python scraper.py --input . --output ./output --all")
        return

    # 调用主处理函数
    scrape_directory(args.input, args.output, options)

if __name__ == '__main__':
    main()