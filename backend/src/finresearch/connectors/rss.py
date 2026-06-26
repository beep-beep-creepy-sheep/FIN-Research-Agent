from __future__ import annotations

import xml.etree.ElementTree as ET

import requests

from finresearch.connectors.base import ConnectorHealth, ExternalItem
from finresearch.connectors.utils import content_hash, html_to_text, now_iso


class RSSConnector:
    name = "rss"

    def __init__(self, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds

    def health_check(self) -> ConnectorHealth:
        return ConnectorHealth(
            name=self.name,
            status="available",
            enabled=True,
            configured=True,
            available=True,
            active_backend="stdlib-xml",
        )

    def search(self, query: str, limit: int = 10) -> list[ExternalItem]:
        if query.startswith(("http://", "https://")):
            return self.read_feed(query, limit=limit)
        return []

    def read(self, url: str) -> ExternalItem:
        items = self.read_feed(url, limit=1)
        if not items:
            raise ValueError("rss_feed_empty")
        return items[0]

    def read_feed(self, feed_url: str, limit: int = 10) -> list[ExternalItem]:
        response = requests.get(
            feed_url,
            timeout=self.timeout_seconds,
            headers={"User-Agent": "finresearch-agent/0.1"},
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)
        fetched_at = now_iso()
        items: list[ExternalItem] = []
        for node in root.findall(".//item")[:limit] or root.findall(".//{*}entry")[:limit]:
            title = _child_text(node, "title")
            link = _child_text(node, "link") or _link_href(node) or feed_url
            published = _child_text(node, "pubDate") or _child_text(node, "published")
            content = _child_text(node, "description") or _child_text(node, "summary") or title or ""
            text = html_to_text(content)
            items.append(
                ExternalItem(
                    connector=self.name,
                    platform="rss",
                    title=title,
                    url=link,
                    published_at=published,
                    fetched_at=fetched_at,
                    content=text,
                    content_hash=content_hash(f"{link}\n{text}"),
                    trust_level="secondary",
                    metadata={"feed_url": feed_url},
                )
            )
        return items


def _child_text(node: ET.Element, tag: str) -> str | None:
    found = node.find(tag) or node.find(f"{{*}}{tag}")
    if found is None or found.text is None:
        return None
    return found.text.strip()


def _link_href(node: ET.Element) -> str | None:
    for child in node:
        if child.tag.endswith("link") and child.attrib.get("href"):
            return child.attrib["href"]
    return None
