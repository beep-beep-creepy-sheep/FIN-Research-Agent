from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from finresearch.api.main import app
from finresearch.data_sources.official import FilingMetadata
from finresearch.services.artifact_download import ArtifactDownloadService
from finresearch.services.institutional_report import (
    InstitutionalReport,
    InstitutionalReportSection,
    _contains_forbidden_advice,
    _to_html,
    _to_markdown,
)
from finresearch.settings import Settings, validate_settings


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    base = {
        "app_env": "development",
        "database_url": f"sqlite:///{tmp_path / 'library.sqlite'}",
        "data_dir": tmp_path,
        "documents_dir": tmp_path / "documents",
        "raw_data_dir": tmp_path / "raw",
        "reports_dir": tmp_path / "reports",
    }
    base.update(overrides)
    return Settings(**base)


def test_config_validation_success_and_safe_defaults(tmp_path: Path) -> None:
    result = validate_settings(_settings(tmp_path))

    assert result["status"] == "passed"
    summary = result["summary"]
    assert summary["llm"] == {"enabled": False, "provider": "ollama"}
    assert summary["external_network"]["official_source_mode"] == "fixture"
    assert "*" not in summary["api"]["cors_origins"]


def test_missing_required_production_config_fails(tmp_path: Path) -> None:
    result = validate_settings(_settings(tmp_path, app_env="production"))

    assert result["status"] == "failed"
    assert any("PostgreSQL" in error for error in result["errors"])


def test_secret_redaction_does_not_expose_full_value(tmp_path: Path) -> None:
    result = validate_settings(_settings(tmp_path, openai_api_key="sk-placeholder-secret-value"))

    encoded = json.dumps(result, ensure_ascii=False)
    assert "sk-placeholder-secret-value" not in encoded
    assert "[redacted]" in encoded


def test_system_health_readiness_version_and_config_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DOCUMENTS_DIR", "RAW_DATA_DIR", "REPORTS_DIR", "LLM_ENABLED", "AGENT_REACH_ENABLED"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")
    monkeypatch.setenv("APP_ENV", "test")
    client = TestClient(app)

    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json()["status"] == "ready"
    assert client.get("/version").json()["stage"] == "stage_8_production_security_release"
    config = client.get("/v1/system/config-check")
    assert config.status_code == 200
    assert config.json()["status"] == "passed"
    status = client.get("/v1/system/status").json()
    assert status["database"]["status"] == "ok"
    assert "Users" not in json.dumps(status)


def test_structured_validation_error_and_query_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")
    client = TestClient(app)

    response = client.post("/v1/screener/query", json={"limit": 201})

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "validation_error"
    assert payload["error"]["request_id"]


def test_404_error_contract_has_code_and_request_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")
    client = TestClient(app)

    response = client.get("/v1/portfolios/999999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "portfolio_not_found"
    assert response.headers["X-Request-ID"]


def test_path_traversal_document_id_is_blocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    metadata = FilingMetadata(
        source_id="cninfo",
        source_document_id="../..",
        symbol="600519",
        exchange="SSE",
        title="unsafe",
        filing_type="annual_report",
        announcement_category="periodic_report",
        publication_date="2026-04-01",
        report_period="2025",
        canonical_url="https://www.cninfo.com.cn/unsafe.pdf",
        download_url="https://www.cninfo.com.cn/unsafe.pdf",
        document_type="pdf",
        source_tier="official",
    )

    with pytest.raises(ValueError, match="unsafe_path_segment"):
        ArtifactDownloadService().archive_bytes(
            metadata,
            b"%PDF-1.4\n",
            allowed_domains=("www.cninfo.com.cn",),
        )


def test_ssrf_guard_blocks_private_dns_resolution(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    def fake_getaddrinfo(*_args: object, **_kwargs: object):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(ValueError, match="blocked_private_or_metadata_ip"):
        ArtifactDownloadService().validate_url(
            "https://static.cninfo.com.cn/finalpage/fixture.pdf",
            ("static.cninfo.com.cn",),
        )


def test_markdown_and_html_exports_escape_untrusted_content() -> None:
    report = InstitutionalReport(
        run_id="report_test",
        symbol="600519",
        as_of_date="2026-06-29",
        strict_as_of=True,
        report_style="institutional_full",
        language="en",
        sections=(
            InstitutionalReportSection(
                section_id="evidence_appendix",
                title="<script>alert(1)</script>",
                status="completed",
                content={"snippet": "<img src=x onerror=alert(1)>"},
                evidence_ids=("ev_1",),
            ),
        ),
        validation={"status": "passed"},
        evidence_coverage={"referenced_evidence_count": 1, "available_evidence_count": 1},
        warnings=(),
        limitations=(),
        llm={"enabled": False},
        bundle_hash="bundle",
        report_hash="hash",
        generated_at="2026-06-29T00:00:00+00:00",
    )

    markdown = _to_markdown(report)
    html = _to_html(report, markdown)

    assert "<script>alert(1)</script>" in markdown
    assert "<script>alert(1)</script>" not in html
    assert "<img src=x onerror=alert(1)>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_forbidden_advice_and_trading_wording_guards() -> None:
    assert _contains_forbidden_advice("target price")
    assert _contains_forbidden_advice("买入")
    assert _contains_forbidden_advice("sell")
    assert not _contains_forbidden_advice("research-only valuation scenario")
