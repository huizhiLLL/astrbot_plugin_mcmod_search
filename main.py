"""AstrBot MCMod 搜索与详情工具插件。"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Literal
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup
from astrbot.api import llm_tool, logger
from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Star, register

PLUGIN_NAME = "astrbot_plugin_mcmod_search"
SearchType = Literal["mod", "modpack", "item", "post", "all"]
Operation = Literal["search", "detail"]


@register(
    PLUGIN_NAME,
    "小枝",
    "直接查询 MCMod 的模组、整合包、物品和教程信息",
    "0.2.0",
)
class MCModSearchPlugin(Star):
    """只提供给 LLM 调用的 MCMod 搜索与详情工具。"""

    SEARCH_TYPES: dict[str, str] = {
        "mod": "模组", "modpack": "整合包", "item": "物品", "post": "教程"
    }
    TYPE_PATTERNS: dict[str, str] = {
        "mod": "/class/", "modpack": "/modpack/", "item": "/item/", "post": "/post/"
    }
    BASE_URL = "https://search.mcmod.cn/s"
    SITE_ORIGIN = "https://www.mcmod.cn"
    USER_AGENT = "AstrBot-MCModSearch/0.2 (+https://github.com/huizhiLLL/astrbot_plugin_mcmod_search)"
    MAX_QUERY_LENGTH = 100
    MAX_PAGE = 20
    MAX_RESULTS_PER_TYPE = 20
    MAX_DETAIL_TEXT = 4000

    @llm_tool(name="mcmod_search")
    async def mcmod_search(
        self,
        event: AstrMessageEvent,
        operation: Operation = "search",
        query: str = "",
        search_type: SearchType = "all",
        page: int = 1,
        url: str = "",
    ) -> str:
        """搜索 MCMod，或读取一个 MCMod 页面详情并返回结构化 JSON。

        operation=search：根据用户问题传入 query 和类型。mod 是模组，modpack
        是整合包，item 是物品，post 是教程，all 是综合搜索；page 范围为 1 到 20。
        operation=detail：传入 MCMod 站内 url，读取标题、简介、作者、支持版本、
        更新日志和正文摘要，不需要 query。用户询问具体 MCMod 页面详情时使用它。
        普通 Minecraft 知识问答不要调用此工具。
        """
        if operation not in ("search", "detail"):
            return self._error("operation 必须是 search 或 detail")
        try:
            if operation == "detail":
                normalized_url = self._normalize_mcmod_url(url)
                if not normalized_url:
                    return self._error("detail 操作需要有效的 MCMod 站内 url")
                html = await self._fetch_page(normalized_url)
                detail = self._parse_detail(html, normalized_url)
                return self._json({"ok": True, "source": "mcmod.cn", "detail": detail})

            normalized_query = self._normalize_query(query)
            if not normalized_query:
                return self._error("search 操作需要 query")
            if len(normalized_query) > self.MAX_QUERY_LENGTH:
                return self._error(f"query 过长，最多 {self.MAX_QUERY_LENGTH} 个字符")
            if search_type not in (*self.SEARCH_TYPES, "all"):
                return self._error("search_type 必须是 mod、modpack、item、post 或 all")
            if not isinstance(page, int) or isinstance(page, bool) or not 1 <= page <= self.MAX_PAGE:
                return self._error(f"page 必须是 1 到 {self.MAX_PAGE} 的整数")
            html = await self._fetch_search_page(normalized_query, page)
            results = self._parse_results(html, search_type)
            return self._json({
                "ok": True, "source": "mcmod.cn", "query": normalized_query,
                "search_type": search_type, "page": page,
                "result_count": sum(len(items) for items in results.values()),
                "results": results,
            })
        except asyncio.TimeoutError as exc:
            logger.warning("MCMod 请求超时: %s", exc)
            return self._error("MCMod 搜索超时，请稍后再试")
        except aiohttp.ClientError as exc:
            logger.warning("MCMod 请求失败: %s", exc)
            return self._error("MCMod 暂时无法访问，请稍后再试")
        except Exception:
            logger.exception("MCMod 搜索或详情解析失败")
            return self._error("MCMod 页面解析失败")

    async def _fetch_search_page(self, query: str, page: int) -> str:
        return await self._fetch_page(self.BASE_URL, {"key": query, "filter": 0, "page": page})

    async def _fetch_page(self, url: str, params: dict[str, Any] | None = None) -> str:
        timeout = aiohttp.ClientTimeout(total=15, connect=5, sock_read=10)
        headers = {
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "zh-CN,zh;q=0.9", "User-Agent": self.USER_AGENT,
        }
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                return await response.text()

    def _parse_results(self, html: str, search_type: str) -> dict[str, list[dict[str, str]]]:
        soup = BeautifulSoup(html, "html.parser")
        results = {kind: [] for kind in self.SEARCH_TYPES}
        seen_urls: set[str] = set()
        containers = soup.select(".search-result") or [soup]
        for container in containers:
            for link in container.select("a[href]"):
                parsed = self._classify_link(link.get("href", ""))
                if not parsed:
                    continue
                kind, item_url = parsed
                if search_type != "all" and kind != search_type:
                    continue
                if item_url in seen_urls or len(results[kind]) >= self.MAX_RESULTS_PER_TYPE:
                    continue
                name = " ".join(link.get_text(" ", strip=True).split())
                if name:
                    seen_urls.add(item_url)
                    results[kind].append({"name": name, "url": item_url})
        return {search_type: results[search_type]} if search_type != "all" else results

    def _parse_detail(self, html: str, url: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        title = re.sub(r"\s*[-|｜].*MC百科.*$", "", title).strip()
        description_tag = soup.find("meta", attrs={"name": "description"})
        description = description_tag.get("content", "").strip() if description_tag else ""
        path = urlparse(url).path
        page_type = next((kind for kind, pattern in self.TYPE_PATTERNS.items() if pattern in path), "unknown")
        versions = sorted({a.get_text(" ", strip=True) for a in soup.select('a[href*="mcver="]') if a.get_text(strip=True)})
        authors: list[str] = []
        for link in soup.select('a[href*="/author/"]'):
            name = link.get_text(" ", strip=True)
            if name and name not in authors:
                authors.append(name)
        changelog: list[str] = []
        for link in soup.select('a[href*="/class/version/"]')[:20]:
            name = link.get_text(" ", strip=True)
            if name and name not in changelog:
                changelog.append(name)
        text_root = soup.find("main") or soup.body or soup
        for node in text_root.select("script, style, nav, header, footer"):
            node.decompose()
        content = " ".join(text_root.get_text(" ", strip=True).split())
        return {
            "url": url, "type": page_type, "title": title, "description": description,
            "supported_versions": versions[:100], "authors": authors[:50],
            "changelog_entries": changelog, "content_excerpt": content[:self.MAX_DETAIL_TEXT],
        }

    def _classify_link(self, href: str) -> tuple[str, str] | None:
        if not href:
            return None
        url = urljoin(self.SITE_ORIGIN, href)
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if hostname != "mcmod.cn" and not hostname.endswith(".mcmod.cn"):
            return None
        if "/class/category/" in parsed.path:
            return None
        for kind, pattern in self.TYPE_PATTERNS.items():
            if pattern in parsed.path:
                return kind, url
        return None

    def _normalize_mcmod_url(self, value: Any) -> str | None:
        if not isinstance(value, str) or len(value) > 500:
            return None
        url = urljoin(self.SITE_ORIGIN, value.strip())
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or (hostname != "mcmod.cn" and not hostname.endswith(".mcmod.cn")):
            return None
        if not parsed.path.startswith(("/class/", "/modpack/", "/item/", "/post/")):
            return None
        return url

    @staticmethod
    def _normalize_query(query: Any) -> str:
        return re.sub(r"\s+", " ", query).strip() if isinstance(query, str) else ""

    @staticmethod
    def _json(data: dict[str, Any]) -> str:
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def _error(cls, message: str) -> str:
        return cls._json({"ok": False, "error": message})
