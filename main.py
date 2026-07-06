from log import log
import requests
from lxml import etree
import re
import html2text
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from PIL import Image
import tempfile
import time
import os


# ======================
# Telegram 发送文本
# ======================
def send_telegram_message(message: str) -> bool:
    token = os.environ.get("TG_TOKEN")
    chat_id = os.environ.get("TG_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
    }
    try:
        r = requests.post(url, data=payload, timeout=15)
        if r.status_code != 200:
            log.logger.warning(f"Tg文本发送失败: {r.text}")
        return r.status_code == 200
    except Exception as e:
        log.logger.error(f"Tg文本异常: {e}")
        return False


# ======================
# 图片下载
# ======================
def download_image(url, save_path):
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X)",
        "Referer": "https://m.ds.163.com/"
    }
    try:
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code == 200 and r.headers.get("Content-Type", "").startswith("image"):
            with open(save_path, "wb") as f:
                f.write(r.content)
            return True
        else:
            log.logger.warning(f"非图片内容: {url}")
    except Exception as e:
        log.logger.warning(f"图片下载失败 {url}: {e}")
    return False


# ======================
# 压缩图片
# ======================
def compress_image_to_limit(src_path, max_mb=9.5):
    max_bytes = max_mb * 1024 * 1024
    if os.path.getsize(src_path) <= max_bytes:
        return src_path

    try:
        img = Image.open(src_path)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        quality = 90
        tmp_path = src_path + "_compressed.jpg"
        while quality >= 30:
            img.save(tmp_path, "JPEG", quality=quality, optimize=True)
            if os.path.getsize(tmp_path) <= max_bytes:
                log.logger.info(f"图片压缩成功 {os.path.getsize(tmp_path)/1024/1024:.2f}MB q={quality}")
                return tmp_path
            quality -= 10

        log.logger.warning("图片压缩失败，仍大于 10MB")
        return src_path
    except Exception as e:
        log.logger.error(f"图片压缩异常: {e}")
        return src_path


# ======================
# 发送图片
# ======================
def send_telegram_media(filepath):
    send_path = compress_image_to_limit(filepath)
    size_mb = os.path.getsize(send_path) / 1024 / 1024
    token = os.environ.get("TG_TOKEN")
    chat_id = os.environ.get("TG_CHAT_ID")

    try:
        if size_mb <= 9.5:
            url = f"https://api.telegram.org/bot{token}/sendPhoto"
            files = {"photo": open(send_path, "rb")}
        else:
            url = f"https://api.telegram.org/bot{token}/sendDocument"
            files = {"document": open(send_path, "rb")}

        data = {"chat_id": chat_id}
        r = requests.post(url, files=files, data=data, timeout=60)
        if r.status_code != 200:
            log.logger.warning(f"Tg媒体发送失败({size_mb:.2f}MB): {r.text}")
    except Exception as e:
        log.logger.error(f"Tg媒体异常: {e}")
    finally:
        for f in files.values():
            f.close()
        if send_path != filepath and os.path.exists(send_path):
            os.unlink(send_path)


# ======================
# 发送文本 + 图片
# ======================
def send_content_list_grouped(content_list):
    buffer = ""
    for type_, data in content_list:
        if type_ == "text":
            buffer += data + "\n"
        elif type_ == "img":
            if buffer.strip():
                send_telegram_message(buffer.strip())
                buffer = ""
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                if download_image(data, tmp.name):
                    send_telegram_media(tmp.name)
                os.unlink(tmp.name)
            time.sleep(0.5)
    if buffer.strip():
        send_telegram_message(buffer.strip())


# ======================
# README.md 覆盖更新（SkyTask 样式）
# ======================
def push_to_readme_latest(title, md_content, html_content):
    md_full = f"# {title}\n{md_content}"

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(md_full)
    with open("readme.txt", "w", encoding="utf-8") as f:
        f.write(md_full)

    log.logger.info(f"README.md 已覆盖更新：{title}")


# ======================
# SkyTask 类
# ======================
class SkyTask:
    def __init__(self):
        self.header = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X)"}
        self.index_url = "https://m.ds.163.com/user/0c565eef3c904d84b23f5624ff67f853"

    def getIndex(self) -> list:
        try:
            resp = requests.get(self.index_url, headers=self.header, timeout=15).text
            html = etree.HTML(resp)
            urlList = html.xpath("//div[@class='feed-card']//div[@class='feed-brief-card']/a/@href")
            return [urljoin("https://m.ds.163.com", u) for u in urlList]
        except Exception as e:
            log.logger.warning(f"解析文章列表失败: {e}")
            return []

    def parse(self, article_url):
        try:
            resp = requests.get(article_url, headers=self.header, timeout=15).text
            html = re.findall(r'<article class="ph-ml feed-article__content">(.*?)</article>', resp, re.S)
            title = re.findall(r'<h1 class="feed-article__headline"><div>(.*?)</div></h1>', resp, re.S)
            return title[0] if title else "", html[0] if html else ""
        except Exception as e:
            log.logger.warning(f"{article_url} 解析失败: {e}")
            return "", ""

    def disposeHTML(self, html: str):
        html = html.replace("<p><br></p>", "")
        html = re.sub(r"<p[\S\s]+?</a></p>", "", html)
        return html

    def parseArticle(self, html):
        html = self.disposeHTML(html)
        md = html2text.html2text(html)
        return html, md

    def extract_text_and_images(self, html: str):
        soup = BeautifulSoup(html, "html.parser")
        content = []
        for elem in soup.descendants:
            if elem.name == "p":
                text = elem.get_text(strip=True)
                if text:
                    content.append(("text", text))
            elif elem.name == "img":
                src = elem.get("data-src") or elem.get("data-original") or elem.get("data-echo") or elem.get("src")
                if not src or src.startswith("data:"):
                    continue
                src = src.split("?")[0]
                if src.startswith("//"):
                    src = "https:" + src
                elif src.startswith("/"):
                    src = urljoin("https://m.ds.163.com", src)
                content.append(("img", src))
        return content


# ======================
# 主流程
# ======================
def main():
    log.logger.info("爬取开始ing......")
    spider = SkyTask()

    urls = []
    for _ in range(10):
        urls = spider.getIndex()
        if urls:
            break
        time.sleep(1)

    if not urls:
        log.logger.info("没有获取到文章链接")
        return

    log.logger.info(f"共获取到 {len(urls)} 条链接.")

    # 只处理最新一篇文章
    for url in urls:
        for _ in range(10):
            title, html = spider.parse(url)
            if html:
                break
            time.sleep(1)
        else:
            continue

        html, md = spider.parseArticle(html)
        # 直接处理，不再调用占位数据库函数
        content_list = spider.extract_text_and_images(html)
        send_content_list_grouped(content_list)
        push_to_readme_latest(title, md, html)
        log.logger.info(f"已推送最新文章到 Telegram: {title}")
        break

    log.logger.info("处理完成!")


if __name__ == "__main__":
    main()