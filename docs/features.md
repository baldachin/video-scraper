# 视频刮削工具 - 新功能说明

## 功能概览

本次更新新增了两个重要功能：

### 1. 无刮削数据时使用视频帧作为海报占位

当无法从豆瓣获取海报时，系统会自动从视频文件中提取一帧作为海报。

#### 实现方式

系统按优先级尝试以下方法：

1. **ffmpeg** (优先): 如果系统中安装了 ffmpeg，直接从视频提取帧
2. **OpenCV** (备选): 如果 Python 环境中有 cv2 库，使用它提取帧
3. **PIL 占位符** (最后手段): 生成一个带有视频名称的占位图片

#### 占位符图片特点

使用 PIL 生成的占位符图片包含：
- 2:3 比例的竖版海报尺寸 (600x900)
- 深色渐变背景
- 视频文件名称
- "🎬" 图标
- "【 无刮削数据 - 自动生成 】" 标识

#### 使用示例

```bash
# 在刮削过程中自动应用
python3 scraper.py . --all

# 即使有刮削数据也强制从视频提取帧
python3 scraper.py . --poster --extract-frame
```

### 2. 子目录完整性检查和自动补全

检查目录结构是否符合规则，并自动修复缺失的内容。

#### 检查项目

1. **海报检查**
   - 每个目录应有 `poster.jpg`
   - 如果缺失，从视频提取或从其他目录复制

2. **NFO 文件检查**
   - 剧集根目录应有 `tvshow.nfo`
   - 每季目录应有 `tvshow.nfo`
   - 每集应有对应的 `{集名}.nfo`
   - 电影目录应有 `{电影名}.nfo`

3. **缩略图检查**
   - 剧集的每集应有 `{集名}-thumb.jpg`

4. **目录结构检查**
   - 剧集根目录 → Season 子目录 → 视频文件
   - 自动识别并处理多层嵌套

#### 使用示例

```bash
# 检查并修复目录完整性
python3 scraper.py . --check

# 检查特定目录
python3 scraper.py "电影目录" --check
```

#### 自动修复内容

当发现缺失时，系统会：

- **复制现有海报**: 如果子目录有海报，复制到父目录；反之亦然
- **提取视频帧**: 使用 `extract_video_frame()` 从视频生成海报
- **生成 NFO**: 创建符合格式的 NFO 文件，包含基本信息
- **复制缩略图**: 从季海报复制到每集作为缩略图

#### 修复流程示例

```
输入: 剧集目录/Season 01/剧集.S01E01.mp4
检测: 缺少 poster.jpg, 缺少 剧集.S01E01.nfo, 缺少 剧集.S01E01-thumb.jpg
修复:
  ✓ 从视频提取 poster.jpg
  ✓ 生成 剧集.S01E01.nfo
  ✓ 生成 剧集.S01E01-thumb.jpg
```

## 命令行参数

| 参数 | 简写 | 说明 |
|------|------|------|
| `--check` | `-c` | 检查目录完整性并自动修复 |
| `--extract-frame` | `-e` | 即使有刮削数据也强制从视频提取帧 |
| `--poster` | `-p` | 下载/生成海报 |
| `--nfo` | `-n` | 生成 NFO 文件 |
| `--all` | `-a` | 执行全部操作 |

## 典型使用场景

### 场景1: 批量处理新下载的视频

```bash
# 刮削并整理
python3 scraper.py 下载目录 --all

# 检查并补充缺失内容
python3 scraper.py 下载目录 --check
```

### 场景2: 整理混乱的媒体库

```bash
# 对整个媒体库进行检查和修复
python3 scraper.py /path/to/media --check
```

### 场景3: 只想补充缺失的海报

```bash
# 只检查和补充海报
python3 scraper.py . --poster --check
```

## 技术细节

### 视频帧提取逻辑

```python
def extract_video_frame(video_path, output_path, timestamp=None):
    # 1. 优先使用 ffmpeg
    if shutil.which('ffmpeg'):
        # 获取视频时长，取 10% 位置
        timestamp = duration * 0.1
        subprocess.run(['ffmpeg', '-ss', str(timestamp), ...])
    
    # 2. 备选 cv2
    elif HAS_CV2:
        cap = cv2.VideoCapture(video_path)
        cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        ret, frame = cap.read()
        cv2.imwrite(output_path, frame)
    
    # 3. 最后手段：PIL 占位符
    else:
        generate_placeholder_poster(output_path, video_name)
```

### 完整性检查流程

```python
def check_directory_completeness(root_path, options):
    for dir_path in root_path.rglob('*'):
        if not dir_path.is_dir():
            continue
        
        # 识别目录类型
        if is_series_root(dir_path):
            # 检查 tvshow.nfo 和 poster.jpg
            ...
        elif is_season_dir(dir_path):
            # 检查每集的 nfo 和 thumb
            ...
        elif is_movie_dir(dir_path):
            # 检查海报和电影的 nfo
            ...
        
        # 应用必要的修复
        if needs_fix:
            apply_fixes()
```

## 注意事项

1. **视频文件**: 占位符功能需要真实的视频文件才能提取帧，空文件只能生成占位符
2. **多次运行安全**: 检查功能是幂等的，多次运行不会重复修复
3. **刮削优先**: 刮削数据会优先于视频帧提取
4. **备份建议**: 首次使用建议备份重要数据

## 故障排除

### Q: 海报提取失败怎么办？

A: 确保系统有 ffmpeg 或 Python 环境有 cv2：
```bash
# 安装 ffmpeg (Ubuntu/Debian)
sudo apt-get install ffmpeg

# 安装 OpenCV (Python)
pip install opencv-python
```

### Q: 生成的占位符图片太小？

A: PIL 占位符固定为 600x900，可使用 ffmpeg 获得更好的质量。

### Q: 检查功能修复了不想改动的文件？

A: 可以只检查不修复的预览模式（未来版本支持）。
