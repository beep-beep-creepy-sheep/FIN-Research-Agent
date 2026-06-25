from __future__ import annotations

from finresearch.connectors.agent_reach.commands import AgentReachConnector
from finresearch.connectors.base import InternetConnector
from finresearch.connectors.direct_web import DirectWebConnector
from finresearch.connectors.rss import RSSConnector
from finresearch.settings import get_settings


def connector_registry() -> dict[str, InternetConnector]:
    settings = get_settings()
    agent_reach_enabled = getattr(settings, "agent_reach_enabled", False)
    connectors: list[InternetConnector] = [
        DirectWebConnector(),
        RSSConnector(),
        AgentReachConnector(enabled=agent_reach_enabled),
    ]
    return {connector.name: connector for connector in connectors}

