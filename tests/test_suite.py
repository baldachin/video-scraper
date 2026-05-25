#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频刮削工具 - 测试套件
验证新功能的正确性
"""

import os
import sys
import shutil
import tempfile
from pathlib import Path

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import scraper

def test_poster_generation():
    """测试海报生成功能"""
    print("\n" + "="*60)
    print("测试1: 海报占位符生成")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # 测试生成占位符
        poster_path = tmpdir / "poster.jpg"
        video_name = "测试电影.2024.1080p.mp4"
        
        result = scraper.generate_placeholder_poster(str(poster_path), video_name)
        
        print(f"✓ 生成结果: {'成功' if result else '失败'}")
        print(f"✓ 文件是否存在: {poster_path.exists()}")
        
        if poster_path.exists():
            size = poster_path.stat().st_size
            print(f"✓ 文件大小: {size} bytes")
            
            # 检查是否是有效的图片
            try:
                from PIL import Image
                img = Image.open(poster_path)
                print(f"✓ 图片尺寸: {img.size}")
                print(f"✓ 图片格式: {img.format}")
            except Exception as e:
                print(f"✗ 图片验证失败: {e}")
        
        return result and poster_path.exists()

def test_directory_structure_creation():
    """测试目录结构创建"""
    print("\n" + "="*60)
    print("测试2: 目录结构检查")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # 创建测试结构
        test_dirs = [
            tmpdir / "电影1",
            tmpdir / "剧集1" / "Season 01",
            tmpdir / "剧集1" / "Season 02",
        ]
        
        test_files = [
            tmpdir / "电影1" / "movie.mp4",
            tmpdir / "剧集1" / "Season 01" / "show.S01E01.mp4",
            tmpdir / "剧集1" / "Season 01" / "show.S01E02.mp4",
            tmpdir / "剧集1" / "Season 02" / "show.S02E01.mp4",
        ]
        
        # 创建目录和文件
        for d in test_dirs:
            d.mkdir(parents=True, exist_ok=True)
        for f in test_files:
            f.touch()
        
        print(f"✓ 创建测试目录: {len(test_dirs)}")
        print(f"✓ 创建测试文件: {len(test_files)}")
        
        # 运行完整性检查
        scraper.check_directory_completeness(tmpdir, {'poster': True, 'nfo': True})
        
        # 验证结果
        results = {
            '电影海报': (tmpdir / "电影1" / "poster.jpg").exists(),
            '剧集海报': (tmpdir / "剧集1" / "Season 01" / "poster.jpg").exists(),
            '剧集根海报': (tmpdir / "剧集1" / "poster.jpg").exists(),
            '季1NFO': (tmpdir / "剧集1" / "Season 01" / "show.S01E01.nfo").exists(),
            '季2NFO': (tmpdir / "剧集1" / "Season 02" / "show.S02E01.nfo").exists(),
        }
        
        print("\n生成文件检查:")
        all_pass = True
        for name, exists in results.items():
            status = "✓" if exists else "✗"
            print(f"  {status} {name}: {'存在' if exists else '缺失'}")
            if not exists:
                all_pass = False
        
        return all_pass

def test_nfo_generation():
    """测试 NFO 文件生成"""
    print("\n" + "="*60)
    print("测试3: NFO 文件生成")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # 测试剧集 NFO
        episode_info = {
            'title': '测试剧集',
            'season': 1,
            'episode': 5
        }
        
        ep_nfo_path = tmpdir / "测试剧集.S01E05.nfo"
        nfo_content = scraper.generate_nfo(episode_info, 'episode')
        
        with open(ep_nfo_path, 'w', encoding='utf-8') as f:
            f.write(nfo_content)
        
        print(f"✓ NFO 文件创建: {ep_nfo_path.exists()}")
        
        # 验证内容
        with open(ep_nfo_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = [
            ('<?xml' in content, 'XML 头'),
            ('<episodedetails>' in content, 'Episode 标签'),
            ('<season>1</season>' in content, '季号'),
            ('<episode>5</episode>' in content, '集号'),
        ]
        
        all_pass = True
        for check, name in checks:
            status = "✓" if check else "✗"
            print(f"  {status} {name}: {'通过' if check else '失败'}")
            if not check:
                all_pass = False
        
        return all_pass

def test_filename_sanitization():
    """测试文件名清理"""
    print("\n" + "="*60)
    print("测试4: 文件名清理")
    print("="*60)
    
    test_cases = [
        ("test:file*name?.mp4", "test_file_name_.mp4"),
        ("电影 (2024).mp4", "电影 (2024).mp4"),
        ("normal_name.mp4", "normal_name.mp4"),
    ]
    
    all_pass = True
    for input_name, expected in test_cases:
        result = scraper.sanitize_filename(input_name)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{input_name}' -> '{result}'")
        if result != expected:
            all_pass = False
    
    return all_pass

def test_episode_parsing():
    """测试剧集信息解析"""
    print("\n" + "="*60)
    print("测试5: 剧集信息解析")
    print("="*60)
    
    test_cases = [
        ("Show.S01E05.mp4", (1, 5)),
        ("Movie.2024.1080p.mp4", (None, None)),
        ("Series 1x01.mp4", (1, 1)),
        ("Episode.E02.mkv", (1, 2)),  # E02 格式匹配，默认第1季
        ("Test.5x03.avi", (5, 3)),   # 1x03 格式
        ("NoEpisode.mp4", (None, None)),  # 无剧集信息
    ]
    
    all_pass = True
    for filename, expected in test_cases:
        result = scraper.parse_episode_info(filename)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{filename}' -> {result} (期望: {expected})")
        if result != expected:
            all_pass = False
    
    return all_pass

def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("视频刮削工具 - 功能测试套件")
    print("="*60)
    
    tests = [
        ("海报生成", test_poster_generation),
        ("目录结构检查", test_directory_structure_creation),
        ("NFO 文件生成", test_nfo_generation),
        ("文件名清理", test_filename_sanitization),
        ("剧集信息解析", test_episode_parsing),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ 测试 '{test_name}' 异常: {e}")
            results.append((test_name, False))
    
    # 打印总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {status}: {test_name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠ {total - passed} 个测试失败")
        return 1

if __name__ == '__main__':
    sys.exit(main())
