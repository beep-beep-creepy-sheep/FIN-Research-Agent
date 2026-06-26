from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable

from finresearch.metrics.context import FLOW_METRICS, FinancialPeriod

FLOW_BASIS_CUMULATIVE_YTD = "cumulative_ytd"
FLOW_BASIS_SINGLE_QUARTER = "single_quarter"
FLOW_BASIS_ANNUAL = "annual"
FLOW_BASIS_UNKNOWN = "unknown"
FLOW_BASIS_AMBIGUOUS = "ambiguous_flow_basis"
KNOWN_FLOW_BASES = {
    FLOW_BASIS_CUMULATIVE_YTD,
    FLOW_BASIS_SINGLE_QUARTER,
    FLOW_BASIS_ANNUAL,
    FLOW_BASIS_UNKNOWN,
    FLOW_BASIS_AMBIGUOUS,
}


@dataclass(frozen=True, order=True)
class QuarterKey:
    year: int
    quarter: int

    @property
    def end_date(self) -> str:
        month_day = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}[self.quarter]
        return f"{self.year}-{month_day}"

    @property
    def start_date(self) -> str:
        month_day = {1: "01-01", 2: "04-01", 3: "07-01", 4: "10-01"}[self.quarter]
        return f"{self.year}-{month_day}"

    def previous(self) -> "QuarterKey":
        if self.quarter == 1:
            return QuarterKey(self.year - 1, 4)
        return QuarterKey(self.year, self.quarter - 1)

    def previous_year(self) -> "QuarterKey":
        return QuarterKey(self.year - 1, self.quarter)


@dataclass(frozen=True)
class NormalizedQuarter:
    key: QuarterKey
    symbol: str
    period_start: str
    period_end: str
    currency: str | None
    values: dict[str, float]
    fact_ids_by_metric: dict[str, tuple[int, ...]]
    source_urls_by_metric: dict[str, tuple[str, ...]]
    formulas_by_metric: dict[str, str]
    warnings: tuple[str, ...] = ()

    def value(self, *codes: str) -> float | None:
        for code in codes:
            if code in self.values:
                return self.values[code]
        return None

    def fact_ids(self, *codes: str) -> tuple[int, ...]:
        ids: list[int] = []
        for code in codes:
            ids.extend(self.fact_ids_by_metric.get(code, ()))
        return tuple(dict.fromkeys(ids))

    def source_urls(self, *codes: str) -> tuple[str, ...]:
        urls: list[str] = []
        for code in codes:
            urls.extend(self.source_urls_by_metric.get(code, ()))
        return tuple(dict.fromkeys(urls))


@dataclass(frozen=True)
class PeriodNormalizationResult:
    quarters: tuple[NormalizedQuarter, ...]
    warnings: tuple[str, ...] = ()


class PeriodNormalizationService:
    def normalize(self, periods: tuple[FinancialPeriod, ...]) -> PeriodNormalizationResult:
        if not periods:
            return PeriodNormalizationResult(quarters=(), warnings=("missing_structured_financial_facts",))
        currencies = {period.currency for period in periods if period.currency}
        if len(currencies) > 1:
            return PeriodNormalizationResult(quarters=(), warnings=("currency_mismatch",))
        candidates = self._latest_by_quarter_and_basis(periods)
        quarters: dict[QuarterKey, NormalizedQuarter] = {}
        warnings: list[str] = []
        for key in sorted(candidates):
            period_candidates = candidates[key]
            current = _best_period(period_candidates.values())
            values: dict[str, float] = {}
            fact_ids: dict[str, tuple[int, ...]] = {}
            urls: dict[str, tuple[str, ...]] = {}
            formulas: dict[str, str] = {}
            previous_candidates = candidates.get(key.previous(), {})
            previous_cumulative = _cumulative_period(previous_candidates)
            codes = {
                code
                for period in period_candidates.values()
                for code in period.values
            }
            for code in codes:
                if code in FLOW_METRICS:
                    quarter_value, metric_fact_ids, metric_urls, formula = self._flow_quarter_value(
                        code, key, period_candidates, previous_cumulative
                    )
                    if quarter_value is None:
                        if formula == FLOW_BASIS_AMBIGUOUS:
                            warnings.append(f"ambiguous_flow_basis:{key.end_date}:{code}")
                        continue
                    values[code] = quarter_value
                    fact_ids[code] = metric_fact_ids
                    urls[code] = metric_urls
                    formulas[code] = formula
                else:
                    value = current.value(code)
                    if value is None:
                        continue
                    values[code] = value
                    fact_ids[code] = current.fact_ids(code)
                    urls[code] = current.source_urls(code)
                    formulas[code] = f"{code} point-in-time from {current.period_end}"
            quarters[key] = NormalizedQuarter(
                key=key,
                symbol=current.symbol,
                period_start=key.start_date,
                period_end=key.end_date,
                currency=current.currency,
                values=values,
                fact_ids_by_metric=fact_ids,
                source_urls_by_metric=urls,
                formulas_by_metric=formulas,
            )
        return PeriodNormalizationResult(
            quarters=tuple(quarters[key] for key in sorted(quarters)),
            warnings=tuple(warnings),
        )

    def ttm(
        self,
        quarters: tuple[NormalizedQuarter, ...],
        metric_code: str,
        *,
        as_of_period_end: str | None = None,
    ) -> tuple[float | None, tuple[NormalizedQuarter, ...], str | None]:
        available = [quarter for quarter in quarters if metric_code in quarter.values]
        if as_of_period_end:
            available = [quarter for quarter in available if quarter.period_end <= as_of_period_end]
        if len(available) < 4:
            return None, tuple(), "insufficient_contiguous_quarters"
        latest = available[-1]
        needed: list[QuarterKey] = [latest.key]
        for _ in range(3):
            needed.append(needed[-1].previous())
        needed = list(reversed(needed))
        by_key = {quarter.key: quarter for quarter in available}
        if any(key not in by_key for key in needed):
            return None, tuple(), "insufficient_contiguous_quarters"
        selected = tuple(by_key[key] for key in needed)
        return sum(quarter.values[metric_code] for quarter in selected), selected, None

    def yoy(
        self,
        periods: tuple[FinancialPeriod, ...],
        quarters: tuple[NormalizedQuarter, ...],
        metric_code: str,
    ) -> tuple[float | None, tuple[int, ...], str | None]:
        annual = [period for period in periods if _quarter_from_period_end(period.period_end) == 4 and period.report_type == "annual"]
        annual = [period for period in annual if metric_code in period.values]
        if annual:
            latest = sorted(annual, key=lambda period: period.period_end)[-1]
            previous = next(
                (
                    period
                    for period in annual
                    if period.period_end.startswith(str(int(latest.period_end[:4]) - 1))
                ),
                None,
            )
            if previous is None:
                return None, latest.fact_ids(metric_code), "missing_comparable_period"
            denominator = previous.values[metric_code]
            if denominator == 0:
                return None, latest.fact_ids(metric_code) + previous.fact_ids(metric_code), "zero_denominator"
            return (
                latest.values[metric_code] / denominator - 1,
                latest.fact_ids(metric_code) + previous.fact_ids(metric_code),
                None,
            )
        quarter_rows = [quarter for quarter in quarters if metric_code in quarter.values]
        if not quarter_rows:
            return None, tuple(), "missing_input"
        latest_q = quarter_rows[-1]
        previous_q = next(
            (quarter for quarter in quarter_rows if quarter.key == latest_q.key.previous_year()),
            None,
        )
        if previous_q is None:
            return None, latest_q.fact_ids(metric_code), "missing_comparable_period"
        denominator = previous_q.values[metric_code]
        if denominator == 0:
            return None, latest_q.fact_ids(metric_code) + previous_q.fact_ids(metric_code), "zero_denominator"
        return (
            latest_q.values[metric_code] / denominator - 1,
            latest_q.fact_ids(metric_code) + previous_q.fact_ids(metric_code),
            None,
        )

    def _latest_by_quarter_and_basis(
        self,
        periods: tuple[FinancialPeriod, ...],
    ) -> dict[QuarterKey, dict[str, FinancialPeriod]]:
        by_key: dict[QuarterKey, dict[str, FinancialPeriod]] = {}
        for period in periods:
            quarter = _quarter_from_period_end(period.period_end)
            if quarter is None:
                continue
            key = QuarterKey(int(period.period_end[:4]), quarter)
            basis = _flow_basis(period)
            current = by_key.setdefault(key, {}).get(basis)
            if current is None or _period_rank(period) > _period_rank(current):
                by_key[key][basis] = period
        return by_key

    def _flow_quarter_value(
        self,
        code: str,
        key: QuarterKey,
        candidates: dict[str, FinancialPeriod],
        previous_cumulative: FinancialPeriod | None,
    ) -> tuple[float | None, tuple[int, ...], tuple[str, ...], str]:
        current = candidates.get(FLOW_BASIS_SINGLE_QUARTER)
        if current is not None and current.value(code) is not None:
            current_value = current.value(code)
            if current_value is None:
                return None, tuple(), tuple(), f"{code} missing"
            return (
                current_value,
                current.fact_ids(code),
                current.source_urls(code),
                f"{code} Q{key.quarter} = source single quarter",
            )

        current = _cumulative_period(candidates)
        if current is None:
            ambiguous = candidates.get(FLOW_BASIS_UNKNOWN) or candidates.get(FLOW_BASIS_AMBIGUOUS)
            if ambiguous is not None and ambiguous.value(code) is not None:
                return (
                    None,
                    ambiguous.fact_ids(code),
                    ambiguous.source_urls(code),
                    FLOW_BASIS_AMBIGUOUS,
                )
            return None, tuple(), tuple(), f"{code} missing"
        current_value = current.value(code)
        if current_value is None:
            return None, tuple(), tuple(), f"{code} missing"
        if key.quarter == 1:
            return (
                current_value,
                current.fact_ids(code),
                current.source_urls(code),
                f"{code} Q1 = Q1 {current.flow_basis or _flow_basis(current)}",
            )
        if previous_cumulative is None:
            return None, current.fact_ids(code), current.source_urls(code), "missing_previous_cumulative"
        previous_value = previous_cumulative.value(code)
        if previous_value is None:
            return None, current.fact_ids(code), current.source_urls(code), "missing_previous_cumulative_metric"
        return (
            current_value - previous_value,
            current.fact_ids(code) + previous_cumulative.fact_ids(code),
            current.source_urls(code) + previous_cumulative.source_urls(code),
            f"{code} Q{key.quarter} = {current.period_end} {current.flow_basis or _flow_basis(current)} - {previous_cumulative.period_end} cumulative",
        )


def _quarter_from_period_end(period_end: str) -> int | None:
    if period_end.endswith("-03-31"):
        return 1
    if period_end.endswith("-06-30"):
        return 2
    if period_end.endswith("-09-30"):
        return 3
    if period_end.endswith("-12-31"):
        return 4
    return None


def _flow_basis(period: FinancialPeriod) -> str:
    explicit = (period.flow_basis or period.source_flow_basis or "").strip().lower()
    if explicit in KNOWN_FLOW_BASES:
        return explicit
    if period.is_cumulative is True:
        if period.report_type == "annual" or period.period_end.endswith("-12-31"):
            return FLOW_BASIS_ANNUAL
        return FLOW_BASIS_CUMULATIVE_YTD
    if period.is_cumulative is False:
        return FLOW_BASIS_SINGLE_QUARTER
    if period.report_type == "annual":
        return FLOW_BASIS_ANNUAL
    if not period.period_start:
        return FLOW_BASIS_UNKNOWN
    year = period.period_end[:4]
    if period.period_start == f"{year}-01-01":
        if period.period_end.endswith("-03-31"):
            return FLOW_BASIS_CUMULATIVE_YTD
        if period.period_end.endswith(("-06-30", "-09-30")):
            return FLOW_BASIS_CUMULATIVE_YTD
        if period.period_end.endswith("-12-31"):
            return FLOW_BASIS_ANNUAL
    if period.period_start == f"{year}-04-01" and period.period_end.endswith("-06-30"):
        return FLOW_BASIS_SINGLE_QUARTER
    if period.period_start == f"{year}-07-01" and period.period_end.endswith("-09-30"):
        return FLOW_BASIS_SINGLE_QUARTER
    if period.period_start == f"{year}-10-01" and period.period_end.endswith("-12-31"):
        return FLOW_BASIS_SINGLE_QUARTER
    return FLOW_BASIS_UNKNOWN


def _cumulative_period(candidates: dict[str, FinancialPeriod]) -> FinancialPeriod | None:
    return candidates.get(FLOW_BASIS_CUMULATIVE_YTD) or candidates.get(FLOW_BASIS_ANNUAL)


def _best_period(periods: Iterable[FinancialPeriod]) -> FinancialPeriod:
    return sorted(periods, key=_period_rank)[-1]


def _period_rank(period: FinancialPeriod) -> tuple[str, int, str]:
    return (
        period.publication_date or "",
        period.version or 0,
        period.data_source or "",
    )
