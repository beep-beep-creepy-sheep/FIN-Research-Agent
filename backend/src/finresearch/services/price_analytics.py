from __future__ import annotations

import os
from dataclasses import dataclass, replace
from math import sqrt
from statistics import fmean, stdev

from finresearch.metrics.context import MetricResult, PricePoint
from finresearch.settings import get_settings


PRICE_METRIC_CODES = (
    "return_1d",
    "return_5d",
    "return_20d",
    "return_60d",
    "return_ytd",
    "annualized_volatility",
    "downside_volatility",
    "maximum_drawdown",
    "beta",
    "alpha",
    "r_squared",
    "tracking_error",
    "information_ratio",
    "sharpe_ratio",
    "sortino_ratio",
)
TEST_PRICE_SOURCES = frozenset({"fixture_price", "test"})


@dataclass(frozen=True)
class DrawdownDetail:
    value: float
    start_date: str | None
    trough_date: str | None
    recovery_date: str | None
    duration: int


@dataclass(frozen=True)
class CanonicalPriceSeries:
    prices: tuple[PricePoint, ...]
    adjustment_type: str | None
    data_source: str | None
    selected_source_reason: str
    missing_reason: str | None = None

    @property
    def observations_count(self) -> int:
        return len(self.prices)


def select_canonical_price_series(
    price_series: tuple[PricePoint, ...],
    *,
    symbol: str,
    adjustment_type: str | None = None,
    source_priority: tuple[str, ...] | None = None,
) -> CanonicalPriceSeries:
    if not price_series:
        return CanonicalPriceSeries(tuple(), adjustment_type, None, "no_price_observations", "missing_price_series")
    symbols = {point.symbol for point in price_series}
    if symbols != {symbol}:
        return CanonicalPriceSeries(tuple(), adjustment_type, None, "symbol_mismatch", "ambiguous_price_series")
    if any(point.close <= 0 for point in price_series):
        return CanonicalPriceSeries(tuple(), adjustment_type, None, "non_positive_close", "ambiguous_price_series")

    configured_adjustment = adjustment_type or get_settings().cn_stock_adjustment_type
    adjustment_candidates = tuple(point for point in price_series if point.adjustment_type == configured_adjustment)
    if not adjustment_candidates:
        return CanonicalPriceSeries(
            tuple(),
            configured_adjustment,
            None,
            f"configured_adjustment_type_not_found:{configured_adjustment}",
            "ambiguous_price_series",
        )

    priority = source_priority or get_settings().price_source_priority
    allow_test_sources = _test_price_sources_allowed()
    blocked_sources = {source for source in priority if source in TEST_PRICE_SOURCES}
    if not allow_test_sources:
        priority = tuple(source for source in priority if source not in TEST_PRICE_SOURCES)
        adjustment_candidates = tuple(
            point for point in adjustment_candidates if point.data_source not in TEST_PRICE_SOURCES
        )
        if not adjustment_candidates:
            reason = "test_price_sources_disabled"
            if blocked_sources:
                reason = f"{reason}:{','.join(sorted(blocked_sources))}"
            return CanonicalPriceSeries(tuple(), configured_adjustment, None, reason, "test_price_sources_disabled")

    sources = {point.data_source for point in adjustment_candidates}
    selected_source = next((source for source in priority if source in sources), None)
    reason = "source_priority"
    if selected_source is None:
        if len(sources) != 1:
            return CanonicalPriceSeries(
                tuple(),
                configured_adjustment,
                None,
                "source_priority_no_match",
                "ambiguous_price_series",
            )
        selected_source = next(iter(sources))
        reason = "single_available_source"

    selected = tuple(point for point in adjustment_candidates if point.data_source == selected_source)
    validation_reason = validate_price_series(selected)
    if validation_reason is not None:
        return CanonicalPriceSeries(tuple(), configured_adjustment, selected_source, validation_reason, "ambiguous_price_series")
    return CanonicalPriceSeries(
        tuple(sorted(selected, key=lambda point: point.trade_date)),
        configured_adjustment,
        selected_source,
        f"{reason}:{selected_source};adjustment_type:{configured_adjustment}",
    )


def _test_price_sources_allowed() -> bool:
    if "PYTEST_CURRENT_TEST" in os.environ:
        return True
    if os.getenv("APP_ENV", "").strip().lower() == "test":
        return True
    return os.getenv("ALLOW_TEST_DATA_SOURCES", "").strip().lower() == "true"


def validate_price_series(prices: tuple[PricePoint, ...]) -> str | None:
    if not prices:
        return "missing_price_series"
    if len({point.symbol for point in prices}) != 1:
        return "symbol_mismatch"
    if len({point.adjustment_type for point in prices}) != 1:
        return "mixed_adjustment_type"
    if len({point.data_source for point in prices}) != 1:
        return "mixed_data_source"
    ordered = tuple(sorted(prices, key=lambda point: point.trade_date))
    dates = [point.trade_date for point in ordered]
    if len(dates) != len(set(dates)):
        return "duplicate_trade_date"
    if dates != sorted(dates):
        return "trade_date_not_increasing"
    if any(point.close <= 0 for point in ordered):
        return "non_positive_close"
    return None


class PriceAnalyticsService:
    def calculate(
        self,
        price_series: tuple[PricePoint, ...],
        benchmark_series: tuple[PricePoint, ...] = (),
        *,
        benchmark_code: str | None = None,
        trading_days_per_year: int = 252,
        risk_free_rate: float = 0.0,
        minimum_observations: int = 20,
    ) -> list[MetricResult]:
        prices = tuple(sorted(price_series, key=lambda point: point.trade_date))
        validation_reason = validate_price_series(prices)
        if validation_reason is not None:
            return _missing_price_metrics(validation_reason, prices)
        returns = _returns(prices)
        results = [
            self._period_return("return_1d", prices, 1),
            self._period_return("return_5d", prices, 5),
            self._period_return("return_20d", prices, 20),
            self._period_return("return_60d", prices, 60),
            self._ytd_return(prices),
            self._volatility("annualized_volatility", returns, trading_days_per_year, minimum_observations),
            self._downside_volatility(returns, trading_days_per_year, minimum_observations),
            self._maximum_drawdown(prices),
            self._sharpe_ratio(returns, trading_days_per_year, risk_free_rate, minimum_observations),
            self._sortino_ratio(returns, trading_days_per_year, risk_free_rate, minimum_observations),
        ]
        aligned = _aligned_returns(prices, tuple(sorted(benchmark_series, key=lambda point: point.trade_date)))
        results.extend(
            [
                self._beta(aligned, benchmark_code, minimum_observations),
                self._alpha(aligned, benchmark_code, trading_days_per_year, risk_free_rate, minimum_observations),
                self._r_squared(aligned, benchmark_code, minimum_observations),
                self._tracking_error(aligned, benchmark_code, trading_days_per_year, minimum_observations),
                self._information_ratio(aligned, benchmark_code, trading_days_per_year, minimum_observations),
            ]
        )
        return [_with_price_metadata(result, prices) for result in results]

    def _period_return(self, code: str, prices: tuple[PricePoint, ...], days: int) -> MetricResult:
        if len(prices) <= days:
            return _missing_price(code, "insufficient_price_history", prices, observations=len(prices))
        start = prices[-days - 1]
        end = prices[-1]
        value = end.close / start.close - 1
        return _price_result(
            code,
            value,
            f"adjusted_close_t / adjusted_close_t_minus_{days} - 1",
            prices,
            start_date=start.trade_date,
            observations=len(prices),
        )

    def _ytd_return(self, prices: tuple[PricePoint, ...]) -> MetricResult:
        if len(prices) < 2:
            return _missing_price("return_ytd", "insufficient_price_history", prices, observations=len(prices))
        year = prices[-1].trade_date[:4]
        year_prices = [point for point in prices if point.trade_date.startswith(year)]
        if len(year_prices) < 2:
            return _missing_price("return_ytd", "insufficient_price_history", prices, observations=len(year_prices))
        return _price_result(
            "return_ytd",
            year_prices[-1].close / year_prices[0].close - 1,
            "adjusted_close_latest / first_adjusted_close_of_year - 1",
            prices,
            start_date=year_prices[0].trade_date,
            observations=len(year_prices),
        )

    def _volatility(
        self,
        code: str,
        returns: tuple[tuple[str, float], ...],
        trading_days_per_year: int,
        minimum_observations: int,
    ) -> MetricResult:
        if len(returns) < minimum_observations:
            return _missing_price(code, "insufficient_price_history", tuple(), observations=len(returns))
        value = stdev([row[1] for row in returns]) * sqrt(trading_days_per_year)
        return _return_result(
            code,
            value,
            "sample_stddev(daily_returns) * sqrt(trading_days_per_year)",
            returns,
            assumptions={"trading_days_per_year": trading_days_per_year},
        )

    def _downside_volatility(
        self,
        returns: tuple[tuple[str, float], ...],
        trading_days_per_year: int,
        minimum_observations: int,
    ) -> MetricResult:
        downside = tuple(row for row in returns if row[1] < 0)
        if len(returns) < minimum_observations or len(downside) < 2:
            return _missing_price("downside_volatility", "insufficient_price_history", tuple(), observations=len(returns))
        value = stdev([row[1] for row in downside]) * sqrt(trading_days_per_year)
        return _return_result(
            "downside_volatility",
            value,
            "sample_stddev(negative_daily_returns) * sqrt(trading_days_per_year)",
            returns,
            assumptions={"trading_days_per_year": trading_days_per_year},
        )

    def _maximum_drawdown(self, prices: tuple[PricePoint, ...]) -> MetricResult:
        if len(prices) < 2:
            return _missing_price("maximum_drawdown", "insufficient_price_history", prices, observations=len(prices))
        detail = _drawdown(prices)
        return _price_result(
            "maximum_drawdown",
            detail.value,
            "min(value_t / running_max_t - 1)",
            prices,
            start_date=detail.start_date,
            observations=len(prices),
            inputs={
                "drawdown_start": detail.start_date,
                "drawdown_trough": detail.trough_date,
                "recovery_date": detail.recovery_date,
                "drawdown_duration": detail.duration,
            },
        )

    def _beta(
        self,
        aligned: tuple[tuple[str, float, float], ...],
        benchmark_code: str | None,
        minimum_observations: int,
    ) -> MetricResult:
        if len(aligned) < minimum_observations:
            return _missing_benchmark("beta", "insufficient_price_history", benchmark_code, len(aligned))
        benchmark_returns = [row[2] for row in aligned]
        variance = _variance(benchmark_returns)
        if variance == 0:
            return _missing_benchmark("beta", "zero_benchmark_variance", benchmark_code, len(aligned))
        stock_returns = [row[1] for row in aligned]
        beta = _covariance(stock_returns, benchmark_returns) / variance
        return _benchmark_result("beta", beta, "cov(stock_return, benchmark_return) / var(benchmark_return)", aligned, benchmark_code)

    def _alpha(
        self,
        aligned: tuple[tuple[str, float, float], ...],
        benchmark_code: str | None,
        trading_days_per_year: int,
        risk_free_rate: float,
        minimum_observations: int,
    ) -> MetricResult:
        beta = self._beta(aligned, benchmark_code, minimum_observations)
        if beta.value is None:
            return _missing_benchmark("alpha", beta.missing_reason or "missing_beta", benchmark_code, len(aligned))
        stock_annual = _annualized_return([row[1] for row in aligned], trading_days_per_year)
        benchmark_annual = _annualized_return([row[2] for row in aligned], trading_days_per_year)
        alpha = stock_annual - (risk_free_rate + beta.value * (benchmark_annual - risk_free_rate))
        return _benchmark_result(
            "alpha",
            alpha,
            "annualized_stock_return - (risk_free_rate + beta * (annualized_benchmark_return - risk_free_rate))",
            aligned,
            benchmark_code,
            assumptions={
                "risk_free_rate": risk_free_rate,
                "beta": beta.value,
                "trading_days_per_year": trading_days_per_year,
                "annualization": "geometric_daily_returns",
            },
        )

    def _r_squared(
        self,
        aligned: tuple[tuple[str, float, float], ...],
        benchmark_code: str | None,
        minimum_observations: int,
    ) -> MetricResult:
        if len(aligned) < minimum_observations:
            return _missing_benchmark("r_squared", "insufficient_price_history", benchmark_code, len(aligned))
        corr = _correlation([row[1] for row in aligned], [row[2] for row in aligned])
        if corr is None:
            return _missing_benchmark("r_squared", "zero_variance", benchmark_code, len(aligned))
        return _benchmark_result("r_squared", corr * corr, "corr(stock_return, benchmark_return) ** 2", aligned, benchmark_code)

    def _tracking_error(
        self,
        aligned: tuple[tuple[str, float, float], ...],
        benchmark_code: str | None,
        trading_days_per_year: int,
        minimum_observations: int,
    ) -> MetricResult:
        if len(aligned) < minimum_observations:
            return _missing_benchmark("tracking_error", "insufficient_price_history", benchmark_code, len(aligned))
        active = [row[1] - row[2] for row in aligned]
        return _benchmark_result(
            "tracking_error",
            stdev(active) * sqrt(trading_days_per_year),
            "sample_stddev(stock_return - benchmark_return) * sqrt(trading_days_per_year)",
            aligned,
            benchmark_code,
            assumptions={"trading_days_per_year": trading_days_per_year},
        )

    def _information_ratio(
        self,
        aligned: tuple[tuple[str, float, float], ...],
        benchmark_code: str | None,
        trading_days_per_year: int,
        minimum_observations: int,
    ) -> MetricResult:
        tracking_error = self._tracking_error(aligned, benchmark_code, trading_days_per_year, minimum_observations)
        if tracking_error.value in (None, 0):
            return _missing_benchmark("information_ratio", tracking_error.missing_reason or "zero_tracking_error", benchmark_code, len(aligned))
        active_return = _annualized_return([row[1] - row[2] for row in aligned], trading_days_per_year)
        return _benchmark_result(
            "information_ratio",
            active_return / tracking_error.value,
            "annualized_active_return / tracking_error",
            aligned,
            benchmark_code,
            assumptions={"trading_days_per_year": trading_days_per_year},
        )

    def _sharpe_ratio(
        self,
        returns: tuple[tuple[str, float], ...],
        trading_days_per_year: int,
        risk_free_rate: float,
        minimum_observations: int,
    ) -> MetricResult:
        volatility = self._volatility("annualized_volatility", returns, trading_days_per_year, minimum_observations)
        if volatility.value in (None, 0):
            return _missing_price("sharpe_ratio", volatility.missing_reason or "zero_volatility", tuple(), observations=len(returns))
        annual_return = _annualized_return([row[1] for row in returns], trading_days_per_year)
        return _return_result(
            "sharpe_ratio",
            (annual_return - risk_free_rate) / volatility.value,
            "(annualized_return - risk_free_rate) / annualized_volatility",
            returns,
            assumptions={"risk_free_rate": risk_free_rate, "trading_days_per_year": trading_days_per_year},
        )

    def _sortino_ratio(
        self,
        returns: tuple[tuple[str, float], ...],
        trading_days_per_year: int,
        risk_free_rate: float,
        minimum_observations: int,
    ) -> MetricResult:
        downside = self._downside_volatility(returns, trading_days_per_year, minimum_observations)
        if downside.value in (None, 0):
            return _missing_price("sortino_ratio", downside.missing_reason or "zero_downside_volatility", tuple(), observations=len(returns))
        annual_return = _annualized_return([row[1] for row in returns], trading_days_per_year)
        return _return_result(
            "sortino_ratio",
            (annual_return - risk_free_rate) / downside.value,
            "(annualized_return - risk_free_rate) / downside_volatility",
            returns,
            assumptions={"risk_free_rate": risk_free_rate, "trading_days_per_year": trading_days_per_year},
        )


def _returns(prices: tuple[PricePoint, ...]) -> tuple[tuple[str, float], ...]:
    output: list[tuple[str, float]] = []
    for previous, current in zip(prices, prices[1:]):
        if previous.close == 0:
            continue
        output.append((current.trade_date, current.close / previous.close - 1))
    return tuple(output)


def _aligned_returns(
    prices: tuple[PricePoint, ...],
    benchmark: tuple[PricePoint, ...],
) -> tuple[tuple[str, float, float], ...]:
    stock_returns = dict(_returns(prices))
    benchmark_returns = dict(_returns(benchmark))
    dates = sorted(set(stock_returns).intersection(benchmark_returns))
    return tuple((date, stock_returns[date], benchmark_returns[date]) for date in dates)


def _drawdown(prices: tuple[PricePoint, ...]) -> DrawdownDetail:
    running_max = prices[0].close
    running_max_date = prices[0].trade_date
    worst = 0.0
    start = prices[0].trade_date
    trough = prices[0].trade_date
    recovery: str | None = None
    trough_index = 0
    start_index = 0
    for index, point in enumerate(prices):
        if point.close > running_max:
            running_max = point.close
            running_max_date = point.trade_date
        drawdown = point.close / running_max - 1
        if drawdown < worst:
            worst = drawdown
            start = running_max_date
            trough = point.trade_date
            trough_index = index
            start_index = next(i for i, item in enumerate(prices) if item.trade_date == start)
            recovery = None
        if worst < 0 and recovery is None and index > trough_index and point.close >= running_max:
            recovery = point.trade_date
    return DrawdownDetail(worst, start, trough, recovery, trough_index - start_index)


def _variance(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = fmean(values)
    return sum((value - mean) ** 2 for value in values) / (len(values) - 1)


def _covariance(left: list[float], right: list[float]) -> float:
    mean_left = fmean(left)
    mean_right = fmean(right)
    return sum((a - mean_left) * (b - mean_right) for a, b in zip(left, right)) / (len(left) - 1)


def _correlation(left: list[float], right: list[float]) -> float | None:
    var_left = _variance(left)
    var_right = _variance(right)
    if var_left == 0 or var_right == 0:
        return None
    return _covariance(left, right) / sqrt(var_left * var_right)


def _annualized_return(values: list[float], trading_days_per_year: int) -> float:
    if not values:
        return 0.0
    compounded = 1.0
    for value in values:
        compounded *= 1 + value
    return compounded ** (trading_days_per_year / len(values)) - 1


def _price_result(
    code: str,
    value: float,
    formula: str,
    prices: tuple[PricePoint, ...],
    *,
    start_date: str | None = None,
    observations: int | None = None,
    inputs: dict[str, object] | None = None,
) -> MetricResult:
    return MetricResult(
        code=code,
        value=value,
        unit="ratio",
        formula=formula,
        formula_version="2.0.0",
        input_values=inputs or {},
        source_price_ids=tuple(point.id for point in prices if point.id is not None),
        price_source=prices[-1].data_source if prices else None,
        start_date=start_date or (prices[0].trade_date if prices else None),
        end_date=prices[-1].trade_date if prices else None,
        observations_count=observations,
        adjustment_type=prices[-1].adjustment_type if prices else None,
        selected_source_reason=(
            f"canonical_price_series:{prices[-1].data_source}:{prices[-1].adjustment_type}"
            if prices
            else None
        ),
        assumptions={},
    )


def _return_result(
    code: str,
    value: float,
    formula: str,
    returns: tuple[tuple[str, float], ...],
    *,
    assumptions: dict[str, object] | None = None,
) -> MetricResult:
    return MetricResult(
        code=code,
        value=value,
        unit="ratio",
        formula=formula,
        formula_version="2.0.0",
        start_date=returns[0][0] if returns else None,
        end_date=returns[-1][0] if returns else None,
        observations_count=len(returns),
        assumptions=assumptions or {},
    )


def _benchmark_result(
    code: str,
    value: float,
    formula: str,
    aligned: tuple[tuple[str, float, float], ...],
    benchmark_code: str | None,
    *,
    assumptions: dict[str, object] | None = None,
) -> MetricResult:
    return MetricResult(
        code=code,
        value=value,
        unit="ratio",
        formula=formula,
        formula_version="2.0.0",
        benchmark_code=benchmark_code,
        benchmark_source="benchmark_price_series",
        start_date=aligned[0][0] if aligned else None,
        end_date=aligned[-1][0] if aligned else None,
        observations_count=len(aligned),
        assumptions=assumptions or {},
    )


def _missing_price(
    code: str,
    reason: str,
    prices: tuple[PricePoint, ...],
    *,
    observations: int,
) -> MetricResult:
    return MetricResult(
        code=code,
        value=None,
        quality_status="missing",
        missing_reason=reason,
        source_price_ids=tuple(point.id for point in prices if point.id is not None),
        observations_count=observations,
        adjustment_type=prices[-1].adjustment_type if prices else None,
        price_source=prices[-1].data_source if prices else None,
    )


def _missing_benchmark(
    code: str,
    reason: str,
    benchmark_code: str | None,
    observations: int,
) -> MetricResult:
    return MetricResult(
        code=code,
        value=None,
        quality_status="missing",
        missing_reason=reason,
        benchmark_code=benchmark_code,
        observations_count=observations,
    )


def _missing_price_metrics(reason: str, prices: tuple[PricePoint, ...]) -> list[MetricResult]:
    return [
        _with_price_metadata(_missing_price(code, reason, prices, observations=len(prices)), prices)
        for code in PRICE_METRIC_CODES
    ]


def _with_price_metadata(result: MetricResult, prices: tuple[PricePoint, ...]) -> MetricResult:
    if not prices:
        return result
    return replace(
        result,
        price_source=result.price_source or prices[-1].data_source,
        source_price_ids=result.source_price_ids
        or tuple(point.id for point in prices if point.id is not None),
        adjustment_type=result.adjustment_type or prices[-1].adjustment_type,
        selected_source_reason=result.selected_source_reason
        or f"canonical_price_series:{prices[-1].data_source}:{prices[-1].adjustment_type}",
        observations_count=result.observations_count if result.observations_count is not None else len(prices),
    )
