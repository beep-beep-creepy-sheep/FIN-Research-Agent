from __future__ import annotations

from finresearch.connectors.base import ConnectorHealth
from finresearch.connectors.registry import connector_registry


def check_all_connectors() -> list[ConnectorHealth]:
    return [connector.health_check() for connector in connector_registry().values()]
