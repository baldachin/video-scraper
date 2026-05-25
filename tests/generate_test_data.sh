#!/bin/bash
# 剧集测试数据生成脚本
# 使用方法: bash generate_test_data.sh

mkdir -p "测试剧集/Friends"
touch "测试剧集/Friends/Friends.S01E01.mp4"
touch "测试剧集/Friends/Friends.S01E02.mp4"
touch "测试剧集/Friends/Friends.S01E03.mp4"
touch "测试剧集/Friends/Friends.S01E04.mp4"
touch "测试剧集/Friends/Friends.S01E05.mp4"

mkdir -p "测试剧集/Stranger Things"
touch "测试剧集/Stranger Things/S02E01.mp4"
touch "测试剧集/Stranger Things/S02E02.mp4"
touch "测试剧集/Stranger Things/S02E03.mp4"

mkdir -p "测试剧集/权力的游戏"
touch "测试剧集/权力的游戏/GOT.S01E01.mp4"
touch "测试剧集/权力的游戏/GOT.S01E02.mp4"
touch "测试剧集/权力的游戏/GOT.S01E03.mp4"
touch "测试剧集/权力的游戏/GOT.S01E04.mp4"
touch "测试剧集/权力的游戏/GOT.S02E01.mp4"
touch "测试剧集/权力的游戏/GOT.S02E02.mp4"

mkdir -p "测试剧集/纪录片"
touch "测试剧集/纪录片/Doc.1x01.mp4"
touch "测试剧集/纪录片/Doc.1x02.mp4"
touch "测试剧集/纪录片/Doc.2x01.mp4"
touch "测试剧集/纪录片/Doc.2x02.mp4"

mkdir -p "测试剧集/综艺"
touch "测试剧集/综艺/Show.S01E01.2023.mp4"
touch "测试剧集/综艺/Show.S01E02.2023.mp4"

echo "测试数据已生成在 ./测试剧集 目录"
echo ""
echo "运行刮削测试:"
echo "  python3 scraper.py '测试剧集' --all --force"
echo ""
echo "清理测试数据:"
echo "  rm -rf 测试剧集"