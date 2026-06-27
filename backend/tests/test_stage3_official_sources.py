from __future__ import annotations

import socket

import pytest
from fastapi.testclient import TestClient

from app.models import FinancialFact
from finresearch.api.main import app
from finresearch.data_sources.official_registry import OfficialSourceRegistry
from finresearch.repositories.data_quality import DataQualityRepository
from finresearch.repositories.financial_facts import FinancialFactRepository
from finresearch.repositories.filings import FilingRepository
from finresearch.services.artifact_download import ArtifactDownloadService
from finresearch.services.benchmark_selection import BenchmarkSelectionService
from finresearch.services.filing_document_parser import FilingDocumentParser


def _public_dns(*_args, **_kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


def test_official_source_registry_contracts() -> None:
    registry = OfficialSourceRegistry()
    source_ids = {item.source_id for item in registry.list_definitions()}

    assert {"cninfo", "sse", "szse", "bse", "sec_edgar"}.issubset(source_ids)
    for source_id in ("cninfo", "sse", "szse", "bse"):
        adapter = registry.get_adapter(source_id)
        health = adapter.health_check()
        assert health.status == "fixture_verified"
        fixture_symbol = {"szse": "000001", "bse": "430047"}.get(source_id, "600519")
        candidates = adapter.list_filings(symbol=fixture_symbol)
        assert candidates
        assert candidates[0].source_id == source_id
        assert candidates[0].canonical_url.startswith("https://")


def test_filing_upsert_and_revision_are_idempotent(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")
    adapter = OfficialSourceRegistry().get_adapter("cninfo")
    repo = FilingRepository()
    company_id = repo.upsert_company_identity(adapter.resolve_company("600519"))

    candidates = adapter.list_filings(symbol="600519")
    first_id, created = repo.upsert_candidate(candidates[0], company_id)
    again_id, created_again = repo.upsert_candidate(candidates[0], company_id)
    revision_id, revision_created = repo.upsert_candidate(candidates[1], company_id)

    assert created is True
    assert first_id == again_id
    assert created_again is False
    assert revision_created is True
    assert revision_id != first_id
    assert len(repo.list("600519")) == 2


def test_artifact_archive_hash_reuse_and_ssrf_blocks(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DOCUMENTS_DIR", str(tmp_path / "documents"))
    monkeypatch.setenv("RAW_DATA_DIR", str(tmp_path / "raw"))
    monkeypatch.setattr(socket, "getaddrinfo", _public_dns)
    adapter = OfficialSourceRegistry().get_adapter("cninfo")
    metadata = adapter.fetch_filing_metadata(adapter.list_filings(symbol="600519")[0])

    service = ArtifactDownloadService(max_bytes=1024 * 1024)
    first = service.archive_bytes(
        metadata,
        adapter.download_artifact(metadata),
        allowed_domains=("static.cninfo.com.cn", "www.cninfo.com.cn"),
    )
    second = service.archive_bytes(
        metadata,
        adapter.download_artifact(metadata),
        allowed_domains=("static.cninfo.com.cn", "www.cninfo.com.cn"),
    )

    assert first.sha256 == second.sha256
    assert second.reused is True
    assert first.final_path.exists()
    with pytest.raises(ValueError, match="blocked_url_scheme"):
        service.validate_url("file:///etc/passwd", ("static.cninfo.com.cn",))
    with pytest.raises(ValueError, match="domain_not_allowed"):
        service.validate_url("https://example.com/report.pdf", ("static.cninfo.com.cn",))


def test_page_aware_parser_creates_stable_chunks(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")
    monkeypatch.setenv("DOCUMENTS_DIR", str(tmp_path / "documents"))
    monkeypatch.setenv("RAW_DATA_DIR", str(tmp_path / "raw"))
    monkeypatch.setattr(socket, "getaddrinfo", _public_dns)
    adapter = OfficialSourceRegistry().get_adapter("cninfo")
    candidate = adapter.list_filings(symbol="600519")[0]
    repo = FilingRepository()
    company_id = repo.upsert_company_identity(adapter.resolve_company("600519"))
    filing_id, _ = repo.upsert_candidate(candidate, company_id)
    metadata = adapter.fetch_filing_metadata(candidate)
    artifact = ArtifactDownloadService().archive_bytes(
        metadata,
        adapter.download_artifact(metadata),
        allowed_domains=("static.cninfo.com.cn", "www.cninfo.com.cn"),
    )
    repo.update_download(
        filing_id,
        local_path=str(artifact.final_path),
        raw_metadata_path=str(artifact.raw_metadata_path),
        sha256=artifact.sha256,
        content_type=artifact.content_type,
        content_length=artifact.content_length,
    )

    result = FilingDocumentParser().parse_filing(filing_id)
    result_again = FilingDocumentParser().parse_filing(filing_id)

    assert result["filing_id"] == filing_id
    assert result["chunks_created"] >= 1
    assert result_again["chunks_created"] == result["chunks_created"]


def test_data_quality_issue_idempotence(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")
    repo = DataQualityRepository()

    first = repo.upsert_issue(
        issue_type="missing_publication_date",
        severity="medium",
        entity_type="filing",
        entity_id="1",
        source_id="cninfo",
    )
    second = repo.upsert_issue(
        issue_type="missing_publication_date",
        severity="medium",
        entity_type="filing",
        entity_id="1",
        source_id="cninfo",
    )

    assert first == second
    assert repo.summary()["open_count"] == 1


def test_unofficial_sources_cannot_write_financial_facts(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")

    with pytest.raises(ValueError, match="unofficial_source"):
        FinancialFactRepository().upsert_many(
            [
                FinancialFact(
                    symbol="600519",
                    metric_code="revenue",
                    metric_name="营业收入",
                    value=1.0,
                    period_end="2025-12-31",
                    data_source="community",
                    retrieved_at="2026-06-26T00:00:00+00:00",
                )
            ]
        )


def test_benchmark_selection_returns_missing_price_reason(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")

    selection = BenchmarkSelectionService().select_for_symbol("688001")

    assert selection["benchmark_code"] == "000688.SH"
    assert selection["missing_reason"] == "benchmark_price_missing"


def test_stage3_api_empty_and_job_states(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")
    client = TestClient(app)

    assert client.get("/v1/data-sources").status_code == 200
    assert client.get("/v1/companies/600519/filings").json() == []
    response = client.post("/v1/companies/600519/filings/sync", json={"source_ids": ["cninfo"]})
    assert response.status_code == 200
    assert response.json()["job_type"] == "sync_official_filings"
    assert client.get("/v1/data-quality/summary").status_code == 200
