# find the title and description of each website
import requests
from bs4 import BeautifulSoup
import json
from tqdm import tqdm
# SRF 视频页面 URL
def get_info(url):
# url = "https://www.srf.ch/play/tv/arena/video/abstimmungs-arena-initiative-gegen-heiratsstrafe?urn=urn:srf:video:751941f0-2d71-4316-b678-31d457e7f882"

    # 请求网页
    response = requests.get(url)
    response.encoding = 'utf-8'
    response.raise_for_status()  # 确保请求成功

    # 解析 HTML
    soup = BeautifulSoup(response.text, "html.parser")

    # 获取网页标题
    title = soup.title.string.rstrip(' - Arena - Play SRF') if soup.title else "No title found"

    # 获取描述内容（og:description）
    meta_desc = soup.find("meta", property="og:description")
    description = meta_desc["content"] if meta_desc else "No description found"
    return title, description

if __name__ == "__main__":
    with open('video_links.txt') as f:
        links = f.read().splitlines()
    with open('video_info.json', 'w', encoding="utf-8") as f:
        for link in tqdm(links):
            try:
                title, description = get_info(link)
            except Exception as e:
                title, description = None, None
            d = {'title': title, 'description': description, 'link': link}
            json_str = json.dumps(d, ensure_ascii=False, indent=2)
            f.write(json_str+'\n')
            # break
    # print("Title:", title)
    # print("Description:", description)

# # 如果需要正文内容，可以根据 HTML 结构抓取 <p> 或 <div> 标签
# # 示例（根据网页结构调整选择器）
# paragraphs = soup.find_all("p")
# content = "\n".join([p.get_text() for p in paragraphs])
# print("Content:", content)
