"""AstrBot MCMod 搜索工具插件。"""

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
from astrbot.api.star import Context, Star, register

PLUGIN_NAME = "astrbot_plugin_mcmod_search"
SearchType = Literal["mod", "modpack", "item", "post", "all"]


@register(
    PLUGIN_NAME,
    "小枝",
    "直接查询 MCMod 的模组、整合包、物品和教程信息",
    "0.1.0",
)
class MCModSearchPlugin(Star):
    """只提供给 LLM 调用的 MCMod 搜索工具。"""

    SEARCH_TYPES: dict[str, str] = {
        "mod": "模组",
        "modpack": "整合包",
        "item": "物品",
        "post": "教程",
    }
    TYPE_PATTERNS: dict[str, str] = {
        "mod": "/class/",
        "modpack": "/modpack/",
        "item": "/item/",
        "post": "/post/",
    }
    BASE_URL = "https://search.mcmod.cn/s"
    SITE_ORIGIN = "https://www.mcmod.cn"
    USER_AGENT = "AstrBot-MCModSearch/0.1 (+https://github.com/huizhiLLL/astrbot_plugin_mcmod_search)"
    MAX_QUERY_LENGTH = 100
    MAX_PAGE = 20
    MAX_RESULTS_PER_TYPE = 20

    @llm_tool(name="mcmod_search")
    async def mcmod_search(
        self,
        event: AstrMessageEvent,
        query: str,
        search_type: SearchType = "all",
        page: int = 1,
    ) -> str:
        """查询 MCMod 网站上的 Minecraft 内容并返回结构化结果。

        当用户询问具体 Minecraft 模组、整合包、物品、教程，或希望查询
        MCMod 页面、版本、作者、链接时调用。根据用户问题传入类型：
        mod=模组，modpack=整合包，item=物品，post=教程，all=无法确定或综合查询。
        query 只填写搜索关键词；page 用于翻页，范围为 1 到 20。
        普通 Minecraft 知识问答、无需查询 MCMod 的问题不要调用此工具。
        """
        normalized_query = self._normalize_query(query)
        if not normalized_query:
            return self._error("query 不能为空")
        if len(normalized_query) > self.MAX_QUERY_LENGTH:
            return self._error(f"query 过长，最多 {self.MAX_QUERY_LENGTH} 个字符")

        if search_type not in (*self.SEARCH_TYPES, "all"):
            return self._error("search_type 必须是 mod、modpack、item、post 或 all")
        if not isinstance(page, int) or isinstance(page, bool) or not 1 <= page <= self.MAX_PAGE:
            return self._error(f"page 必须是 1 到 {self.MAX_PAGE} 的整数")

        try:
            html = await self._fetch_search_page(normalized_query, page)
            results = self._parse_results(html, search_type)
            return json.dumps(
                {
                    "ok": True,
                    "source": "mcmod.cn",
                    "query": normalized_query,
                    "search_type": search_type,
                    "page": page,
                    "result_count": sum(len(items) for items in results.values()),
                    "results": results,
                },
                ensure_ascii=False,
            )
        except asyncio.TimeoutError as exc:
            logger.warning("MCMod 搜索超时: %s", exc)
            return self._error("MCMod 搜索超时，请稍后再试")
        except aiohttp.ClientError as exc:
            logger.warning("MCMod 请求失败: %s", exc)
            return self._error("MCMod 暂时无法访问，请稍后再试")
        except Exception:
            logger.exception("MCMod 搜索解析失败")
            return self._error("MCMod 搜索结果解析失败")

    async def _fetch_search_page(self, query: str, page: int) -> str:
        timeout = aiohttp.ClientTimeout(total=15, connect=5, sock_read=10)
        headers = {
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "User-Agent": self.USER_AGENT,
        }
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(
                self.BASE_URL,
                params={"key": query, "filter": 0, "page": page},
            ) as response:
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
                kind, url = parsed
                if search_type != "all" and kind != search_type:
                    continue
                if url in seen_urls or len(results[kind]) >= self.MAX_RESULTS_PER_TYPE:
                    continue
                name = " ".join(link.get_text(" ", strip=True).split())
                if not name:
                    continue
                seen_urls.add(url)
                results[kind].append({"name": name, "url": url})

        if search_type != "all":
            return {search_type: results[search_type]}
        return results

    def _classify_link(self, href: str) -> tuple[str, str] | None:
        if not href:
            return None
        url = urljoin(self.SITE_ORIGIN, href)
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if hostname != "mcmod.cn" and not hostname.endswith(".mcmod.cn"):
            return None
        path = parsed.path
        if "/class/category/" in path:
            return None
        for kind, pattern in self.TYPE_PATTERNS.items():
            if pattern in path:
                return kind, url
        return None

    @staticmethod
    def _normalize_query(query: Any) -> str:
        if not isinstance(query, str):
            return ""
        return re.sub(r"\s+", " ", query).strip()

    @staticmethod
    def _error(message: str) -> str:
        return json.dumps({"ok": False, "error": message}, ensure_ascii=False)

