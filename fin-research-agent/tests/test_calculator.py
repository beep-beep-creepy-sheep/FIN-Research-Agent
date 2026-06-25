from app.calculator import calculate_ratios
from app.models import FinancialInputs


def test_calculate_ratios() -> None:
    result = calculate_ratios(
        FinancialInputs(
            revenue=100,
            gross_profit=40,
            net_profit=10,
            operating_cash_flow=12,
            capital_expenditure=4,
            equity_begin=50,
            equity_end=70,
            interest_bearing_debt=30,
            cash=8,
        )
    )
    assert result["gross_margin"] == 0.4
    assert result["net_margin"] == 0.1
    assert result["cash_conversion"] == 1.2
    assert result["roe"] == 10 / 60
    assert result["free_cash_flow"] == 8
    assert result["net_debt"] == 22
