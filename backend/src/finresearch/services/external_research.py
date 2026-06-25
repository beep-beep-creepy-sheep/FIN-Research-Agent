from __future__ import annotations

from dataclasses import asdict, dataclass

from finresearch.connectors.registry import connector_registry
from finresearch.repositories.connector_status import ConnectorStatusRepository
from finresearch.repositories.external_sources import ExternalSourceRepository


@dataclass(frozen=True)
class ExternalResearchResult:
    query: str
    connectors: list[str]
    items: list[dict[str, object]]
    warnings: list[str]


class ExternalResearchService:
    def __init__(self) -> None:
        self.registry = connector_registry()
        self.source_repo = ExternalSourceRepository()
        self.status_repo = ConnectorStatusRepository()

    def health(self) -> list[dict[str, object]]:
        rows = []
        for name, connector in self.registry.items():
            health = connector.health_check()
            self.status_repo.save_health(health, enabled=health.status != "disabled")
            rows.append(asdict(health))
        return rows

    def search(self, query: str, connectors: list[str] | None = None, limit: int = 10) -> ExternalResearchResult:
        names = connectors or ["direct_web", "rss"]
        warnings: list[str] = []
        items = []
        for name in names:
            connector = self.registry.get(name)
            if connector is None:
                warnings.append(f"unknown_connector:{name}")
                continue
            try:
                found = connector.search(query, limit=limit)
                self.source_repo.upsert_many(found)
                items.extend(asdict(item) for item in found)
            except Exception as exc:
                warnings.append(f"{name}:{exc}")
        return ExternalResearchResult(query=query, connectors=names, items=items, warnings=warnings)

    def read_url(self, url: str, connector_name: str = "direct_web") -> dict[str, object]:
        connector = self.registry.get(connector_name)
        if connector is None:
            raise ValueError(f"unknown_connector:{connector_name}")
        item = connector.read(url)
        source_id = self.source_repo.upsert(item)
        payload = asdict(item)
        payload["id"] = source_id
        return payload

    def list_sources(self, limit: int = 50, platform: str | None = None) -> list[dict[str, object]]:
        return self.source_repo.list(limit=limit, platform=platform)
