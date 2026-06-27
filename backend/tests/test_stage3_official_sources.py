from __future__ import annotations

import socket
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app.models import FinancialFact
from finresearch.api.main import app
from finresearch.data_sources.cninfo_live import CNInfoLiveSourceAdapter
from finresearch.data_sources.official import SourceAdapterError
from finresearch.data_sources.official_registry import OfficialSourceRegistry
from finresearch.repositories.data_quality import DataQualityRepository
from finresearch.repositories.financial_facts import FinancialFactRepository
from finresearch.repositories.filings import FilingRepository
from finresearch.repositories.documents import DocumentRepository
from finresearch.services.artifact_download import ArtifactDownloadService
from finresearch.services.benchmark_selection import BenchmarkSelectionService
from finresearch.services.filing_document_parser import FilingDocumentParser
from finresearch.services.job_service import JobService
from finresearch.services.official_filings import OfficialFilingService


def _public_dns(*_args, **_kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


PDF_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n"


@dataclass
class FakeResponse:
    status_code: int
    body: bytes
    headers: dict[str, str]

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> dict[str, object]:
        import json

        return json.loads(self.text)

    def iter_content(self, chunk_size: int = 65536):
        for index in range(0, len(self.body), chunk_size):
            yield self.body[index : index + chunk_size]

    def close(self) -> None:
        pass


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.urls: list[str] = []

    def get(self, url: str, **_kwargs):
        self.urls.append(url)
        return self.responses.pop(0)


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


def test_official_source_mode_policy(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///data/test-mode-policy.sqlite")
    registry = OfficialSourceRegistry()

    monkeypatch.setenv("OFFICIAL_SOURCE_MODE", "fixture")
    assert registry.get_adapter("cninfo").health_check().status == "fixture_verified"

    monkeypatch.setenv("OFFICIAL_SOURCE_MODE", "live")
    assert isinstance(registry.get_adapter("cninfo"), CNInfoLiveSourceAdapter)
    with pytest.raises(SourceAdapterError, match="live_adapter_not_implemented"):
        registry.get_adapter("sse")


def test_cninfo_live_adapter_normalizes_mocked_json(monkeypatch) -> None:
    definition = OfficialSourceRegistry().get_definition("cninfo")
    assert definition is not None

    def fake_post(*_args, **_kwargs):
        return FakeResponse(
            200,
            b'{"announcements":[{"announcementId":"live-1","announcementTitle":"2025\\u5e74\\u5e74\\u5ea6\\u62a5\\u544a","adjunctUrl":"finalpage/2026-04-02/live.pdf","announcementTime":1775088000000}]}',
            {"content-type": "application/json"},
        )

    monkeypatch.setattr("finresearch.data_sources.cninfo_live.requests.post", fake_post)
    adapter = CNInfoLiveSourceAdapter(definition)

    candidates = adapter.list_filings(symbol="600519", start_date="2026-01-01", end_date="2026-12-31", limit=1)

    assert candidates[0].source_document_id == "live-1"
    assert candidates[0].download_url == "https://static.cninfo.com.cn/finalpage/2026-04-02/live.pdf"
    assert candidates[0].publication_date == "2026-04-02"
    assert candidates[0].filing_type == "annual_report"


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


def test_artifact_http_download_redirect_and_validation(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DOCUMENTS_DIR", str(tmp_path / "documents"))
    monkeypatch.setenv("RAW_DATA_DIR", str(tmp_path / "raw"))
    monkeypatch.setattr(socket, "getaddrinfo", _public_dns)
    adapter = OfficialSourceRegistry().get_fixture_adapter("cninfo")
    metadata = adapter.fetch_filing_metadata(adapter.list_filings(symbol="600519")[0])
    metadata = metadata.__class__(**{**metadata.__dict__, "download_url": "https://static.cninfo.com.cn/a.pdf"})
    service = ArtifactDownloadService(max_bytes=1024)

    artifact = service.download_from_url(
        metadata,
        allowed_domains=("static.cninfo.com.cn", "www.cninfo.com.cn"),
        session=FakeSession(
            [
                FakeResponse(302, b"", {"Location": "https://static.cninfo.com.cn/b.pdf"}),
                FakeResponse(200, PDF_BYTES, {"Content-Type": "application/pdf"}),
            ]
        ),
    )
    reused = service.download_from_url(
        metadata,
        allowed_domains=("static.cninfo.com.cn", "www.cninfo.com.cn"),
        session=FakeSession([FakeResponse(200, PDF_BYTES, {"Content-Type": "application/pdf"})]),
    )

    assert artifact.sha256 == reused.sha256
    assert reused.reused is True
    with pytest.raises(ValueError, match="domain_not_allowed"):
        service.download_from_url(
            metadata,
            allowed_domains=("static.cninfo.com.cn",),
            session=FakeSession([FakeResponse(302, b"", {"Location": "https://example.com/b.pdf"})]),
        )
    with pytest.raises(ValueError, match="html_error_page"):
        service.download_from_url(
            metadata,
            allowed_domains=("static.cninfo.com.cn",),
            session=FakeSession([FakeResponse(200, b"<html>blocked</html>", {"Content-Type": "application/pdf"})]),
        )
    with pytest.raises(ValueError, match="invalid_pdf_magic"):
        service.download_from_url(
            metadata,
            allowed_domains=("static.cninfo.com.cn",),
            session=FakeSession([FakeResponse(200, b"not a pdf", {"Content-Type": "application/pdf"})]),
        )
    with pytest.raises(ValueError, match="download_too_large"):
        service.download_from_url(
            metadata,
            allowed_domains=("static.cninfo.com.cn",),
            session=FakeSession([FakeResponse(200, b"%PDF" + b"x" * 2048, {"Content-Type": "application/pdf"})]),
        )


def test_artifact_http_download_blocks_private_dns(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))])
    service = ArtifactDownloadService()

    with pytest.raises(ValueError, match="blocked_private_or_metadata_ip"):
        service.validate_url("https://static.cninfo.com.cn/a.pdf", ("static.cninfo.com.cn",))


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


def test_download_filing_and_retry_jobs_are_idempotent(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")
    monkeypatch.setenv("DOCUMENTS_DIR", str(tmp_path / "documents"))
    monkeypatch.setenv("RAW_DATA_DIR", str(tmp_path / "raw"))
    monkeypatch.setenv("OFFICIAL_SOURCE_MODE", "fixture")
    monkeypatch.setattr(socket, "getaddrinfo", _public_dns)
    jobs = JobService(tmp_path / "library.sqlite")
    repo = FilingRepository()

    jobs.create_official_filing_sync_job("600519", source_ids=["cninfo"], download=False, parse=False)
    sync_result = jobs.run_next()
    filing_id = int(sync_result["result"]["filing_ids"][0])
    jobs.create_filing_job("download_filing", filing_id)
    download_result = jobs.run_next()
    jobs.create_filing_job("download_filing", filing_id)
    download_again = jobs.run_next()

    assert download_result["status"] == "completed"
    assert download_again["result"]["sha256"] == download_result["result"]["sha256"]
    assert download_again["result"]["reused"] is True

    repo.update_parse_status(filing_id, "failed", "fixture parse retry")
    jobs.create_filing_job("retry_filing", filing_id)
    retry_result = jobs.run_next()
    chunks = DocumentRepository().chunks(int(retry_result["result"]["document_id"]))
    jobs.create_filing_job("retry_filing", filing_id)
    retry_again = jobs.run_next()
    chunks_again = DocumentRepository().chunks(int(retry_again["result"].get("document_id", retry_result["result"]["document_id"])))

    assert retry_result["status"] == "completed"
    assert len(chunks_again) == len(chunks)


def test_retry_download_failed_filing(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")
    monkeypatch.setenv("DOCUMENTS_DIR", str(tmp_path / "documents"))
    monkeypatch.setenv("RAW_DATA_DIR", str(tmp_path / "raw"))
    monkeypatch.setenv("OFFICIAL_SOURCE_MODE", "fixture")
    monkeypatch.setattr(socket, "getaddrinfo", _public_dns)
    adapter = OfficialSourceRegistry().get_fixture_adapter("cninfo")
    repo = FilingRepository()
    company_id = repo.upsert_company_identity(adapter.resolve_company("600519"))
    filing_id, _ = repo.upsert_candidate(adapter.list_filings(symbol="600519")[0], company_id)
    repo.update_download_failure(filing_id, error_type="fixture", error_message="failed once")

    result = OfficialFilingService().retry_filing(filing_id)

    assert result["status"] == "downloaded"
    assert FilingRepository().get(filing_id)["download_status"] == "downloaded"


def test_live_not_implemented_download_job_fails_structured(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")
    monkeypatch.setenv("OFFICIAL_SOURCE_MODE", "fixture")
    adapter = OfficialSourceRegistry().get_fixture_adapter("sse")
    repo = FilingRepository()
    company_id = repo.upsert_company_identity(adapter.resolve_company("600519"))
    filing_id, _ = repo.upsert_candidate(adapter.list_filings(symbol="600519")[0], company_id)
    monkeypatch.setenv("OFFICIAL_SOURCE_MODE", "live")
    jobs = JobService(tmp_path / "library.sqlite")

    jobs.create_filing_job("download_filing", filing_id)
    result = jobs.run_next()

    assert result["status"] == "failed"
    assert result["error_type"] == "SourceAdapterError"
    filing = repo.get(filing_id)
    assert filing["download_status"] == "failed"
