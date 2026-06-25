from finresearch.connectors.agent_reach.commands import AgentReachConnector
from finresearch.connectors.agent_reach.normalizers import normalize_exa_stdout
from finresearch.connectors.direct_web import DirectWebConnector
from finresearch.repositories.external_sources import ExternalSourceRepository


def test_agent_reach_disabled_by_default() -> None:
    health = AgentReachConnector(enabled=False).health_check()

    assert health.status == "disabled"


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
