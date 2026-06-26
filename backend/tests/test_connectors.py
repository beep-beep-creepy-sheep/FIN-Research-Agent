from finresearch.connectors.agent_reach.commands import AgentReachExaConnector
from finresearch.connectors.agent_reach.client import CommandResult
from finresearch.connectors.agent_reach.normalizers import normalize_exa_stdout
from finresearch.connectors.direct_web import DirectWebConnector
from finresearch.repositories.external_sources import ExternalSourceRepository
from finresearch.services.external_research import ExternalResearchService


def test_agent_reach_exa_disabled_skips_mcporter(monkeypatch) -> None:
    calls = {"mcporter": 0}

    def fake_search(*_args: object, **_kwargs: object) -> CommandResult:
        calls["mcporter"] += 1
        return CommandResult(False, "", "should not run")

    monkeypatch.setattr(
        "finresearch.connectors.agent_reach.client.AgentReachCommandClient.exa_search",
        fake_search,
    )
    health = AgentReachExaConnector(agent_reach_enabled=True, exa_enabled=False).health_check()

    assert health.status == "disabled"
    assert calls["mcporter"] == 0


def test_agent_reach_exa_missing_mcporter_is_missing_dependency(monkeypatch) -> None:
    monkeypatch.setattr(
        "finresearch.connectors.agent_reach.client.AgentReachCommandClient.has_command",
        lambda _self, command: command != "mcporter",
    )

    health = AgentReachExaConnector(agent_reach_enabled=True, exa_enabled=True).health_check()

    assert health.status == "missing_dependency"
    assert "mcporter" in str(health.last_error)


def test_agent_reach_exa_unconfigured_is_needs_configuration(monkeypatch) -> None:
    monkeypatch.setattr(
        "finresearch.connectors.agent_reach.client.AgentReachCommandClient.has_command",
        lambda _self, _command: True,
    )
    monkeypatch.setattr(
        "finresearch.connectors.agent_reach.client.AgentReachCommandClient.exa_search",
        lambda *_args, **_kwargs: CommandResult(False, "", "Exa is not configured"),
    )

    health = AgentReachExaConnector(agent_reach_enabled=True, exa_enabled=True).health_check()

    assert health.status == "needs_configuration"


def test_normalize_exa_stdout_fallback() -> None:
    items = normalize_exa_stdout("plain search output", "query")

    assert len(items) == 1
    assert items[0].platform == "exa"
    assert items[0].verification_status == "unverified"


def test_external_source_repository_upserts(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'external.sqlite'}")
    item = DirectWebConnector().health_check()
    assert item.status == "available"

    from finresearch.connectors.base import ExternalItem
    from finresearch.connectors.utils import content_hash, now_iso

    source = ExternalItem(
        connector="test",
        platform="web",
        url="https://example.com",
        title="Example",
        fetched_at=now_iso(),
        content="hello",
        content_hash=content_hash("hello"),
    )
    repo = ExternalSourceRepository()

    first = repo.upsert(source)
    second = repo.upsert(source)

    assert first == second
    assert repo.list()[0]["url"] == "https://example.com"


def test_search_fast_skips_disabled_exa(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'external.sqlite'}")
    monkeypatch.setenv("AGENT_REACH_ENABLED", "true")
    monkeypatch.setenv("EXA_ENABLED", "false")
    calls = {"mcporter": 0}

    def fake_search(*_args: object, **_kwargs: object) -> CommandResult:
        calls["mcporter"] += 1
        return CommandResult(True, "[]")

    monkeypatch.setattr(
        "finresearch.connectors.agent_reach.client.AgentReachCommandClient.exa_search",
        fake_search,
    )

    result = ExternalResearchService().search("贵州茅台", connectors=["agent_reach_exa"])

    assert result.items == []
    assert result.warnings[0].startswith("agent_reach_exa:skipped:disabled")
    assert calls["mcporter"] == 0


def test_connector_failure_opens_circuit(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'external.sqlite'}")

    class BrokenConnector:
        name = "broken"

        def health_check(self):
            from finresearch.connectors.base import ConnectorHealth

            return ConnectorHealth(
                name=self.name,
                status="available",
                enabled=True,
                configured=True,
                available=True,
            )

        def search(self, query: str, limit: int = 10):
            raise RuntimeError("boom")

        def read(self, url: str):
            raise RuntimeError("boom")

    service = ExternalResearchService()
    service.registry = {"broken": BrokenConnector()}

    for _ in range(3):
        service.search("query", connectors=["broken"])

    skipped = service.search("query", connectors=["broken"])

    assert skipped.warnings[0].startswith("broken:skipped:circuit_open")


def test_connector_health_is_cached(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'external.sqlite'}")
    calls = {"health": 0}

    class CachedConnector:
        name = "cached"

        def health_check(self):
            from finresearch.connectors.base import ConnectorHealth

            calls["health"] += 1
            return ConnectorHealth(
                name=self.name,
                status="available",
                enabled=True,
                configured=True,
                available=True,
            )

        def search(self, query: str, limit: int = 10):
            return []

        def read(self, url: str):
            raise RuntimeError("not used")

    service = ExternalResearchService()
    service.registry = {"cached": CachedConnector()}

    first = service.health()
    second = service.health()

    assert first[0]["status"] == "available"
    assert second[0]["status"] == "available"
    assert calls["health"] == 1
