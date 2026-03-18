"""MCP Server — 将抓取的网站内容或本地文件暴露为 Resource 和 Tool"""

import sys
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

from mcp.server.fastmcp import FastMCP, Context

from scraper import scrape_site_sync, read_local_folder_sync

@dataclass
class SiteData:
    pages: list[dict] = field(default_factory=list)


def create_server(
    source_path: str,
    source_type: str = "url",
    site_name: str = "MySite",
    max_pages: int = 20,
    transport: str = "stdio",
    css_selector: str = "",
) -> FastMCP:
    """根据配置创建 MCP Server 实例"""

    kwargs = {}
    if transport == "streamable-http":
        kwargs.update(stateless_http=True, json_response=True)

    print(f"[MCP] 正在加载数据来源: {source_path} (类型: {source_type})...", file=sys.stderr)
    
    if source_type == "url":
        pages = scrape_site_sync(source_path, max_pages, css_selector)
    else:
        pages = read_local_folder_sync(source_path, max_pages)

    print(f"[MCP] 数据加载完成，共 {len(pages)} 条记录", file=sys.stderr)
    
    # 保存到缓存文件供 UI 的“测试框”读取
    cache_file = Path(__file__).parent / "mcp_cache.json"
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False)
        
    global_site_data = SiteData(pages=pages)

    @asynccontextmanager
    async def lifespan(server: FastMCP):
        yield global_site_data

    mcp = FastMCP(site_name, lifespan=lifespan, **kwargs)

    # --- Resources ---

    @mcp.resource("site://pages")
    def list_pages(ctx: Context = None) -> str:
        """返回所有页面列表"""
        data: SiteData = ctx.request_context.lifespan_context if ctx else SiteData()
        lines = [f"{i}. [{p['title']}]({p['url']})" for i, p in enumerate(data.pages)]
        return "\n".join(lines) or "没有找到任何页面或文件"

    @mcp.resource("site://page/{index}")
    def get_page(index: int, ctx: Context = None) -> str:
        """按索引返回单页内容"""
        data: SiteData = ctx.request_context.lifespan_context if ctx else SiteData()
        if 0 <= index < len(data.pages):
            p = data.pages[index]
            return f"# {p['title']}\n\n来源: {p['url']}\n\n{p['content']}"
        return "内容不存在"

    # --- Tools ---

    @mcp.tool()
    def search_content(query: str, ctx: Context = None) -> str:
        """在抓取的站点或文件中搜索关键词，返回匹配片段"""
        data: SiteData = ctx.request_context.lifespan_context if ctx else SiteData()
        results = []
        for p in data.pages:
            if query.lower() in p["content"].lower():
                idx = p["content"].lower().index(query.lower())
                start = max(0, idx - 100)
                end = min(len(p["content"]), idx + len(query) + 100)
                snippet = p["content"][start:end]
                results.append(f"**{p['title']}** ({p['url']})\n...{snippet}...")
        return "\n\n---\n\n".join(results) if results else "未找到匹配内容"

    @mcp.tool()
    def get_recommendation(user_preference: str, ctx: Context = None) -> str:
        """根据用户偏好相关度推荐内容"""
        data: SiteData = ctx.request_context.lifespan_context if ctx else SiteData()
        keywords = user_preference.lower().split()
        scored = []
        for p in data.pages:
            content_lower = p["content"].lower()
            score = sum(content_lower.count(kw) for kw in keywords)
            if score > 0:
                scored.append((score, p))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:5]  # 最多推荐5个

        if not top:
            return "没有找到与您偏好相关的内容"

        lines = []
        for score, p in top:
            preview = p["content"][:200]
            lines.append(f"**{p['title']}** (相关度: {score})\n{p['url']}\n{preview}...")
        return "\n\n---\n\n".join(lines)

    return mcp


def run_server(
    source_path: str,
    source_type: str = "url",
    site_name: str = "MySite",
    max_pages: int = 20,
    transport: str = "stdio",
    css_selector: str = "",
    host: str = "0.0.0.0",
    port: int = 8000,
):
    """创建并运行 MCP Server"""
    mcp = create_server(source_path, source_type, site_name, max_pages, transport, css_selector)
    if transport == "streamable-http":
        mcp.settings.host = host
        mcp.settings.port = port
    mcp.run(transport=transport)


if __name__ == "__main__":
    import os
    source = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    mode = sys.argv[2] if len(sys.argv) > 2 else "stdio"
    
    stype = os.environ.get("MCP_SOURCE_TYPE", "url")
    name = os.environ.get("MCP_SITE_NAME", "MySite")
    pages = int(os.environ.get("MCP_MAX_PAGES", "20"))
    css_sel = os.environ.get("MCP_CSS_SELECTOR", "")
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "8000"))
    
    run_server(source, source_type=stype, site_name=name, max_pages=pages,
               transport=mode, css_selector=css_sel, host=host, port=port)
