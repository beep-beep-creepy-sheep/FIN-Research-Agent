import requests

from finresearch.ai.ollama import OllamaProvider
from finresearch.settings import Settings


def _settings(tmp_path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'x.sqlite'}",
        data_dir=tmp_path,
        documents_dir=tmp_path / "documents",
        raw_data_dir=tmp_path / "raw",
        reports_dir=tmp_path / "reports",
        llm_enabled=True,
        ollama_model="qwen3:8b",
    )


def test_ollama_generate_timeout_is_classified(monkeypatch, tmp_path) -> None:
    def timeout(*_args, **_kwargs):
        raise requests.Timeout("slow")

    monkeypatch.setattr("requests.post", timeout)

    try:
        OllamaProvider(_settings(tmp_path)).generate("hello")
    except RuntimeError as exc:
        assert str(exc) == "ollama_timeout"
    else:
        raise AssertionError("expected timeout")


def test_ollama_status_unavailable(monkeypatch, tmp_path) -> None:
    def unavailable(*_args, **_kwargs):
        raise requests.ConnectionError("down")

    monkeypatch.setattr("requests.get", unavailable)

    status = OllamaProvider(_settings(tmp_path)).status()

    assert status["available"] is False
    assert status["error_type"] == "ollama_unavailable"
