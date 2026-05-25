#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据源可用性测试
测试豆瓣和TMDB的搜索、详情获取、海报获取能力
"""

import requests
import time
import sys
from pathlib import Path

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
import scraper

# 代理配置
PROXIES = {
    'http': 'http://127.0.0.1:7890',
    'https': 'http://127.0.0.1:7890',
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Referer': 'https://movie.douban.com/',
}

# 测试样本
MOVIES = [
    ("流浪地球", 2023),
    ("满江红", 2023),
    ("你好，李焕英", 2021),
    ("哪吒之魔童降世", 2019),
    ("复仇者联盟4", 2019),
]

TV_SHOWS = [
    ("狂飙", 2023),
    ("漫长的季节", 2023),
    ("三体", 2023),
    ("甄嬛传", 2011),
    ("琅琊榜", 2015),
]

TMDB_API_KEY = 'c1a55e15baa85b77b9e976a280ce71dc'

def test_douban_search(name, year):
    """测试豆瓣搜索API"""
    start = time.time()
    try:
        url = f"https://movie.douban.com/j/subject_suggest?q={name}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        elapsed = time.time() - start

        if resp.status_code == 200:
            data = resp.json()
            if data:
                item = data[0]
                douban_id = item.get('id', '')
                return {
                    'success': True,
                    'elapsed': elapsed,
                    'id': douban_id,
                    'title': item.get('title', ''),
                    'year': item.get('year', ''),
                    'poster': item.get('img', ''),
                }
        return {'success': False, 'elapsed': elapsed, 'error': f'HTTP {resp.status_code}'}
    except Exception as e:
        return {'success': False, 'elapsed': time.time() - start, 'error': str(e)[:50]}

def test_douban_detail(douban_id):
    """测试豆瓣详情页"""
    start = time.time()
    try:
        url = f"https://movie.douban.com/subject/{douban_id}/"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        elapsed = time.time() - start

        if resp.status_code == 200:
            html = resp.text
            info = scraper.DoubanScraper()._parse_detail_page(html)
            return {
                'success': True,
                'elapsed': elapsed,
                'fields': list(info.keys()),
                'title': info.get('title', ''),
                'rating': info.get('rating', ''),
                'year': info.get('year', ''),
                'poster': info.get('poster_url', ''),
            }
        return {'success': False, 'elapsed': elapsed, 'error': f'HTTP {resp.status_code}'}
    except Exception as e:
        return {'success': False, 'elapsed': time.time() - start, 'error': str(e)[:50]}

def test_douban_poster(poster_url):
    """测试豆瓣海报可用性"""
    if not poster_url:
        return {'success': False, 'error': '无海报URL'}

    start = time.time()
    try:
        resp = requests.get(poster_url, headers=HEADERS, timeout=10)
        elapsed = time.time() - start

        if resp.status_code == 200 and len(resp.content) > 1000:
            return {'success': True, 'elapsed': elapsed, 'size': len(resp.content)}
        return {'success': False, 'elapsed': elapsed, 'error': f'HTTP {resp.status_code}'}
    except Exception as e:
        return {'success': False, 'elapsed': elapsed, 'error': str(e)[:50]}

def test_tmdb_search(name, year):
    """测试TMDB搜索API"""
    start = time.time()
    try:
        url = "https://api.themoviedb.org/3/search/movie"
        params = {
            'api_key': TMDB_API_KEY,
            'query': name,
            'language': 'zh-CN',
        }
        if year:
            params['year'] = str(year)

        resp = requests.get(url, params=params, proxies=PROXIES, timeout=20)
        elapsed = time.time() - start

        if resp.status_code == 200:
            data = resp.json()
            if data.get('results') and len(data['results']) > 0:
                movie = data['results'][0]
                return {
                    'success': True,
                    'elapsed': elapsed,
                    'id': movie.get('id'),
                    'title': movie.get('title', ''),
                    'year': movie.get('release_date', '')[:4] if movie.get('release_date') else '',
                    'poster_path': movie.get('poster_path', ''),
                    'overview': movie.get('overview', '')[:100] if movie.get('overview') else '',
                }
        return {'success': False, 'elapsed': elapsed, 'error': '无结果'}
    except Exception as e:
        return {'success': False, 'elapsed': time.time() - start, 'error': str(e)[:50]}

def test_tmdb_poster(poster_path):
    """测试TMDB海报可用性"""
    if not poster_path:
        return {'success': False, 'error': '无海报路径'}

    start = time.time()
    try:
        url = f"https://image.tmdb.org/t/p/w500{poster_path}"
        resp = requests.get(url, timeout=10)
        elapsed = time.time() - start

        if resp.status_code == 200 and len(resp.content) > 1000:
            return {'success': True, 'elapsed': elapsed, 'size': len(resp.content)}
        return {'success': False, 'elapsed': elapsed, 'error': f'HTTP {resp.status_code}'}
    except Exception as e:
        return {'success': False, 'elapsed': elapsed, 'error': str(e)[:50]}

def print_result(name, result, prefix="  "):
    """打印测试结果"""
    if result['success']:
        print(f"{prefix}[OK] 成功 ({result['elapsed']:.2f}s)")
    else:
        print(f"{prefix}[FAIL] 失败: {result.get('error', '未知错误')}")

def run_douban_tests():
    """运行豆瓣测试"""
    print("\n" + "=" * 60)
    print("第一阶段：豆瓣数据源测试")
    print("=" * 60)

    all_results = []

    # 测试电影
    print("\n【电影搜索测试】")
    movie_results = []
    for name, year in MOVIES:
        print(f"\n  {name} ({year}):")
        result = test_douban_search(name, year)
        print_result(name, result)
        if result['success']:
            movie_results.append(result)
            print(f"    ID: {result.get('id', 'N/A')}")
            print(f"    标题: {result.get('title', 'N/A')}")
            print(f"    年份: {result.get('year', 'N/A')}")

            # 测试详情页
            douban_id = result.get('id', '')
            if douban_id:
                print(f"    测试详情页...")
                detail = test_douban_detail(douban_id)
                print_result(name, detail, "      ")
                if detail['success']:
                    print(f"      字段数: {len(detail.get('fields', []))}")
                    print(f"      评分: {detail.get('rating', 'N/A')}")

                    # 测试海报
                    poster_url = detail.get('poster', '')
                    if poster_url:
                        poster_url_l = poster_url.replace('s_ratio_poster', 'l_ratio_poster')
                        print(f"    测试海报...")
                        poster = test_douban_poster(poster_url_l)
                        print_result(name, poster, "      ")
                else:
                    # 尝试直接测试海报
                    poster_url = result.get('poster', '')
                    if poster_url:
                        poster_url_l = poster_url.replace('s_ratio_poster', 'l_ratio_poster')
                        print(f"    测试海报...")
                        poster = test_douban_poster(poster_url_l)
                        print_result(name, poster, "      ")

        time.sleep(1)  # 避免请求过快

        all_results.append({
            'name': name,
            'type': 'movie',
            'search': result,
        })

    # 测试电视剧
    print("\n\n【电视剧搜索测试】")
    tv_results = []
    for name, year in TV_SHOWS:
        print(f"\n  {name} ({year}):")
        result = test_douban_search(name, year)
        print_result(name, result)
        if result['success']:
            tv_results.append(result)
            print(f"    ID: {result.get('id', 'N/A')}")
            print(f"    标题: {result.get('title', 'N/A')}")
            print(f"    年份: {result.get('year', 'N/A')}")

            # 测试详情页
            douban_id = result.get('id', '')
            if douban_id:
                print(f"    测试详情页...")
                detail = test_douban_detail(douban_id)
                print_result(name, detail, "      ")
                if detail['success']:
                    print(f"      字段数: {len(detail.get('fields', []))}")
                    print(f"      评分: {detail.get('rating', 'N/A')}")

                    # 测试海报
                    poster_url = detail.get('poster', '')
                    if poster_url:
                        poster_url_l = poster_url.replace('s_ratio_poster', 'l_ratio_poster')
                        print(f"    测试海报...")
                        poster = test_douban_poster(poster_url_l)
                        print_result(name, poster, "      ")

        time.sleep(1)

        all_results.append({
            'name': name,
            'type': 'tv',
            'search': result,
        })

    # 统计
    print("\n\n" + "=" * 60)
    print("豆瓣测试统计")
    print("=" * 60)

    movie_search_ok = sum(1 for r in movie_results if r['success'])
    tv_search_ok = sum(1 for r in tv_results if r['success'])

    print(f"电影搜索成功率: {movie_search_ok}/{len(MOVIES)} ({100*movie_search_ok/len(MOVIES):.0f}%)")
    print(f"电视剧搜索成功率: {tv_search_ok}/{len(TV_SHOWS)} ({100*tv_search_ok/len(TV_SHOWS):.0f}%)")

    return all_results

def run_tmdb_tests():
    """运行TMDB测试"""
    print("\n\n" + "=" * 60)
    print("第二阶段：TMDB数据源测试")
    print("=" * 60)

    all_results = []

    # 测试电影
    print("\n【电影搜索测试】")
    movie_results = []
    for name, year in MOVIES:
        print(f"\n  {name} ({year}):")
        result = test_tmdb_search(name, year)
        print_result(name, result)
        if result['success']:
            movie_results.append(result)
            print(f"    TMDB ID: {result.get('id', 'N/A')}")
            print(f"    标题: {result.get('title', 'N/A')}")
            print(f"    年份: {result.get('year', 'N/A')}")
            print(f"    概述: {result.get('overview', 'N/A')[:80]}...")

            # 测试海报
            poster_path = result.get('poster_path', '')
            if poster_path:
                print(f"    测试海报...")
                poster = test_tmdb_poster(poster_path)
                print_result(name, poster, "      ")

        time.sleep(0.5)  # TMDB有速率限制

        all_results.append({
            'name': name,
            'type': 'movie',
            'search': result,
        })

    # 测试电视剧
    print("\n\n【电视剧搜索测试 - TMDB TV】")
    tv_results = []
    for name, year in TV_SHOWS:
        print(f"\n  {name} ({year}):")
        # TMDB电视剧搜索
        start = time.time()
        try:
            url = "https://api.themoviedb.org/3/search/tv"
            params = {
                'api_key': TMDB_API_KEY,
                'query': name,
                'language': 'zh-CN',
            }

            resp = requests.get(url, params=params, proxies=PROXIES, timeout=20)
            elapsed = time.time() - start

            if resp.status_code == 200:
                data = resp.json()
                if data.get('results') and len(data['results']) > 0:
                    show = data['results'][0]
                    result = {
                        'success': True,
                        'elapsed': elapsed,
                        'id': show.get('id'),
                        'title': show.get('name', ''),
                        'year': show.get('first_air_date', '')[:4] if show.get('first_air_date') else '',
                        'poster_path': show.get('poster_path', ''),
                        'overview': show.get('overview', '')[:100] if show.get('overview') else '',
                    }
                else:
                    result = {'success': False, 'elapsed': elapsed, 'error': '无结果'}
            else:
                result = {'success': False, 'elapsed': elapsed, 'error': f'HTTP {resp.status_code}'}
        except Exception as e:
            result = {'success': False, 'elapsed': time.time() - start, 'error': str(e)[:50]}

        print_result(name, result)
        if result['success']:
            tv_results.append(result)
            print(f"    TMDB ID: {result.get('id', 'N/A')}")
            print(f"    标题: {result.get('title', 'N/A')}")
            print(f"    年份: {result.get('year', 'N/A')}")
            print(f"    概述: {result.get('overview', 'N/A')[:80]}...")

            # 测试海报
            poster_path = result.get('poster_path', '')
            if poster_path:
                print(f"    测试海报...")
                poster = test_tmdb_poster(poster_path)
                print_result(name, poster, "      ")

        time.sleep(0.5)

        all_results.append({
            'name': name,
            'type': 'tv',
            'search': result,
        })

    # 统计
    print("\n\n" + "=" * 60)
    print("TMDB测试统计")
    print("=" * 60)

    movie_search_ok = sum(1 for r in movie_results if r['success'])
    tv_search_ok = sum(1 for r in tv_results if r['success'])

    print(f"电影搜索成功率: {movie_search_ok}/{len(MOVIES)} ({100*movie_search_ok/len(MOVIES):.0f}%)")
    print(f"电视剧搜索成功率: {tv_search_ok}/{len(TV_SHOWS)} ({100*tv_search_ok/len(TV_SHOWS):.0f}%)")

    return all_results

def main():
    print("=" * 60)
    print("数据源可用性测试")
    print("=" * 60)

    douban_results = run_douban_tests()
    tmdb_results = run_tmdb_tests()

    print("\n\n" + "=" * 60)
    print("测试完成总结")
    print("=" * 60)

    print("\n豆瓣 vs TMDB 对比:")
    print("-" * 40)

    douban_movie_ok = sum(1 for r in douban_results[:5] if r['search']['success'])
    douban_tv_ok = sum(1 for r in douban_results[5:] if r['search']['success'])
    tmdb_movie_ok = sum(1 for r in tmdb_results[:5] if r['search']['success'])
    tmdb_tv_ok = sum(1 for r in tmdb_results[5:] if r['search']['success'])

    print(f"                  豆瓣      TMDB")
    print(f"电影搜索成功率:   {100*douban_movie_ok/5:.0f}%      {100*tmdb_movie_ok/5:.0f}%")
    print(f"电视剧搜索成功率: {100*douban_tv_ok/5:.0f}%      {100*tmdb_tv_ok/5:.0f}%")

if __name__ == '__main__':
    main()