# 视频刮削工具

一个功能强大的视频刮削工具，支持从 TMDB 获取电影/剧集信息，自动整理媒体库。

## 特性

- 智能识别输入目录中的视频（电影/剧集/综艺/纪录片）
- 自动从 TMDB 获取刮削数据
- 生成符合 Kodi 标准的 NFO 文件
- 下载海报、fanart、clearlogo 等图片
- 支持输出到指定目录
- 刮削失败时记录到 `failed_scrape.json`

## 安装

```bash
pip install requests mutagen Pillow
```

## 使用方法

```bash
# 基本用法：刮削到指定输出目录
python src/scraper.py --input "/path/to/video.mp4" --output "/path/to/output" --all

# 处理整个目录
python src/scraper.py --input "/path/to/folder" --output "/path/to/output" --all

# 复制模式（不移动原文件）
python src/scraper.py --input "/path/to/folder" --output "/path/to/output" --copy --poster --nfo

# 检查目录完整性
python src/scraper.py --input "/path/to/folder" --check
```

## 命令行参数

| 参数 | 说明 |
|------|------|
| `--input`, `-i` | 输入目录或文件路径 |
| `--output`, `-o` | 输出目录路径 |
| `--poster`, `-p` | 下载海报 |
| `--nfo`, `-n` | 生成 NFO 文件 |
| `--all`, `-a` | 执行全部操作 |
| `--copy` | 复制模式（不移动原文件） |
| `--check` | 检查目录完整性 |
| `--force`, `-f` | 强制处理未匹配的文件 |

## 输出目录结构

### 电影
```
{输出目录}/{中文名} ({年份})/
├── {中文名} ({年份}) {分辨率} {音频编码}.mp4
├── {中文名} ({年份}) {分辨率} {音频编码}.nfo
├── {中文名} ({年份}) {分辨率} {音频编码}-poster.jpg
├── {中文名} ({年份}) {分辨率} {音频编码}-fanart.jpg
├── {中文名} ({年份}) {分辨率} {音频编码}-clearlogo.png
└── movie.nfo
```

### 剧集
```
{输出目录}/{剧集名}/
├── tvshow.nfo
├── poster.jpg
├── fanart.jpg
├── clearlogo.png (可选)
├── Season {数字}/
│   ├── {剧集名} - S{季}E{集} - {中文集名}.nfo
│   └── {剧集名} - S{季}E{集} - {中文集名}-thumb.jpg
└── season{数字}-poster.jpg
```

## 配置代理

TMDB API 需要代理访问。在 `src/scraper.py` 中修改：

```python
PROXIES = {
    'http': 'http://127.0.0.1:7890',
    'https': 'http://127.0.0.1:7890',
}
```

## 依赖

- Python 3.6+
- requests
- mutagen
- Pillow

可选（用于从视频提取帧）：
- ffmpeg
- opencv-python

## 许可证

MIT