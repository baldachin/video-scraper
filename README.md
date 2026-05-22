# 视频刮削工具

一个功能强大的视频刮削工具，支持从豆瓣获取电影/剧集信息，自动整理媒体库。

## 🎯 最新更新 (v2.0)

### ✨ 新增功能

#### 1. 智能海报占位符系统
当无法获取刮削数据时，系统会自动从视频提取帧或生成专业的占位符海报。

**技术特点**:
- 多级降级策略：ffmpeg → OpenCV → PIL
- 智能选择视频位置（自动选择正片开始后的帧）
- 生成专业级占位图片 (600x900)

#### 2. 目录完整性自动检查
自动检查媒体库中的缺失内容，并智能修复。

**检查项目**:
- 海报文件 (poster.jpg)
- NFO 元数据文件
- 剧集缩略图 (-thumb.jpg)
- 目录结构完整性

**自动修复**:
- 从视频提取帧生成海报
- 复制已有资源到缺失位置
- 生成符合 Kodi 标准的 NFO 文件

## 📖 快速开始

### 基础命令

```bash
# 检查并修复目录完整性（推荐首先使用）
python3 scraper.py /path/to/media --check

# 执行完整刮削
python3 scraper.py /path/to/media --all

# 只下载/生成海报
python3 scraper.py /path/to/media --poster

# 查看帮助
python3 scraper.py --help
```

### 典型使用场景

#### 场景 1: 新下载视频的快速整理
```bash
# 1. 刮削并整理
python3 scraper.py ~/Downloads/movies --all

# 2. 检查并补充缺失内容
python3 scraper.py ~/Downloads/movies --check
```

#### 场景 2: 整理混乱的媒体库
```bash
# 对整个媒体库进行检查和修复
python3 scraper.py /media/library --check
```

#### 场景 3: 只补充缺失的海报
```bash
# 只检查和补充海报
python3 scraper.py . --poster --check
```

## 🔧 功能列表

| 参数 | 简写 | 说明 |
|------|------|------|
| `--check` | `-c` | 检查目录完整性并自动修复 |
| `--poster` | `-p` | 下载/生成海报 |
| `--nfo` | `-n` | 生成 NFO 文件 |
| `--all` | `-a` | 执行全部操作 |
| `--force` | `-f` | 强制处理未匹配的文件 |
| `--extract-frame` | `-e` | 即使有刮削数据也强制从视频提取帧 |

## 📁 支持的媒体类型

### 电影
```
电影名 (2024)/
├── poster.jpg
├── 电影名 (2024).mp4
└── 电影名 (2024).nfo
```

### 剧集
```
剧集名/
├── poster.jpg
├── tvshow.nfo
├── Season 01/
│   ├── poster.jpg
│   ├── tvshow.nfo
│   ├── 剧集名 - S01E01.mp4
│   ├── 剧集名 - S01E01.nfo
│   ├── 剧集名 - S01E01-thumb.jpg
│   └── ...
└── Season 02/
    └── ...
```

### 纪录片/综艺
结构同剧集

## 🛠️ 安装依赖

### 必需
- Python 3.6+
- requests
- mutagen
- Pillow

### 可选（推荐安装以获得最佳效果）
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# Python 依赖
pip install requests mutagen Pillow opencv-python
```

## 📊 测试结果

运行验证脚本确认所有功能正常：
```bash
python3 验证脚本.py
```

预期输出：
```
🎉 所有测试通过！

新增功能验证成功:
  ✓ 海报占位符生成
  ✓ 目录完整性检查
  ✓ NFO 文件生成
  ✓ 多层目录结构支持
  ✓ 幂等性保证
```

## 📝 文档

- [新功能说明.md](新功能说明.md) - 详细的功能介绍和使用指南
- [更新总结.md](更新总结.md) - 完整的更新日志和技术细节
- [快速参考.txt](快速参考.txt) - 命令速查卡片
- [test_suite.py](test_suite.py) - 完整的测试套件
- [验证脚本.py](验证脚本.py) - 功能验证脚本

## ⚠️ 注意事项

1. **备份重要数据**: 首次使用建议备份重要媒体文件
2. **视频文件**: 占位符功能需要真实视频文件才能提取帧
3. **刮削优先**: 刮削数据会优先于视频帧提取
4. **多次运行安全**: 检查功能是幂等的，重复运行不会重复修复

## 🐛 故障排除

### 问题: 海报提取失败
**解决**: 安装 ffmpeg
```bash
sudo apt-get install ffmpeg
```

### 问题: 想要更好的海报质量
**解决**: 使用 `--extract-frame` 强制从视频提取
```bash
python3 scraper.py . --poster --extract-frame
```

### 问题: 某些视频没有被处理
**解决**: 使用 `--force` 强制处理
```bash
python3 scraper.py . --all --force
```

## 🔮 未来计划

- [ ] 支持手动选择视频帧位置
- [ ] 添加预览模式的检查功能
- [ ] 支持自定义海报模板
- [ ] 添加批量重命名功能
- [ ] 支持更多视频格式的元数据提取

## 📜 许可证

MIT License

## 👥 贡献

欢迎提交 Issue 和 Pull Request！

---

**版本**: v2.0  
**更新日期**: 2024年5月22日
