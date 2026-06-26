from __future__ import annotations

from finresearch.connectors.agent_reach.commands import (
    CAPABILITIES,
    AgentReachExaConnector,
    AgentReachPlatformConnector,
)
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
        AgentReachExaConnector(
            agent_reach_enabled=agent_reach_enabled,
            exa_enabled=getattr(settings, "exa_enabled", False),
        ),
        *[
            AgentReachPlatformConnector(capability, enabled=agent_reach_enabled)
            for capability in CAPABILITIES
        ],
    ]
    return {connector.name: connector for connector in connectors}
