from pytest import approx
from fastapi.testclient import TestClient

from finresearch.metrics import MetricResult, PricePoint
from finresearch.services.price_analytics import PriceAnalyticsService, select_canonical_price_series


def _prices(
    closes: list[float],
    *,
    symbol: str = "000001",
    source: str = "fixture_price",
    start_id: int = 1,
) -> tuple[PricePoint, ...]:
    return tuple(
        PricePoint(start_id + index, symbol, f"2025-01-{index + 1:02d}", close, "qfq", source)
        for index, close in enumerate(closes)
    )


def _by_code(closes: list[float], benchmark: list[float] | None = None) -> dict[str, MetricResult]:
    return {
        result.code: result
        for result in PriceAnalyticsService().calculate(
            _prices(closes),
            _prices(benchmark or [], symbol="000300", start_id=100),
            benchmark_code="000300",
            minimum_observations=5,
            risk_free_rate=0.02,
        )
    }


def test_price_analytics_calculates_returns_volatility_drawdown_and_lineage() -> None:
    by_code = _by_code([10.0, 11.0, 12.0, 9.0, 10.0, 12.0, 15.0])

    assert by_code["return_1d"].value == approx(0.25)
    assert by_code["return_5d"].value == approx(15.0 / 11.0 - 1)
    assert by_code["annualized_volatility"].value is not None
    assert by_code["maximum_drawdown"].value == approx(-0.25)
    assert by_code["maximum_drawdown"].input_values["drawdown_start"] == "2025-01-03"
    assert by_code["return_1d"].source_price_ids == (1, 2, 3, 4, 5, 6, 7)


def test_price_analytics_requires_aligned_benchmark_returns_for_beta_and_alpha() -> None:
    by_code = _by_code(
        [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0],
        [20.0, 20.5, 21.0, 21.8, 22.6, 23.0, 24.0],
    )

    assert by_code["beta"].value is not None
    assert by_code["alpha"].value is not None
    assert by_code["beta"].benchmark_code == "000300"
    assert by_code["alpha"].observations_count == 6


def test_price_analytics_rejects_zero_benchmark_variance() -> None:
    by_code = _by_code(
        [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0],
        [20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0],
    )

    assert by_code["beta"].value is None
    assert by_code["beta"].missing_reason == "zero_benchmark_variance"
    assert by_code["alpha"].missing_reason == "zero_benchmark_variance"


def test_price_analytics_reports_insufficient_price_history() -> None:
    by_code = _by_code([10.0, 11.0])

    assert by_code["return_5d"].missing_reason == "insufficient_price_history"
    assert by_code["annualized_volatility"].missing_reason == "insufficient_price_history"
    assert by_code["beta"].missing_reason == "insufficient_price_history"


def test_canonical_price_series_selects_configured_adjustment_from_mixed_qfq_hfq_none() -> None:
    prices = _prices([10.0, 11.0, 12.0]) + tuple(
        PricePoint(10 + index, "000001", f"2025-01-{index + 1:02d}", close, adjustment, "fixture_price")
        for index, (close, adjustment) in enumerate([(9.0, "hfq"), (8.0, "none")])
    )

    selected = select_canonical_price_series(
        prices,
        symbol="000001",
        adjustment_type="qfq",
        source_priority=("fixture_price",),
    )

    assert selected.missing_reason is None
    assert selected.adjustment_type == "qfq"
    assert {point.adjustment_type for point in selected.prices} == {"qfq"}


def test_canonical_price_series_uses_source_priority_for_same_date_multi_source() -> None:
    prices = (
        PricePoint(1, "000001", "2025-01-01", 10.0, "qfq", "secondary"),
        PricePoint(2, "000001", "2025-01-01", 12.0, "qfq", "primary"),
        PricePoint(3, "000001", "2025-01-02", 13.0, "qfq", "primary"),
        PricePoint(4, "000001", "2025-01-02", 11.0, "qfq", "secondary"),
    )

    selected = select_canonical_price_series(
        prices,
        symbol="000001",
        adjustment_type="qfq",
        source_priority=("primary", "secondary"),
    )

    assert selected.data_source == "primary"
    assert [point.id for point in selected.prices] == [2, 3]
    assert selected.selected_source_reason.startswith("source_priority:primary")


def test_canonical_price_series_rejects_duplicate_dates_within_selected_source() -> None:
    selected = select_canonical_price_series(
        (
            PricePoint(1, "000001", "2025-01-01", 10.0, "qfq", "fixture_price"),
            PricePoint(2, "000001", "2025-01-01", 11.0, "qfq", "fixture_price"),
        ),
        symbol="000001",
        adjustment_type="qfq",
        source_priority=("fixture_price",),
    )

    assert selected.missing_reason == "ambiguous_price_series"
    assert selected.selected_source_reason == "duplicate_trade_date"


def test_canonical_price_series_rejects_zero_and_negative_prices() -> None:
    zero = select_canonical_price_series(
        (PricePoint(1, "000001", "2025-01-01", 0.0, "qfq", "fixture_price"),),
        symbol="000001",
        adjustment_type="qfq",
        source_priority=("fixture_price",),
    )
    negative = select_canonical_price_series(
        (PricePoint(1, "000001", "2025-01-01", -1.0, "qfq", "fixture_price"),),
        symbol="000001",
        adjustment_type="qfq",
        source_priority=("fixture_price",),
    )

    assert zero.missing_reason == "ambiguous_price_series"
    assert negative.missing_reason == "ambiguous_price_series"


def test_price_analytics_returns_canonical_metadata_for_normal_qfq_series() -> None:
    selected = select_canonical_price_series(
        _prices([10.0, 11.0, 12.0], source="fixture_price"),
        symbol="000001",
        adjustment_type="qfq",
        source_priority=("fixture_price",),
    )
    by_code = {
        result.code: result
        for result in PriceAnalyticsService().calculate(selected.prices, minimum_observations=2)
    }

    assert by_code["return_1d"].adjustment_type == "qfq"
    assert by_code["return_1d"].price_source == "fixture_price"
    assert by_code["return_1d"].observations_count == 3


def test_metrics_api_uses_selected_adjustment_and_source(tmp_path, monkeypatch) -> None:
    from app.models import PriceRecord
    from finresearch.api.main import app
    from finresearch.repositories.prices import PriceRepository

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")
    monkeypatch.setenv("CN_STOCK_ADJUSTMENT_TYPE", "qfq")
    monkeypatch.setenv("PRICE_SOURCE_PRIORITY", "primary,secondary")
    PriceRepository().upsert_many(
        [
            PriceRecord(symbol="000001", trade_date="2025-01-01", close=10.0, adjustment_type="hfq", data_source="primary", retrieved_at="2026-06-26T00:00:00+00:00"),
            PriceRecord(symbol="000001", trade_date="2025-01-01", close=20.0, adjustment_type="qfq", data_source="secondary", retrieved_at="2026-06-26T00:00:00+00:00"),
            PriceRecord(symbol="000001", trade_date="2025-01-01", close=11.0, adjustment_type="qfq", data_source="primary", retrieved_at="2026-06-26T00:00:00+00:00"),
            PriceRecord(symbol="000001", trade_date="2025-01-02", close=12.0, adjustment_type="qfq", data_source="primary", retrieved_at="2026-06-26T00:00:00+00:00"),
        ]
    )
    client = TestClient(app)

    response = client.get("/v1/companies/000001/metrics")

    assert response.status_code == 200
    by_code = {item["code"]: item for item in response.json()}
    assert by_code["return_1d"]["adjustment_type"] == "qfq"
    assert by_code["return_1d"]["data_source"] == "primary"
    assert by_code["return_1d"]["source_price_ids"]
    assert by_code["return_1d"]["selected_source_reason"].startswith("source_priority:primary")
