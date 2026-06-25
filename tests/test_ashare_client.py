import builtins

import pytest

from app.ashare_client import AShareDataClient, AShareDataError, normalize_financial_rows


def test_normalize_financial_rows_maps_common_metrics() -> None:
    rows = [
        {
            "报告期": "2024-12-31",
            "公告日期": "2025-04-01",
            "营业收入": "1000",
            "净利润": "120",
            "经营活动产生的现金流量净额": "150",
        }
    ]

    facts = normalize_financial_rows(
        rows,
        symbol="600519",
        years=5,
        statement_type="profit_sheet",
        data_source="akshare",
    )

    by_code = {fact.metric_code: fact for fact in facts}
    assert by_code["revenue"].value == 1000.0
    assert by_code["net_profit"].publication_date == "2025-04-01"
    assert by_code["operating_cash_flow"].report_type == "annual"
    assert by_code["revenue"].data_source == "akshare"


def test_ashare_missing_dependency_has_actionable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "akshare":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(AShareDataError, match="pip install akshare"):
        AShareDataClient().fetch_prices("600519")
