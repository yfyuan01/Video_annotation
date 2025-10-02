import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
import os
from datetime import datetime
def download_video(url,i):
# 视频页面 URL
# page_url = "https://www.srf.ch/play/tv/arena/video/parteispitzen-zu-us-zoellen-ukraine-und-gaza?urn=urn:srf:video:168db9f4-a1e4-473d-bcda-873c191a0062"

# 请求页面
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    # 解析页面
    soup = BeautifulSoup(response.text, "html.parser")

    # 尝试查找 MP4 下载链接
    video_url = None
    for tag in soup.find_all("a", href=True):
        href = tag['href']
        if href.endswith(".mp4"):
            video_url = href
            break

    # 获取当前时间
    # now = datetime.now()
    # 格式化为字符串，示例：2025-09-16_14-30-00
    # time_str = now.strftime("%Y-%m-%d_%H-%M-%S")

    if video_url:
        print(f"find the video link: {video_url}")
        # 下载视频
        output_file = f"/s3/politperformance/politperformance-data/politicalvideo/video_{i}.mp4"
        with requests.get(video_url, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            chunk_size = 8192

            with open(output_file, 'wb') as f, tqdm(
                total=total_size, unit='B', unit_scale=True, desc='video.mp4'
            ) as bar:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))

        print(f"Download finished: {output_file}")
    else:
        print("MP4 not found")
links = open('video_links.txt', 'r').read().splitlines()
for i,link in tqdm(enumerate(links)):
    path = f"/s3/politperformance/politperformance-data/politicalvideo/video_{i}.mp4"
    if os.path.exists(path):
        continue
    print(f"Downloading video {i}")
    download_video(link,i)
    if i>100:
        break