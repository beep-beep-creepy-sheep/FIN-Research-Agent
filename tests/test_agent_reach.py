from app.agent_reach import AgentReachClient


def test_legacy_agent_reach_respects_exa_enabled_false(monkeypatch) -> None:
    monkeypatch.setenv("EXA_ENABLED", "false")
    calls = {"which": 0}

    def fake_which(_command: str) -> str | None:
        calls["which"] += 1
        return "/usr/local/bin/mcporter"

    monkeypatch.setattr("shutil.which", fake_which)

    result = AgentReachClient().exa_search("query")

    assert not result.ok
    assert result.stderr == "EXA_ENABLED=false"
    assert calls["which"] == 0
