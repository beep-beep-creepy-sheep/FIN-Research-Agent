from pytest import approx

from finresearch.metrics import MetricResult, PricePoint
from finresearch.services.price_analytics import PriceAnalyticsService


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
