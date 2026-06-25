from __future__ import annotations

import requests

from finresearch.connectors.base import ConnectorHealth, ExternalItem
from finresearch.connectors.utils import content_hash, html_to_text, now_iso, title_from_html


class DirectWebConnector:
    name = "direct_web"

    def __init__(self, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds

    def health_check(self) -> ConnectorHealth:
        return ConnectorHealth(name=self.name, status="available", active_backend="requests")

    def search(self, query: str, limit: int = 10) -> list[ExternalItem]:
        if query.startswith(("http://", "https://")):
            return [self.read(query)]
        return []

    def read(self, url: str) -> ExternalItem:
        response = requests.get(
            url,
            timeout=self.timeout_seconds,
            headers={"User-Agent": "finresearch-agent/0.1"},
        )
        response.raise_for_status()
        html = response.text
        text = html_to_text(html)
        fetched_at = now_iso()
        return ExternalItem(
            connector=self.name,
            platform="web",
            title=title_from_html(html),
            url=url,
            fetched_at=fetched_at,
            content=text,
            content_hash=content_hash(text),
            trust_level="unknown",
            metadata={"backend": "requests", "status_code": response.status_code},
        )

