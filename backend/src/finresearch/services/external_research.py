from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime

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

    def health(self, *, force: bool = False) -> list[dict[str, object]]:
        rows = []
        for name, connector in self.registry.items():
            row = self._health_for(name, force=force)
            if row is not None:
                rows.append(row)
        return rows

    def search(self, query: str, connectors: list[str] | None = None, limit: int = 10) -> ExternalResearchResult:
        names = connectors or ["direct_web", "rss"]
        warnings: list[str] = []
        items: list[dict[str, object]] = []
        for name in names:
            connector = self.registry.get(name)
            if connector is None:
                warnings.append(f"unknown_connector:{name}")
                continue
            health = self._health_for(name, force=False)
            if health and _should_skip(health):
                warnings.append(f"{name}:skipped:{health.get('status')}:{health.get('last_error') or ''}".rstrip(":"))
                continue
            try:
                found = connector.search(query, limit=limit)
                self.source_repo.upsert_many(found)
                items.extend(asdict(item) for item in found)
                self.status_repo.record_success(name)
            except Exception as exc:
                warnings.append(f"{name}:{exc}")
                self.status_repo.record_failure(name, str(exc))
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

    def status_snapshot(self) -> list[dict[str, object]]:
        return self.status_repo.list()

    def _health_for(self, name: str, *, force: bool = False) -> dict[str, object] | None:
        if not force:
            cached = self.status_repo.get_cached(name)
            if cached is not None:
                return cached
        connector = self.registry.get(name)
        if connector is None:
            return None
        health = connector.health_check()
        payload = asdict(health)
        self.status_repo.save_health(health, enabled=health.enabled)
        saved = self.status_repo.get(name)
        return saved or payload


def _should_skip(health: dict[str, object]) -> bool:
    status = str(health.get("status") or "")
    if status in {"disabled", "missing_dependency", "not_installed", "needs_configuration", "requires_login"}:
        return True
    if status != "circuit_open":
        return False
    retry_after = health.get("retry_after")
    if not retry_after:
        return True
    try:
        parsed = datetime.fromisoformat(str(retry_after))
    except ValueError:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed > datetime.now(UTC)
