from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import time
url = 'https://www.srf.ch/play/tv/sendung/arena?id=09784065-687b-4b60-bd23-9ed0d2d43cdc'

driver = webdriver.Chrome(service=ChromeService(
    ChromeDriverManager().install()))

driver.get(url)
time.sleep(3)  # 等待3秒，具体等待时间视网页内容加载情况而定

print(driver.page_source)
click_count = 0
max_clicks = 20
while click_count < max_clicks:
    try:
        buttons = driver.find_elements(By.CSS_SELECTOR,
            "button.Button__StyledButton-sc-1hu80ko-0.cjbhNt.LoadMore__StyledSecondaryButton-sc-1m7lrrf-1.fLJWjy"
        )
        print(f"Found {len(buttons)} buttons")
        if buttons:
            buttons[0].click()
        click_count += 1
        time.sleep(5)
    except:
        break
print('finished loading all videos')

# 获取所有 video 链接
video_links = set()
videos = driver.find_elements(By.CSS_SELECTOR, "a.MediaTeaserWrapper__StyledLink-sc-5tzc7y-1")
print(len(videos))
for video in videos:
    link = video.get_attribute("href")
    video_links.add(link)

driver.quit()

# 保存到 txt 文件
with open("video_links.txt", "w") as f:
    for link in video_links:
        f.write(link + "\n")

print(f"共抓取 {len(video_links)} 个视频链接，已保存到 video_links.txt")
#
# from selenium import webdriver
# from selenium.webdriver.common.by import By
# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# import time
#
# # Chrome 无头模式
# chrome_options = Options()
# chrome_options.add_argument("--headless")
# chrome_options.add_argument("--disable-gpu")
#
# driver = webdriver.Chrome(options=chrome_options)
# driver.get("https://www.srf.ch/play/tv/arena")
# live_html = driver.execute_script("return document.documentElement.outerHTML")
#
# # Save to file
# with open("live_dom.txt", "w", encoding="utf-8") as f:
#     f.write(live_html)
# breakpoint()
# # wait for page load
# wait = WebDriverWait(driver, 10)
# # 点击次数计数
# click_count = 0
# max_clicks = 5
#
# while click_count < max_clicks:
#     try:
#         print(driver.page_source)
#         load_more = wait.until(
#             EC.element_to_be_clickable((By.XPATH, '//button//*[text()="Load more"]/ancestor::button'))
#         )
#         breakpoint()
#         print(load_more.text)
#         click_count += 1
#         load_more.click()
#         click_count += 1
#         time.sleep(2)  # 等待内容加载
#         print('click_count =', click_count)
#     except:
#         print('not found')
#         # 没有按钮可点击时提前结束
#         break
#
# # 获取所有 video 链接
# video_links = set()
# videos = driver.find_elements(By.XPATH, '//a[contains(@href, "/play/tv/arena/video/")]')
#
# for video in videos:
#     link = video.get_attribute("href")
#     video_links.add(link)
#
# driver.quit()
#
# # 保存到 txt 文件
# with open("video_links.txt", "w") as f:
#     for link in video_links:
#         f.write(link + "\n")
#
# print(f"共抓取 {len(video_links)} 个视频链接，已保存到 video_links.txt")
