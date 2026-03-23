"""网站内容抓取与本地文件读取模块"""
import asyncio
import os
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


async def scrape_site(base_url: str, max_pages: int = 20, css_selector: str = "") -> list[dict]:
    """并发 BFS 抓取同域页面"""
    parsed_base = urlparse(base_url)
    domain = parsed_base.netloc
    seen: set[str] = {base_url}
    queue: deque = deque([base_url])
    results: list[dict] = []

    # 限制并发量
    semaphore = asyncio.Semaphore(10)

    async def fetch_and_parse(client, url):
        async with semaphore:
            try:
                resp = await client.get(url)
                if "text/html" not in resp.headers.get("content-type", ""):
                    return None, []
            except Exception:
                return None, []

            soup = BeautifulSoup(resp.text, "html.parser")

            # 去掉脚本和样式
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()

            title = soup.title.string.strip() if soup.title and soup.title.string else url
            
            # 使用 CSS 过滤器
            if css_selector:
                elements = soup.select(css_selector)
                text = "\n".join(el.get_text(separator="\n", strip=True) for el in elements)
                if not text:
                    text = soup.get_text(separator="\n", strip=True)
            else:
                text = soup.get_text(separator="\n", strip=True)

            res_dict = {"url": url, "title": title, "content": text}
            
            new_links = []
            for a in soup.find_all("a", href=True):
                href = urljoin(url, a["href"])
                parsed = urlparse(href)
                if parsed.netloc == domain:
                    clean = href.split("#")[0].split("?")[0]  
                    new_links.append(clean)
                    
            return res_dict, new_links

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        while queue and len(results) < max_pages:
            # 每次取出最多 10 个 URL
            batch_urls = []
            while queue and len(batch_urls) < 10:
                batch_urls.append(queue.popleft())
            
            tasks = [fetch_and_parse(client, u) for u in batch_urls]
            batch_results = await asyncio.gather(*tasks)
            
            for res, new_links in batch_results:
                if res and len(results) < max_pages:
                    results.append(res)
                
                for nl in new_links:
                    if nl not in seen:
                        seen.add(nl)
                        queue.append(nl)

    return results


def scrape_site_sync(base_url: str, max_pages: int = 20, css_selector: str = "") -> list[dict]:
    """同步包装"""
    return asyncio.run(scrape_site(base_url, max_pages, css_selector))


async def read_local_folder(folder_path: str, max_files: int = 100) -> list[dict]:
    """读取本地文件夹内的纯文本文件"""
    results: list[dict] = []
    allowed_exts = {".txt", ".md", ".json", ".csv", ".py", ".js", ".html", ".css"}
    
    path = Path(folder_path)
    if not path.exists() or not path.is_dir():
        return results

    # 递归遍历文件
    count = 0
    for file_path in path.rglob("*"):
        if count >= max_files:
            break
        if file_path.is_file() and file_path.suffix.lower() in allowed_exts:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                results.append({
                    "url": f"file://{file_path.absolute()}",
                    "title": file_path.name,
                    "content": content
                })
                count += 1
            except Exception:
                pass
                
    return results

def read_local_folder_sync(folder_path: str, max_files: int = 100) -> list[dict]:
    return asyncio.run(read_local_folder(folder_path, max_files))
