from app.models import FinancialFact
from finresearch.repositories.financial_facts import FinancialFactRepository
from finresearch.services.job_service import JobService
from finresearch.services.research_service import ResearchService


def _set_database(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'research.sqlite'}")
    monkeypatch.setenv("LLM_ENABLED", "false")
    monkeypatch.setenv("AGENT_REACH_ENABLED", "true")
    monkeypatch.setenv("EXA_ENABLED", "false")


def test_background_research_job_completes_without_ollama_or_exa(monkeypatch, tmp_path) -> None:
    _set_database(monkeypatch, tmp_path)
    FinancialFactRepository().upsert_many(
        [
            FinancialFact(
                symbol="600519",
                metric_code="revenue",
                metric_name="营业收入",
                value=100.0,
                period_end="2025-12-31",
                publication_date="2026-01-01",
                report_type="annual",
                statement_type="profit_sheet",
                data_source="fixture",
                retrieved_at="2026-06-26T00:00:00+00:00",
            ),
            FinancialFact(
                symbol="600519",
                metric_code="net_profit_parent",
                metric_name="归母净利润",
                value=30.0,
                period_end="2025-12-31",
                publication_date="2026-01-01",
                report_type="annual",
                statement_type="profit_sheet",
                data_source="fixture",
                retrieved_at="2026-06-26T00:00:00+00:00",
            ),
        ]
    )
    monkeypatch.setattr("finresearch.connectors.rss.RSSConnector.search", lambda *_args, **_kwargs: [])
    calls = {"mcporter": 0}

    def fail_exa(*_args, **_kwargs):
        calls["mcporter"] += 1
        raise AssertionError("mcporter must not run when EXA_ENABLED=false")

    monkeypatch.setattr(
        "finresearch.connectors.agent_reach.client.AgentReachCommandClient.exa_search",
        fail_exa,
    )
    pending = ResearchService(tmp_path).create_background_run("600519")
    job = JobService(tmp_path).create_research_job(
        research_run_id=int(pending["research_run_id"]),
        symbol="600519",
    )
    ResearchService(tmp_path).research_repo.attach_job(int(pending["research_run_id"]), int(job["id"]))

    result = JobService(tmp_path).run_next()
    run = ResearchService(tmp_path).get_run(int(pending["research_run_id"]))

    assert result["status"] == "completed"
    assert run["status"] == "completed"
    assert "专业研究记录" in run["report_markdown"]
    assert calls["mcporter"] == 0


def test_background_research_failure_records_error_fields(monkeypatch, tmp_path) -> None:
    _set_database(monkeypatch, tmp_path)
    pending = ResearchService(tmp_path).create_background_run("600519")
    job = JobService(tmp_path).create_research_job(
        research_run_id=int(pending["research_run_id"]),
        symbol="600519",
    )
    ResearchService(tmp_path).research_repo.attach_job(int(pending["research_run_id"]), int(job["id"]))
    monkeypatch.setattr(
        "finresearch.services.research_service.ResearchService.create_structured_run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    result = JobService(tmp_path).run_next()
    run = ResearchService(tmp_path).get_run(int(pending["research_run_id"]))

    assert result["status"] == "failed"
    assert result["error_type"] == "RuntimeError"
    assert result["failed_at"] is not None
    assert result["retryable"] is True
    assert run["status"] == "failed"
    assert run["error_message"] == "boom"
