import yt_dlp
import os
from tqdm import tqdm
# 读取链接
with open("video_links.txt", "r", encoding="utf-8") as f:
    links = [line.strip() for line in f if line.strip()]

# 创建字幕文件夹
os.makedirs("subtitles", exist_ok=True)

# yt-dlp 配置
ydl_opts = {
    "skip_download": True,        # 不下载视频
    "writesubtitles": True,       # 下载字幕
    "subtitleslangs": ["de"],     # 只要德语字幕
    "subtitlesformat": "vtt",     # 保存为 .vtt
    "outtmpl": "%(id)s.%(ext)s",  # 临时命名，后面再重命名
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    for i, url in tqdm(enumerate(links)):
        try:
            info = ydl.extract_info(url, download=True)
            video_id = info.get("id")
            subtitle_file = f"{video_id}.de.vtt"
            new_name = os.path.join("subtitles", f"{i}.vtt")

            if os.path.exists(subtitle_file):
                os.rename(subtitle_file, new_name)
                print(f"✅ {url} -> {new_name}")
            else:
                print(f"⚠️ 没有找到字幕: {url}")

        except Exception as e:
            print(f"❌ 下载失败 {url}: {e}")
