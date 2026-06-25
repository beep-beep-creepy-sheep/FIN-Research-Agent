from __future__ import annotations

from finresearch.connectors.agent_reach.client import AgentReachCommandClient
from finresearch.connectors.agent_reach.normalizers import normalize_exa_stdout, normalize_read_url
from finresearch.connectors.base import ConnectorHealth, ExternalItem


class AgentReachConnector:
    name = "agent_reach"

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self.client = AgentReachCommandClient()

    def health_check(self) -> ConnectorHealth:
        if not self.enabled:
            return ConnectorHealth(name=self.name, status="disabled", active_backend=None)
        result = self.client.doctor()
        if result.ok:
            return ConnectorHealth(name=self.name, status="available", active_backend="agent-reach")
        status = "needs_configuration" if "not installed" in result.stderr else "unavailable"
        return ConnectorHealth(name=self.name, status=status, last_error=result.stderr)

    def search(self, query: str, limit: int = 10) -> list[ExternalItem]:
        if not self.enabled:
            return []
        result = self.client.exa_search(query, limit=limit)
        if not result.ok:
            raise RuntimeError(result.stderr)
        return normalize_exa_stdout(result.stdout, query)

    def read(self, url: str) -> ExternalItem:
        if not self.enabled:
            raise RuntimeError("agent_reach_disabled")
        result = self.client.read_url(url)
        if not result.ok:
            raise RuntimeError(result.stderr)
        return normalize_read_url(url, result.stdout)

