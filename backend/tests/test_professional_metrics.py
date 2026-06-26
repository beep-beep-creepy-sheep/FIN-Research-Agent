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
