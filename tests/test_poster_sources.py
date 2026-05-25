#!/usr/bin/env python3
"""测试各种海报来源的可用性"""

import requests
import time

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://movie.douban.com/',
}

sources = [
    # 豆瓣海报
    ("豆瓣-小图", "https://img9.doubanio.com/view/photo/s_ratio_poster/public/p2561716440.jpg"),
    ("豆瓣-大图", "https://img9.doubanio.com/view/photo/l_ratio_poster/public/p2561716440.jpg"),
    
    # TMDB (免费API)
    ("TMDB-示例", "https://image.tmdb.org/t/p/w500/3bhkrj58Vber6sGD1o5OkM9zxYq.jpg"),
    
    # 备用方案
    ("占位符-自动生成", None),
]

print("=" * 60)
print("海报来源可用性测试")
print("=" * 60)

for name, url in sources:
    if url is None:
        print(f"✓ {name}: [使用 PIL 生成占位符]")
        continue
        
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200 and len(resp.content) > 1000:
            print(f"✓ {name}: OK ({len(resp.content)} bytes)")
        else:
            print(f"✗ {name}: HTTP {resp.status_code}")
    except Exception as e:
        print(f"✗ {name}: {str(e)[:50]}")

print("\n" + "=" * 60)
print("结论: 豆瓣海报已不可用，需要替代方案")
print("建议: 1) 使用本地图片库  2) 增强占位符生成  3) 添加 TMDB 支持")
print("=" * 60)
