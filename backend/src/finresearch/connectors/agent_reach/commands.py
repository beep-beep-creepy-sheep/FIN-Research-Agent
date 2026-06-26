from __future__ import annotations

import json
from dataclasses import dataclass

from finresearch.connectors.agent_reach.client import AgentReachCommandClient
from finresearch.connectors.agent_reach.normalizers import normalize_exa_stdout, normalize_read_url
from finresearch.connectors.base import ConnectorHealth, ExternalItem


@dataclass(frozen=True)
class AgentReachCapability:
    name: str
    doctor_key: str
    display_name: str
    requires_login: bool = False


CAPABILITIES = [
    AgentReachCapability("agent_reach_twitter", "twitter", "Twitter/X", requires_login=True),
    AgentReachCapability("agent_reach_xueqiu", "xueqiu", "雪球", requires_login=True),
    AgentReachCapability("agent_reach_reddit", "reddit", "Reddit", requires_login=True),
    AgentReachCapability("agent_reach_youtube", "youtube", "YouTube"),
    AgentReachCapability("agent_reach_xiaohongshu", "xiaohongshu", "小红书", requires_login=True),
]


class AgentReachExaConnector:
    name = "agent_reach_exa"

    def __init__(self, *, agent_reach_enabled: bool = False, exa_enabled: bool = False) -> None:
        self.agent_reach_enabled = agent_reach_enabled
        self.exa_enabled = exa_enabled
        self.client = AgentReachCommandClient()

    def health_check(self) -> ConnectorHealth:
        if not self.agent_reach_enabled or not self.exa_enabled:
            return ConnectorHealth(
                name=self.name,
                status="disabled",
                enabled=False,
                configured=False,
                available=False,
            )
        if not self.client.has_command("mcporter"):
            return ConnectorHealth(
                name=self.name,
                status="not_installed",
                enabled=True,
                configured=False,
                available=False,
                last_error="mcporter is not installed",
            )
        result = self.client.exa_search("finresearch connector health", limit=1, timeout_seconds=5)
        if result.ok:
            return ConnectorHealth(
                name=self.name,
                status="available",
                enabled=True,
                configured=True,
                available=True,
                active_backend="mcporter/exa",
            )
        status = "needs_configuration" if _looks_unconfigured(result.stderr or result.stdout) else "unavailable"
        return ConnectorHealth(
            name=self.name,
            status=status,
            enabled=True,
            configured=False,
            available=False,
            active_backend="mcporter",
            last_error=(result.stderr or result.stdout).strip() or "exa health check failed",
        )

    def search(self, query: str, limit: int = 10) -> list[ExternalItem]:
        if not self.agent_reach_enabled or not self.exa_enabled:
            return []
        result = self.client.exa_search(query, limit=limit, timeout_seconds=15)
        if not result.ok:
            raise RuntimeError((result.stderr or result.stdout).strip() or "exa search failed")
        return normalize_exa_stdout(result.stdout, query)

    def read(self, url: str) -> ExternalItem:
        if not self.agent_reach_enabled:
            raise RuntimeError("agent_reach_disabled")
        result = self.client.read_url(url)
        if not result.ok:
            raise RuntimeError(result.stderr)
        return normalize_read_url(url, result.stdout)


class AgentReachPlatformConnector:
    def __init__(self, capability: AgentReachCapability, *, enabled: bool = False) -> None:
        self.capability = capability
        self.name = capability.name
        self.enabled = enabled
        self.client = AgentReachCommandClient()

    def health_check(self) -> ConnectorHealth:
        if not self.enabled:
            return ConnectorHealth(
                name=self.name,
                status="disabled",
                enabled=False,
                configured=False,
                available=False,
                requires_login=self.capability.requires_login,
            )
        if not self.client.has_command("agent-reach"):
            return ConnectorHealth(
                name=self.name,
                status="not_installed",
                enabled=True,
                configured=False,
                available=False,
                requires_login=self.capability.requires_login,
                last_error="agent-reach is not installed",
            )
        result = self.client.doctor(timeout_seconds=5)
        if not result.ok:
            return ConnectorHealth(
                name=self.name,
                status="unavailable",
                enabled=True,
                configured=False,
                available=False,
                requires_login=self.capability.requires_login,
                last_error=result.stderr or "agent-reach doctor failed",
            )
        payload = _parse_doctor(result.stdout)
        row = payload.get(self.capability.doctor_key) if isinstance(payload, dict) else None
        if not isinstance(row, dict):
            return ConnectorHealth(
                name=self.name,
                status="needs_configuration",
                enabled=True,
                configured=False,
                available=False,
                requires_login=self.capability.requires_login,
                last_error=f"{self.capability.doctor_key} not reported by agent-reach doctor",
            )
        active_backend = row.get("active_backend")
        doctor_status = str(row.get("status") or "")
        configured = bool(active_backend)
        if doctor_status in {"ok", "warn"} and configured:
            status = "available"
        elif self.capability.requires_login:
            status = "requires_login"
        else:
            status = "needs_configuration"
        return ConnectorHealth(
            name=self.name,
            status=status,
            enabled=True,
            configured=configured,
            available=status == "available",
            active_backend=str(active_backend) if active_backend else None,
            requires_login=self.capability.requires_login and status != "available",
            last_error=None if status == "available" else str(row.get("message") or ""),
        )

    def search(self, query: str, limit: int = 10) -> list[ExternalItem]:
        return []

    def read(self, url: str) -> ExternalItem:
        result = self.client.read_url(url)
        if not result.ok:
            raise RuntimeError(result.stderr)
        return normalize_read_url(url, result.stdout)


def _parse_doctor(stdout: str) -> object | None:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None


def _looks_unconfigured(text: str) -> bool:
    lowered = text.lower()
    markers = [
        "not installed",
        "not configured",
        "no server",
        "unknown tool",
        "could not find",
        "exa",
        "config",
    ]
    return any(marker in lowered for marker in markers)
