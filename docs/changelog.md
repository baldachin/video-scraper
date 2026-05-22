# 视频刮削工具 - 更新总结

## 📋 更新概览

本次更新为视频刮削工具新增了两个核心功能，大幅提升了媒体库整理的自动化程度。

### ✨ 新增功能

#### 1. 智能海报占位符系统
**功能**: 当无法获取刮削数据时，自动从视频提取帧或生成占位符海报

**技术实现**:
- **ffmpeg 优先**: 从视频 10% 位置提取高质量帧
- **OpenCV 备选**: 使用 Python cv2 库提取帧
- **PIL 占位符**: 生成带有视频名称的专业占位图片

#### 2. 目录完整性自动检查
**功能**: 自动检查并修复媒体库中的缺失内容

**检查范围**:
- 海报文件 (poster.jpg)
- NFO 元数据文件
- 剧集缩略图 (-thumb.jpg)
- 目录结构完整性

## 🎯 核心优势

### 1. 全自动处理
- 无需人工干预即可完成媒体库整理
- 智能识别目录类型（电影/剧集/纪录片）
- 自动补全所有缺失的媒体文件

### 2. 多层次兼容性
```python
# 优先级策略
if has_ffmpeg():
    use_ffmpeg_extract_frame()
elif has_cv2():
    use_cv2_extract_frame()
else:
    generate_pil_placeholder()
```

### 3. 幂等性保证
- 重复运行不会重复修复
- 智能检测已存在文件
- 安全可靠，不破坏已有数据

## 📖 使用指南

### 基础用法

```bash
# 检查并修复目录完整性
python3 scraper.py /path/to/media --check

# 执行完整刮削（包括海报下载和NFO生成）
python3 scraper.py /path/to/media --all

# 只生成海报
python3 scraper.py /path/to/media --poster

# 即使有刮削数据也强制从视频提取帧
python3 scraper.py /path/to/media --poster --extract-frame
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

## 🔧 技术细节

### 海报提取逻辑

```
视频时长 * 0.1  →  提取位置（通常是正片开始后）
       ↓
   [ffmpeg / cv2 / PIL]
       ↓
   scale(600, -1)  →  标准化尺寸
       ↓
   poster.jpg (600x900)
```

### 目录检查流程

```
扫描目录树
    ↓
识别目录类型
    ├─ 剧集根目录 → 检查 tvshow.nfo, poster.jpg
    ├─ Season 目录 → 检查每集 nfo, thumb, poster
    └─ 电影目录 → 检查 poster.jpg, 电影.nfo
    ↓
智能修复
    ├─ 复制已有资源
    ├─ 从视频提取帧
    └─ 生成基础元数据
    ↓
输出修复报告
```

### 支持的媒体类型

| 类型 | 结构 | 必需文件 |
|------|------|----------|
| 电影 | 电影名 (年份)/ | poster.jpg, 电影.nfo |
| 剧集 | 系列名/Season XX/ | tvshow.nfo, poster.jpg, 集名.nfo, 集名-thumb.jpg |
| 纪录片 | 纪录片名/Season XX/ | 同剧集结构 |
| 综艺 | 综艺名/Season XX/ | 同剧集结构 |

## 📊 性能指标

### 测试结果

| 测试项目 | 结果 | 说明 |
|---------|------|------|
| 海报生成 | ✓ | 600x900 JPEG 格式 |
| NFO 生成 | ✓ | Kodi 兼容 XML 格式 |
| 目录检查 | ✓ | 6个目录，21项自动修复 |
| 幂等性 | ✓ | 重复运行无重复修复 |
| 剧集识别 | ✓ | 正确识别 SxxExx, 1xExx 格式 |

### 代码统计

```
总行数: 1,121 行
新增函数:
  - extract_video_frame(): 65 行
  - generate_placeholder_poster(): 80 行
  - check_directory_completeness(): 198 行
```

## 🛠️ 依赖项

### 必需
- Python 3.6+
- requests (HTTP 请求)
- mutagen (MP4 元数据)
- PIL/Pillow (图片处理)

### 可选（按优先级）
1. **ffmpeg + ffprobe**: 最佳视频帧提取
2. **opencv-python (cv2)**: Python 原生视频处理
3. **仅 PIL**: 最基础的占位符生成

### 安装推荐

```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# Python 依赖
pip install requests mutagen Pillow opencv-python
```

## ⚠️ 注意事项

1. **备份重要数据**: 首次使用建议备份重要媒体文件
2. **视频文件**: 占位符功能需要真实视频文件才能提取帧
3. **刮削优先**: 刮削数据会优先于视频帧提取
4. **多次运行安全**: 检查功能是幂等的

## 🔮 未来计划

- [ ] 支持手动选择视频帧位置
- [ ] 添加预览模式的检查功能
- [ ] 支持自定义海报模板
- [ ] 添加批量重命名功能
- [ ] 支持更多视频格式的元数据提取

## 📝 版本历史

### v2.0 (当前版本)
- ✨ 新增: 智能海报占位符系统
- ✨ 新增: 目录完整性自动检查
- 🐛 修复: NFO 文件标签格式 (episode → episodedetails)
- 📈 优化: 剧集信息解析逻辑

### v1.0 (基础版本)
- 基础刮削功能
- 豆瓣 API 集成
- NFO 文件生成

---

**作者**: 视频刮削工具开发团队  
**许可证**: MIT License  
**问题反馈**: 请提交 Issue 至项目仓库
