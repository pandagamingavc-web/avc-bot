from __future__ import annotations

import logging
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional, List

import aiohttp

log = logging.getLogger(__name__)


@dataclass
class NewsPost:
    title: str
    url: str
    source: str


class NewsWatcher:

    def __init__(self) -> None:
        self.feeds: List[str] = [x.strip() for x in os.getenv("NEWS_FEEDS", "").split(",") if x.strip()]
        self.keywords: List[str] = [x.strip().lower() for x in os.getenv("NEWS_KEYWORDS", "").split(",") if x.strip()]
        self._last_link: Optional[str] = None

    def enabled(self) -> bool:
        return bool(self.feeds)

    async def poll(self, session: aiohttp.ClientSession) -> Optional[NewsPost]:
        if not self.feeds:
            return None

        for feed_url in self.feeds[:10]:
            try:
                async with session.get(feed_url, timeout=aiohttp.ClientTimeout(total=20)) as r:
                    if r.status != 200:
                        continue
                    xml = await r.text()

                post = self._parse_first_item(xml, feed_url)
                if not post:
                    continue

                if not self._match_keywords(post.title):
                    continue

                if self._last_link is None:
                    self._last_link = post.url
                    return None

                if post.url == self._last_link:
                    continue

                self._last_link = post.url

                post.title = self._format_title(post.title)

                return post

            except Exception:
                log.exception("[News] Failed feed: %s", feed_url)

        return None

    def _match_keywords(self, title: str) -> bool:
        if not self.keywords:
            return True
        title_l = title.lower()
        return any(k in title_l for k in self.keywords)

    def _format_title(self, title: str) -> str:
        t = title.lower()

        emoji = "📰"

        if "cs2" in t or "counter" in t:
            emoji = "💣"
        elif "dota" in t:
            emoji = "🧙"
        elif "warface" in t:
            emoji = "🔫"
        elif "call of duty" in t or "cod" in t:
            emoji = "🎖"
        elif "patch" in t or "update" in t:
            emoji = "🛠"
        elif "tournament" in t or "major" in t or "esport" in t or "кибер" in t:
            emoji = "🏆"
        elif "announce" in t or "анонс" in t:
            emoji = "📢"

        return f"{emoji} {title}"

    def _parse_first_item(self, xml: str, source_url: str) -> Optional[NewsPost]:
        root = ET.fromstring(xml)

        channel = root.find("channel")
        if channel is not None:
            item = channel.find("item")
            if item is None:
                return None
            title = (item.findtext("title") or "News").strip()
            link = (item.findtext("link") or "").strip()
            if not link:
                return None
            return NewsPost(title=title, url=link, source=source_url)

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entry = root.find("atom:entry", ns)
        if entry is None:
            return None
        title = (entry.findtext("atom:title", default="News", namespaces=ns) or "News").strip()
        link_el = entry.find("atom:link", ns)
        href = link_el.attrib.get("href") if link_el is not None else ""
        if not href:
            return None
        return NewsPost(title=title, url=href, source=source_url)
