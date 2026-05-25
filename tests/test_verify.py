#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最终验证脚本 - 确保所有新功能正常工作
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import scraper

def test_all_features():
    """测试所有新功能"""
    print("\n" + "="*70)
    print(" " * 20 + "最终验证 - 所有新功能测试")
    print("="*70)
    
    all_passed = True
    temp_dirs = []
    
    try:
        # ========== 测试1: 海报占位符生成 ==========
        print("\n[1/5] 测试海报占位符生成...")
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            poster_path = tmpdir / "poster.jpg"
            result = scraper.generate_placeholder_poster(str(poster_path), "测试电影.2024.mp4")
            
            if result and poster_path.exists():
                # 验证图片
                from PIL import Image
                img = Image.open(poster_path)
                if img.size == (600, 900):
                    print("  ✓ 海报占位符生成正常 (600x900)")
                else:
                    print(f"  ✗ 海报尺寸错误: {img.size}")
                    all_passed = False
            else:
                print("  ✗ 海报生成失败")
                all_passed = False
        
        # ========== 测试2: 剧集结构完整性检查 ==========
        print("\n[2/5] 测试剧集结构完整性检查...")
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            temp_dirs.append(tmpdir)
            
            # 创建复杂结构
            season01_dir = tmpdir / "完整剧集" / "Season 01"
            season02_dir = tmpdir / "完整剧集" / "Season 02"
            season01_dir.mkdir(parents=True, exist_ok=True)
            season02_dir.mkdir(parents=True, exist_ok=True)
            
            (season01_dir / "Show.S01E01.mp4").touch()
            (season01_dir / "Show.S01E02.mp4").touch()
            (season02_dir / "Show.S02E01.mp4").touch()
            
            # 运行检查
            scraper.check_directory_completeness(tmpdir, {'poster': True, 'nfo': True})
            
            # 验证结果
            checks = [
                (tmpdir / "完整剧集" / "poster.jpg", "剧集根目录海报"),
                (tmpdir / "完整剧集" / "Season 01" / "poster.jpg", "Season 01 海报"),
                (tmpdir / "完整剧集" / "Season 01" / "Show.S01E01.nfo", "Season 01 第1集 NFO"),
                (tmpdir / "完整剧集" / "Season 02" / "Show.S02E01.nfo", "Season 02 第1集 NFO"),
                (tmpdir / "完整剧集" / "Season 01" / "Show.S01E01-thumb.jpg", "Season 01 第1集缩略图"),
            ]
            
            for path, name in checks:
                if path.exists():
                    print(f"  ✓ {name}")
                else:
                    print(f"  ✗ {name} 缺失")
                    all_passed = False
        
        # ========== 测试3: 电影结构完整性检查 ==========
        print("\n[3/5] 测试电影结构完整性检查...")
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            temp_dirs.append(tmpdir)
            
            # 创建电影结构
            movie_dir = tmpdir / "测试电影"
            movie_dir.mkdir(parents=True, exist_ok=True)
            (movie_dir / "Movie.2024.mp4").touch()
            
            # 运行检查
            scraper.check_directory_completeness(tmpdir, {'poster': True, 'nfo': True})
            
            # 验证结果
            checks = [
                (tmpdir / "测试电影" / "poster.jpg", "电影海报"),
                (tmpdir / "测试电影" / "Movie.2024.nfo", "电影 NFO"),
            ]
            
            for path, name in checks:
                if path.exists():
                    print(f"  ✓ {name}")
                else:
                    print(f"  ✗ {name} 缺失")
                    all_passed = False
        
        # ========== 测试4: NFO 文件格式验证 ==========
        print("\n[4/5] 测试 NFO 文件格式...")
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            temp_dirs.append(tmpdir)
            
            # 测试剧集 NFO
            ep_info = {'title': '测试剧集', 'season': 1, 'episode': 5}
            ep_nfo = scraper.generate_nfo(ep_info, 'episode')
            
            if '<?xml' in ep_nfo and '<episodedetails>' in ep_nfo and '<season>1</season>' in ep_nfo:
                print("  ✓ 剧集 NFO 格式正确 (episodedetails)")
            else:
                print("  ✗ 剧集 NFO 格式错误")
                all_passed = False
            
            # 测试电影 NFO
            movie_info = {'title': '测试电影', 'year': '2024'}
            movie_nfo = scraper.generate_nfo(movie_info, 'movie')
            
            if '<?xml' in movie_nfo and '<movie>' in movie_nfo and '<year>2024</year>' in movie_nfo:
                print("  ✓ 电影 NFO 格式正确 (movie)")
            else:
                print("  ✗ 电影 NFO 格式错误")
                all_passed = False
        
        # ========== 测试5: 幂等性验证 ==========
        print("\n[5/5] 测试幂等性...")
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            temp_dirs.append(tmpdir)
            
            # 创建测试结构
            test_dir = tmpdir / "测试目录" / "Season 01"
            test_dir.mkdir(parents=True, exist_ok=True)
            (test_dir / "Test.S01E01.mp4").touch()
            
            # 第一次运行
            scraper.check_directory_completeness(tmpdir, {'poster': True, 'nfo': True})
            
            # 记录第一次的文件
            files_first = set()
            for f in (tmpdir / "测试目录").rglob("*"):
                if f.is_file():
                    files_first.add(f.name)
            
            # 第二次运行
            scraper.check_directory_completeness(tmpdir, {'poster': True, 'nfo': True})
            
            # 记录第二次的文件
            files_second = set()
            for f in (tmpdir / "测试目录").rglob("*"):
                if f.is_file():
                    files_second.add(f.name)
            
            if files_first == files_second:
                print("  ✓ 幂等性验证通过 (重复运行无变化)")
            else:
                added = files_second - files_first
                removed = files_first - files_second
                if added or removed:
                    print(f"  ✗ 幂等性验证失败")
                    print(f"    新增: {added}")
                    print(f"    删除: {removed}")
                    all_passed = False
        
    except Exception as e:
        print(f"\n  ✗ 测试过程出现异常: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    # ========== 最终总结 ==========
    print("\n" + "="*70)
    if all_passed:
        print(" " * 25 + "🎉 所有测试通过！")
        print("\n新增功能验证成功:")
        print("  ✓ 海报占位符生成")
        print("  ✓ 目录完整性检查")
        print("  ✓ NFO 文件生成")
        print("  ✓ 多层目录结构支持")
        print("  ✓ 幂等性保证")
        print("\n可以正常使用以下命令:")
        print("  python3 scraper.py <目录> --check  # 检查并修复")
        print("  python3 scraper.py <目录> --all     # 完整刮削")
        return 0
    else:
        print(" " * 25 + "⚠ 部分测试失败")
        print("\n请检查上述输出中的 ✗ 项，并查看完整错误信息。")
        return 1
    
    print("="*70)

if __name__ == '__main__':
    sys.exit(test_all_features())
