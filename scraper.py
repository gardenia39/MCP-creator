"""网站内容抓取模块 — BFS 爬取同域页面，提取纯文本"""

import asyncio
from collections import deque
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


async def scrape_site(base_url: str, max_pages: int = 20) -> list[dict]:
    """BFS 抓取同域页面，返回 [{"url", "title", "content"}]"""
    parsed_base = urlparse(base_url)
    domain = parsed_base.netloc
    seen: set[str] = {base_url}
    queue: deque = deque([base_url])
    results: list[dict] = []

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        while queue and len(results) < max_pages:
            url = queue.popleft()

            try:
                resp = await client.get(url)
                if "text/html" not in resp.headers.get("content-type", ""):
                    continue
            except Exception:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            # 去掉脚本和样式
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()

            title = soup.title.string.strip() if soup.title and soup.title.string else url
            text = soup.get_text(separator="\n", strip=True)

            results.append({"url": url, "title": title, "content": text})

            # 提取同域链接
            for a in soup.find_all("a", href=True):
                href = urljoin(url, a["href"])
                parsed = urlparse(href)
                if parsed.netloc == domain:
                    clean = href.split("#")[0].split("?")[0]  # 去掉锚点和参数
                    if clean not in seen:
                        seen.add(clean)
                        queue.append(clean)

    return results


def scrape_site_sync(base_url: str, max_pages: int = 20) -> list[dict]:
    """同步包装，供非 async 环境调用"""
    return asyncio.run(scrape_site(base_url, max_pages))
