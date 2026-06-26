from pytest import approx

from finresearch.metrics import calculate_registered_metrics, get_metric_definition, list_metric_definitions
from finresearch.services.metric_calculator import calculate_metric_signals


def test_metric_registry_has_required_core_coverage() -> None:
    definitions = list_metric_definitions()

    assert len(definitions) >= 35
    assert get_metric_definition("net_margin") is not None
    assert get_metric_definition("cash_conversion") is None
    assert all(definition.formula for definition in definitions)
    assert all(definition.inputs for definition in definitions)


def test_registered_metrics_calculate_core_ratios_and_growth() -> None:
    matrix = [
        {
            "period_end": "2025-12-31",
            "revenue": 120.0,
            "gross_profit": 54.0,
            "operating_profit": 36.0,
            "net_profit_parent": 24.0,
            "operating_cash_flow": 30.0,
            "capital_expenditure": 6.0,
            "total_assets": 210.0,
            "total_equity": 120.0,
            "total_liabilities": 90.0,
            "current_assets": 80.0,
            "current_liabilities": 40.0,
            "inventory": 10.0,
            "accounts_receivable": 12.0,
            "accounts_payable": 8.0,
            "cost_of_goods_sold": 66.0,
        },
        {
            "period_end": "2024-12-31",
            "revenue": 100.0,
            "net_profit_parent": 20.0,
            "total_assets": 190.0,
            "total_equity": 100.0,
            "inventory": 8.0,
            "accounts_receivable": 10.0,
            "accounts_payable": 6.0,
        },
    ]

    values = {item.code: item.value for item in calculate_registered_metrics(matrix)}

    assert values["revenue_yoy"] == approx(0.2)
    assert values["gross_margin"] == 0.45
    assert values["net_margin"] == 0.2
    assert values["ocf_to_net_profit"] == 1.25
    assert values["fcf"] == 24.0
    assert values["liability_ratio"] == 90.0 / 210.0
    assert values["current_ratio"] == 2.0
    assert round(values["receivable_days"] or 0, 2) == round(11.0 / 120.0 * 365, 2)


def test_registered_metrics_report_missing_reasons_without_fabrication() -> None:
    observations = calculate_registered_metrics([{"period_end": "2025-12-31", "revenue": 0.0}])
    by_code = {item.code: item for item in observations}

    assert by_code["net_margin"].value is None
    assert by_code["net_margin"].missing_reason == "missing_numerator"
    assert by_code["revenue_yoy"].missing_reason is not None


def test_legacy_metric_calculator_keeps_compatible_keys() -> None:
    result = calculate_metric_signals(
        [
            {
                "period_end": "2025-12-31",
                "revenue": 100.0,
                "net_profit_parent": 20.0,
                "operating_cash_flow": 18.0,
                "total_assets": 200.0,
                "total_equity": 100.0,
                "total_liabilities": 80.0,
            }
        ]
    )

    assert result["metrics"]["net_margin"] == 0.2
    assert result["metrics"]["cash_conversion"] == 0.9
    assert result["metrics"]["liability_ratio"] == 0.4
    assert result["metrics"]["roe_proxy"] == 0.2
    assert result["quality_flags"] == ["operating_cash_flow_below_net_profit"]
