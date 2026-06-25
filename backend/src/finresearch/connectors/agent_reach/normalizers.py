from __future__ import annotations

import json

from finresearch.connectors.base import ExternalItem
from finresearch.connectors.utils import content_hash, now_iso


def normalize_exa_stdout(stdout: str, query: str) -> list[ExternalItem]:
    parsed = _try_json(stdout)
    fetched_at = now_iso()
    items: list[ExternalItem] = []
    candidates = []
    if isinstance(parsed, dict):
        for key in ("results", "data", "items"):
            value = parsed.get(key)
            if isinstance(value, list):
                candidates = value
                break
    elif isinstance(parsed, list):
        candidates = parsed

    if not candidates:
        text = stdout.strip()
        if text:
            return [
                ExternalItem(
                    connector="agent_reach",
                    platform="exa",
                    title=f"Agent Reach search: {query}",
                    url=f"agent-reach://exa/{content_hash(query)[:12]}",
                    fetched_at=fetched_at,
                    content=text,
                    content_hash=content_hash(text),
                    trust_level="unknown",
                    metadata={"query": query, "raw": True},
                )
            ]
        return []

    for item in candidates:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or item.get("link") or "")
        content = str(item.get("text") or item.get("summary") or item.get("content") or "")
        title = item.get("title")
        if not url:
            url = f"agent-reach://exa/{content_hash(json.dumps(item, ensure_ascii=False))[:12]}"
        items.append(
            ExternalItem(
                connector="agent_reach",
                platform="exa",
                title=str(title) if title else None,
                url=url,
                fetched_at=fetched_at,
                content=content,
                content_hash=content_hash(f"{url}\n{content}"),
                trust_level="unknown",
                metadata={"query": query, "raw_item": item},
            )
        )
    return items


def normalize_read_url(url: str, content: str) -> ExternalItem:
    return ExternalItem(
        connector="agent_reach",
        platform="web",
        url=url,
        fetched_at=now_iso(),
        content=content,
        content_hash=content_hash(content),
        trust_level="unknown",
        metadata={"backend": "jina-reader"},
    )


def _try_json(text: str) -> object | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None

