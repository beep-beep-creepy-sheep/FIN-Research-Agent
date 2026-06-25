from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol


TrustLevel = Literal["primary", "secondary", "community", "unknown"]
VerificationStatus = Literal["unverified", "corroborated", "rejected"]
ConnectorState = Literal["available", "unavailable", "disabled", "needs_configuration"]


@dataclass(frozen=True)
class ConnectorHealth:
    name: str
    status: ConnectorState
    active_backend: str | None = None
    requires_login: bool = False
    last_error: str | None = None


@dataclass(frozen=True)
class ExternalItem:
    connector: str
    platform: str
    url: str
    fetched_at: str
    content_hash: str
    external_id: str | None = None
    title: str | None = None
    author: str | None = None
    published_at: str | None = None
    content: str = ""
    trust_level: TrustLevel = "unknown"
    verification_status: VerificationStatus = "unverified"
    metadata: dict[str, object] = field(default_factory=dict)


class InternetConnector(Protocol):
    name: str

    def health_check(self) -> ConnectorHealth: ...

    def search(self, query: str, limit: int = 10) -> list[ExternalItem]: ...

    def read(self, url: str) -> ExternalItem: ...

