from pytest import approx

from finresearch.metrics import CalculationContext, FinancialPeriod, MetricResult, PricePoint
from finresearch.services.professional_metrics import ProfessionalMetricEngine


def _period(
    period_end: str,
    values: dict[str, float],
    *,
    fact_id_start: int,
    report_type: str = "quarterly",
) -> FinancialPeriod:
    return FinancialPeriod(
        symbol="000001",
        period_start=f"{period_end[:4]}-01-01",
        period_end=period_end,
        publication_date=f"{period_end[:4]}-05-01",
        report_type=report_type,
        statement_type="consolidated",
        statement_scope="consolidated",
        is_consolidated=True,
        currency="CNY",
        unit="CNY",
        data_source="fixture",
        quality_status="verified",
        version=1,
        values=values,
        fact_ids_by_metric={code: (fact_id_start + index,) for index, code in enumerate(values)},
        source_urls_by_metric={code: (f"https://issuer.example/{period_end}/{code}",) for code in values},
        source_pages_by_metric={code: (1,) for code in values},
    )


def _single_quarter(
    period_end: str,
    values: dict[str, float],
    *,
    fact_id_start: int,
) -> FinancialPeriod:
    quarter_start = {
        "03-31": "01-01",
        "06-30": "04-01",
        "09-30": "07-01",
        "12-31": "10-01",
    }[period_end[5:]]
    return FinancialPeriod(
        symbol="000001",
        period_start=f"{period_end[:4]}-{quarter_start}",
        period_end=period_end,
        publication_date=f"{period_end[:4]}-05-01",
        report_type="quarterly",
        statement_type="consolidated",
        statement_scope="consolidated",
        is_consolidated=True,
        currency="CNY",
        unit="CNY",
        data_source="fixture",
        quality_status="verified",
        version=1,
        values=values,
        fact_ids_by_metric={code: (fact_id_start + index,) for index, code in enumerate(values)},
        source_urls_by_metric={code: (f"https://issuer.example/{period_end}/{code}",) for code in values},
        source_pages_by_metric={code: (1,) for code in values},
        flow_basis="single_quarter",
        is_cumulative=False,
    )


def _context(*, industry: str | None = None, negative_profit: bool = False) -> CalculationContext:
    cumulative = [
        ("2025-03-31", 100.0, 20.0, 25.0, 30.0, -10.0),
        ("2025-06-30", 230.0, 42.0, 55.0, 60.0, -20.0),
        ("2025-09-30", 390.0, 66.0, 90.0, 90.0, -30.0),
        ("2025-12-31", 600.0, -10.0 if negative_profit else 100.0, 140.0, 120.0, -40.0),
    ]
    periods = [
        _period(
            period_end,
            {
                "revenue": revenue,
                "net_profit_parent": profit,
                "ebit": ebit,
                "depreciation": 4.0 * index,
                "amortization": 1.0 * index,
                "income_tax": 3.0 * index,
                "profit_before_tax": 15.0 * index,
                "operating_cash_flow": ocf,
                "capital_expenditure": capex,
                "interest_bearing_debt": 80.0 + index,
                "cash_and_equivalents": 30.0,
                "total_equity": 200.0 + index * 10,
                "shares_outstanding": 10.0,
            },
            fact_id_start=index * 100,
            report_type="annual" if period_end.endswith("12-31") else "quarterly",
        )
        for index, (period_end, revenue, profit, ebit, ocf, capex) in enumerate(cumulative, start=1)
    ]
    return CalculationContext(
        financial_periods=tuple(periods),
        price_series=(
            PricePoint(1, "000001", "2025-12-30", 18.0, "qfq", "fixture_price"),
            PricePoint(2, "000001", "2025-12-31", 20.0, "qfq", "fixture_price"),
        ),
        as_of_date="2025-12-31",
        currency="CNY",
        industry=industry,
    )


def _results(context: CalculationContext) -> dict[str, MetricResult]:
    return {result.code: result for result in ProfessionalMetricEngine().calculate(context)}


def test_professional_engine_calculates_ttm_fcf_and_valuation_metrics() -> None:
    by_code = _results(_context())

    assert by_code["revenue_ttm"].value == 600.0
    assert by_code["net_profit_ttm"].value == 100.0
    assert by_code["fcf_ttm"].value == 80.0
    assert by_code["ebitda_ttm"].value == 160.0
    assert by_code["net_debt"].value == 54.0
    assert by_code["fcf_yield"].value == approx(0.4)
    assert by_code["pe_ttm"].value == 2.0
    assert by_code["ev_to_ebitda"].value == approx((200.0 + 84.0 - 30.0) / 160.0)
    assert by_code["revenue_ttm"].source_fact_ids
    assert by_code["fcf_yield"].source_price_ids == (2,)
    assert by_code["enterprise_value"].input_values["market_price_date"] == "2025-12-31"


def test_professional_engine_rejects_negative_pe_ttm() -> None:
    by_code = _results(_context(negative_profit=True))

    assert by_code["pe_ttm"].value is None
    assert by_code["pe_ttm"].quality_status == "not_applicable"
    assert by_code["pe_ttm"].missing_reason == "not_applicable_negative_earnings"


def test_professional_engine_marks_industry_specific_not_applicable_metrics() -> None:
    by_code = _results(_context(industry="bank"))

    assert by_code["ev_to_ebitda"].quality_status == "not_applicable"
    assert by_code["ev_to_ebitda"].missing_reason == "not_applicable_industry"
    assert by_code["roic"].quality_status == "not_applicable"


def test_professional_engine_does_not_use_future_prices_for_market_cap() -> None:
    context = _context()
    future_price_context = CalculationContext(
        financial_periods=context.financial_periods,
        price_series=context.price_series + (PricePoint(3, "000001", "2026-01-02", 99.0, "qfq", "fixture_price"),),
        as_of_date="2025-12-31",
        currency="CNY",
    )

    by_code = _results(future_price_context)

    assert by_code["pe_ttm"].value == 2.0
    assert by_code["pe_ttm"].source_price_ids == (2,)


def test_fcf_ttm_uses_normal_common_window() -> None:
    periods = tuple(
        _single_quarter(
            period_end,
            {"operating_cash_flow": 10.0, "capital_expenditure": -2.0},
            fact_id_start=index * 10,
        )
        for index, period_end in enumerate(
            ["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"],
            start=1,
        )
    )

    by_code = _results(CalculationContext(financial_periods=periods, currency="CNY"))

    assert by_code["fcf_ttm"].value == 32.0
    assert by_code["fcf_ttm"].input_values["selected_quarters"] == [
        "2025-03-31",
        "2025-06-30",
        "2025-09-30",
        "2025-12-31",
    ]


def test_common_ttm_window_skips_latest_when_component_missing() -> None:
    periods = tuple(
        _single_quarter(
            period_end,
            {"operating_cash_flow": 10.0, **({} if period_end == "2025-12-31" else {"capital_expenditure": -2.0})},
            fact_id_start=index * 10,
        )
        for index, period_end in enumerate(
            ["2024-12-31", "2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"],
            start=1,
        )
    )

    by_code = _results(CalculationContext(financial_periods=periods, currency="CNY"))

    assert by_code["fcf_ttm"].value == 32.0
    assert by_code["fcf_ttm"].input_values["selected_quarters"] == [
        "2024-12-31",
        "2025-03-31",
        "2025-06-30",
        "2025-09-30",
    ]


def test_common_ttm_window_reports_missing_when_no_common_four_quarters() -> None:
    periods = (
        _single_quarter("2025-03-31", {"operating_cash_flow": 10.0}, fact_id_start=10),
        _single_quarter("2025-06-30", {"capital_expenditure": -2.0}, fact_id_start=20),
        _single_quarter("2025-09-30", {"operating_cash_flow": 10.0}, fact_id_start=30),
        _single_quarter("2025-12-31", {"capital_expenditure": -2.0}, fact_id_start=40),
    )

    by_code = _results(CalculationContext(financial_periods=periods, currency="CNY"))

    assert by_code["fcf_ttm"].value is None
    assert by_code["fcf_ttm"].missing_reason == "misaligned_ttm_components"


def test_ebitda_ttm_uses_common_component_window() -> None:
    periods = tuple(
        _single_quarter(
            period_end,
            {"ebit": 10.0, "depreciation": 2.0, "amortization": 1.0},
            fact_id_start=index * 10,
        )
        for index, period_end in enumerate(
            ["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"],
            start=1,
        )
    )

    by_code = _results(CalculationContext(financial_periods=periods, currency="CNY"))

    assert by_code["ebitda_ttm"].value == 52.0
    assert by_code["ebitda_ttm"].input_values["selected_quarters"][-1] == "2025-12-31"


def test_roic_uses_common_tax_window_when_available() -> None:
    context = _context()

    by_code = _results(context)

    assert by_code["roic"].value is not None
    assert by_code["roic"].input_values["selected_quarters"] == [
        "2025-03-31",
        "2025-06-30",
        "2025-09-30",
        "2025-12-31",
    ]


def test_common_ttm_window_after_cumulative_quarter_conversion() -> None:
    by_code = _results(_context())

    assert by_code["fcf_ttm"].value == 80.0
    assert by_code["fcf_ttm"].input_values["selected_quarters"] == [
        "2025-03-31",
        "2025-06-30",
        "2025-09-30",
        "2025-12-31",
    ]


def test_strict_as_of_common_window_uses_available_periods() -> None:
    context = _context()
    strict_context = CalculationContext(
        financial_periods=context.financial_periods[:-1],
        price_series=context.price_series,
        as_of_date="2025-10-01",
        strict_as_of=True,
        currency="CNY",
    )

    by_code = _results(strict_context)

    assert by_code["fcf_ttm"].value is None
    assert by_code["fcf_ttm"].missing_reason in {
        "insufficient_common_ttm_window",
        "misaligned_ttm_components",
    }
