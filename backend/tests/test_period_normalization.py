from pytest import approx

from finresearch.metrics import FinancialPeriod
from finresearch.services.period_normalization import PeriodNormalizationService


def _period(
    period_end: str,
    values: dict[str, float],
    *,
    period_start: str | None = "__default__",
    fact_id_start: int = 1,
    currency: str = "CNY",
    publication_date: str = "2026-04-30",
    report_type: str = "quarterly",
    flow_basis: str | None = None,
    is_cumulative: bool | None = None,
) -> FinancialPeriod:
    return FinancialPeriod(
        symbol="000001",
        period_start=f"{period_end[:4]}-01-01" if period_start == "__default__" else period_start,
        period_end=period_end,
        publication_date=publication_date,
        report_type=report_type,
        statement_type="income",
        statement_scope="consolidated",
        is_consolidated=True,
        currency=currency,
        unit="CNY",
        data_source="fixture",
        quality_status="verified",
        version=1,
        values=values,
        fact_ids_by_metric={
            code: (fact_id_start + offset,)
            for offset, code in enumerate(values)
        },
        source_urls_by_metric={code: (f"https://issuer.example/{period_end}/{code}",) for code in values},
        source_pages_by_metric={code: (1,) for code in values},
        flow_basis=flow_basis,
        is_cumulative=is_cumulative,
        source_flow_basis=flow_basis,
    )


def test_cumulative_reports_are_converted_to_single_quarters_and_ttm() -> None:
    service = PeriodNormalizationService()
    result = service.normalize(
        (
            _period("2025-03-31", {"revenue": 100.0}, fact_id_start=10),
            _period("2025-06-30", {"revenue": 230.0}, fact_id_start=20),
            _period("2025-09-30", {"revenue": 390.0}, fact_id_start=30),
            _period("2025-12-31", {"revenue": 600.0}, fact_id_start=40, report_type="annual"),
        )
    )

    quarterly_revenue = [quarter.values["revenue"] for quarter in result.quarters]
    value, selected, reason = service.ttm(result.quarters, "revenue")

    assert quarterly_revenue == [100.0, 130.0, 160.0, 210.0]
    assert value == 600.0
    assert reason is None
    assert selected[0].period_start == "2025-01-01"
    assert selected[-1].period_end == "2025-12-31"
    assert result.quarters[1].fact_ids("revenue") == (20, 10)
    assert result.quarters[3].fact_ids("revenue") == (40, 30)


def test_original_single_quarter_reports_are_preserved_without_diffing() -> None:
    service = PeriodNormalizationService()
    result = service.normalize(
        (
            _period("2025-03-31", {"revenue": 100.0}, period_start="2025-01-01", fact_id_start=10),
            _period("2025-06-30", {"revenue": 130.0}, period_start="2025-04-01", fact_id_start=20),
            _period("2025-09-30", {"revenue": 160.0}, period_start="2025-07-01", fact_id_start=30),
            _period("2025-12-31", {"revenue": 210.0}, period_start="2025-10-01", fact_id_start=40),
        )
    )

    assert [quarter.values["revenue"] for quarter in result.quarters] == [100.0, 130.0, 160.0, 210.0]
    assert result.quarters[1].fact_ids("revenue") == (20,)
    assert result.quarters[3].fact_ids("revenue") == (40,)
    assert "source single quarter" in result.quarters[3].formulas_by_metric["revenue"]


def test_mixed_cumulative_and_single_quarter_inputs_use_each_basis_correctly() -> None:
    service = PeriodNormalizationService()
    result = service.normalize(
        (
            _period("2025-03-31", {"revenue": 100.0}, fact_id_start=10),
            _period("2025-06-30", {"revenue": 230.0}, fact_id_start=20),
            _period("2025-06-30", {"revenue": 135.0}, period_start="2025-04-01", fact_id_start=25),
            _period("2025-09-30", {"revenue": 390.0}, fact_id_start=30),
            _period("2025-12-31", {"revenue": 215.0}, period_start="2025-10-01", fact_id_start=40),
        )
    )

    assert [quarter.values["revenue"] for quarter in result.quarters] == [100.0, 135.0, 160.0, 215.0]
    assert result.quarters[1].fact_ids("revenue") == (25,)
    assert result.quarters[2].fact_ids("revenue") == (30, 20)


def test_unknown_flow_basis_is_not_guessed() -> None:
    result = PeriodNormalizationService().normalize(
        (
            _period(
                "2025-06-30",
                {"revenue": 230.0},
                period_start="2025-02-01",
                fact_id_start=20,
            ),
        )
    )

    assert result.quarters[0].values == {}
    assert result.warnings == ("ambiguous_flow_basis:2025-06-30:revenue",)


def test_missing_period_start_is_ambiguous_for_flow_metrics() -> None:
    result = PeriodNormalizationService().normalize(
        (
            _period(
                "2025-09-30",
                {"revenue": 390.0},
                period_start=None,
                fact_id_start=30,
                flow_basis="unknown",
            ),
        )
    )

    assert result.quarters[0].values == {}
    assert result.warnings == ("ambiguous_flow_basis:2025-09-30:revenue",)


def test_annual_report_minus_third_quarter_produces_q4() -> None:
    result = PeriodNormalizationService().normalize(
        (
            _period("2025-03-31", {"revenue": 100.0}, fact_id_start=10),
            _period("2025-06-30", {"revenue": 230.0}, fact_id_start=20),
            _period("2025-09-30", {"revenue": 390.0}, fact_id_start=30),
            _period("2025-12-31", {"revenue": 600.0}, fact_id_start=40, report_type="annual"),
        )
    )

    assert result.quarters[3].values["revenue"] == 210.0
    assert result.quarters[3].fact_ids("revenue") == (40, 30)


def test_existing_single_quarter_q4_is_not_reconverted() -> None:
    result = PeriodNormalizationService().normalize(
        (
            _period("2025-09-30", {"revenue": 390.0}, fact_id_start=30),
            _period("2025-12-31", {"revenue": 210.0}, period_start="2025-10-01", fact_id_start=40),
        )
    )

    assert result.quarters[-1].values["revenue"] == 210.0
    assert result.quarters[-1].fact_ids("revenue") == (40,)


def test_latest_restatement_wins_for_single_quarter_inputs() -> None:
    result = PeriodNormalizationService().normalize(
        (
            _period(
                "2025-06-30",
                {"revenue": 130.0},
                period_start="2025-04-01",
                fact_id_start=20,
                publication_date="2025-07-20",
            ),
            _period(
                "2025-06-30",
                {"revenue": 135.0},
                period_start="2025-04-01",
                fact_id_start=25,
                publication_date="2025-08-20",
            ),
        )
    )

    assert result.quarters[0].values["revenue"] == 135.0
    assert result.quarters[0].fact_ids("revenue") == (25,)


def test_ttm_requires_four_contiguous_comparable_quarters() -> None:
    service = PeriodNormalizationService()
    result = service.normalize(
        (
            _period("2025-03-31", {"revenue": 100.0}),
            _period("2025-06-30", {"revenue": 210.0}),
            _period("2025-12-31", {"revenue": 500.0}, report_type="annual"),
        )
    )

    value, selected, reason = service.ttm(result.quarters, "revenue")

    assert value is None
    assert selected == ()
    assert reason == "insufficient_contiguous_quarters"


def test_yoy_prefers_annual_comparable_periods_and_rejects_zero_denominator() -> None:
    service = PeriodNormalizationService()
    periods = (
        _period("2024-12-31", {"revenue": 0.0}, fact_id_start=100, report_type="annual"),
        _period("2025-12-31", {"revenue": 120.0}, fact_id_start=200, report_type="annual"),
    )
    result = service.normalize(periods)

    value, fact_ids, reason = service.yoy(periods, result.quarters, "revenue")

    assert value is None
    assert fact_ids == (200, 100)
    assert reason == "zero_denominator"


def test_period_normalization_rejects_currency_mismatch() -> None:
    result = PeriodNormalizationService().normalize(
        (
            _period("2025-03-31", {"revenue": 100.0}, currency="CNY"),
            _period("2025-06-30", {"revenue": 200.0}, currency="USD"),
        )
    )

    assert result.quarters == ()
    assert result.warnings == ("currency_mismatch",)


def test_latest_restatement_wins_by_publication_date_and_version() -> None:
    service = PeriodNormalizationService()
    result = service.normalize(
        (
            _period("2025-03-31", {"revenue": 100.0}, fact_id_start=1, publication_date="2025-04-20"),
            _period("2025-03-31", {"revenue": 110.0}, fact_id_start=5, publication_date="2025-05-20"),
            _period("2025-06-30", {"revenue": 250.0}, fact_id_start=10),
        )
    )

    assert result.quarters[0].values["revenue"] == 110.0
    assert result.quarters[1].values["revenue"] == approx(140.0)
