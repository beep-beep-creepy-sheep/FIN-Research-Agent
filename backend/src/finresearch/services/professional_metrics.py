from __future__ import annotations

from finresearch.metrics.context import CalculationContext, FinancialPeriod, MetricResult, PricePoint
from finresearch.services.period_normalization import NormalizedQuarter, PeriodNormalizationService


NON_OPERATING_FINANCIAL_INDUSTRIES = {"bank", "banks", "insurance", "securities", "brokerage", "银行", "保险", "证券"}


class ProfessionalMetricEngine:
    def __init__(self) -> None:
        self.periods = PeriodNormalizationService()

    def calculate(self, context: CalculationContext) -> list[MetricResult]:
        normalized = self.periods.normalize(context.financial_periods)
        quarters = normalized.quarters
        latest_period = _latest_period(context.financial_periods)
        results = [
            self._ttm("revenue_ttm", "revenue", context, quarters),
            self._ttm("net_profit_ttm", "net_profit_parent", context, quarters, fallback_code="net_profit"),
            self._yoy("revenue_yoy", "revenue", context, quarters),
            self._yoy("net_profit_yoy", "net_profit_parent", context, quarters, fallback_code="net_profit"),
            self._fcf_ttm(context, quarters),
            self._ebitda_ttm(context, quarters),
            self._net_debt(context, latest_period),
            self._enterprise_value(context, latest_period),
        ]
        result_by_code = {result.code: result for result in results}
        results.extend(
            [
                self._fcf_yield(context, result_by_code.get("fcf_ttm"), latest_period),
                self._net_debt_to_ebitda(result_by_code.get("net_debt"), result_by_code.get("ebitda_ttm")),
                self._ev_to_ebitda(context, result_by_code.get("enterprise_value"), result_by_code.get("ebitda_ttm")),
                self._pe_ttm(context, result_by_code.get("net_profit_ttm"), latest_period),
                self._roic(context, quarters, latest_period),
            ]
        )
        return results

    def _ttm(
        self,
        code: str,
        metric_code: str,
        context: CalculationContext,
        quarters: tuple[NormalizedQuarter, ...],
        *,
        fallback_code: str | None = None,
    ) -> MetricResult:
        value, selected, reason = self.periods.ttm(quarters, metric_code)
        used_code = metric_code
        if reason and fallback_code:
            value, selected, reason = self.periods.ttm(quarters, fallback_code)
            used_code = fallback_code
        if reason or value is None:
            return _missing_financial(code, reason or "missing_input", context)
        return _financial_result(
            code,
            value,
            selected[0].period_start,
            selected[-1].period_end,
            context,
            f"{code} = sum({used_code} from four contiguous comparable quarters)",
            {used_code: [quarter.values[used_code] for quarter in selected]},
            _quarter_fact_ids(selected, used_code),
            _quarter_urls(selected, used_code),
            unit="currency",
            currency=selected[-1].currency or context.currency,
        )

    def _yoy(
        self,
        code: str,
        metric_code: str,
        context: CalculationContext,
        quarters: tuple[NormalizedQuarter, ...],
        *,
        fallback_code: str | None = None,
    ) -> MetricResult:
        value, fact_ids, reason = self.periods.yoy(context.financial_periods, quarters, metric_code)
        used_code = metric_code
        if reason and fallback_code:
            value, fact_ids, reason = self.periods.yoy(context.financial_periods, quarters, fallback_code)
            used_code = fallback_code
        latest = _latest_period(context.financial_periods)
        if reason or value is None:
            return _missing_financial(code, reason or "missing_input", context, source_fact_ids=fact_ids)
        return _financial_result(
            code,
            value,
            latest.period_start if latest else None,
            latest.period_end if latest else None,
            context,
            f"{used_code} comparable period / prior comparable period - 1",
            {"metric_code": used_code},
            fact_ids,
            _urls_for_ids(context.financial_periods, fact_ids),
        )

    def _fcf_ttm(
        self,
        context: CalculationContext,
        quarters: tuple[NormalizedQuarter, ...],
    ) -> MetricResult:
        ocf, ocf_q, ocf_reason = self.periods.ttm(quarters, "operating_cash_flow")
        capex, capex_q, capex_reason = self.periods.ttm(quarters, "capital_expenditure")
        if ocf_reason or capex_reason or ocf is None or capex is None:
            return _missing_financial("fcf_ttm", ocf_reason or capex_reason or "missing_input", context)
        capex_outflow = -capex if capex < 0 else capex
        selected = ocf_q or capex_q
        warnings = ("capital_expenditure_positive_treated_as_outflow",) if capex > 0 else ()
        return _financial_result(
            "fcf_ttm",
            ocf - capex_outflow,
            selected[0].period_start,
            selected[-1].period_end,
            context,
            "FCF TTM = TTM operating cash flow - standardized TTM capital expenditure outflow",
            {"operating_cash_flow_ttm": ocf, "capital_expenditure_ttm": capex, "capex_outflow": capex_outflow},
            _quarter_fact_ids(ocf_q, "operating_cash_flow") + _quarter_fact_ids(capex_q, "capital_expenditure"),
            _quarter_urls(ocf_q, "operating_cash_flow") + _quarter_urls(capex_q, "capital_expenditure"),
            unit="currency",
            currency=selected[-1].currency or context.currency,
            warnings=warnings,
        )

    def _ebitda_ttm(
        self,
        context: CalculationContext,
        quarters: tuple[NormalizedQuarter, ...],
    ) -> MetricResult:
        direct, direct_q, direct_reason = self.periods.ttm(quarters, "ebitda")
        if direct_reason is None and direct is not None:
            return _financial_result(
                "ebitda_ttm",
                direct,
                direct_q[0].period_start,
                direct_q[-1].period_end,
                context,
                "EBITDA TTM = sum(direct disclosed EBITDA for four contiguous quarters)",
                {"ebitda_quarters": [quarter.value("ebitda") for quarter in direct_q]},
                _quarter_fact_ids(direct_q, "ebitda"),
                _quarter_urls(direct_q, "ebitda"),
                unit="currency",
                currency=direct_q[-1].currency or context.currency,
            )
        ebit, ebit_q, ebit_reason = self.periods.ttm(quarters, "ebit")
        depreciation, dep_q, dep_reason = self.periods.ttm(quarters, "depreciation")
        amortization, amort_q, amort_reason = self.periods.ttm(quarters, "amortization")
        if ebit_reason or dep_reason or amort_reason or ebit is None or depreciation is None or amortization is None:
            return _missing_financial("ebitda_ttm", "missing_ebit_depreciation_or_amortization", context)
        selected = ebit_q
        return _financial_result(
            "ebitda_ttm",
            ebit + depreciation + amortization,
            selected[0].period_start,
            selected[-1].period_end,
            context,
            "EBITDA TTM = EBIT TTM + depreciation TTM + amortization TTM",
            {"ebit_ttm": ebit, "depreciation_ttm": depreciation, "amortization_ttm": amortization},
            _quarter_fact_ids(ebit_q, "ebit") + _quarter_fact_ids(dep_q, "depreciation") + _quarter_fact_ids(amort_q, "amortization"),
            _quarter_urls(ebit_q, "ebit") + _quarter_urls(dep_q, "depreciation") + _quarter_urls(amort_q, "amortization"),
            unit="currency",
            currency=selected[-1].currency or context.currency,
        )

    def _net_debt(self, context: CalculationContext, latest: FinancialPeriod | None) -> MetricResult:
        if latest is None:
            return _missing_financial("net_debt", "missing_structured_financial_facts", context)
        debt = latest.value("interest_bearing_debt", "total_debt")
        cash = latest.value("cash_and_equivalents", "cash")
        if debt is None or cash is None:
            return _missing_financial("net_debt", "missing_debt_or_cash", context)
        return _financial_result(
            "net_debt",
            debt - cash,
            latest.period_start,
            latest.period_end,
            context,
            "Net Debt = interest-bearing debt - cash and cash equivalents",
            {"interest_bearing_debt": debt, "cash_and_equivalents": cash},
            latest.fact_ids("interest_bearing_debt", "total_debt", "cash_and_equivalents", "cash"),
            latest.source_urls("interest_bearing_debt", "total_debt", "cash_and_equivalents", "cash"),
            unit="currency",
            currency=latest.currency or context.currency,
        )

    def _enterprise_value(self, context: CalculationContext, latest: FinancialPeriod | None) -> MetricResult:
        market_cap, market_inputs, market_fact_ids, price_ids, price_source, price_date, reason = _market_cap(context, latest)
        if market_cap is None:
            return _missing_financial("enterprise_value", reason or "missing_market_cap", context)
        debt = latest.value("interest_bearing_debt", "total_debt") if latest else None
        cash = latest.value("cash_and_equivalents", "cash") if latest else None
        if latest is None or debt is None or cash is None:
            return _missing_financial("enterprise_value", "missing_debt_or_cash", context)
        preferred = latest.value("preferred_equity")
        minority = latest.value("non_controlling_interest", "minority_interest")
        warnings = []
        if preferred is None:
            preferred = 0.0
            warnings.append("preferred_equity_missing_assumed_zero_for_basic_ev")
        if minority is None:
            minority = 0.0
            warnings.append("non_controlling_interest_missing_assumed_zero_for_basic_ev")
        value = market_cap + debt + preferred + minority - cash
        fact_ids = market_fact_ids + latest.fact_ids(
            "interest_bearing_debt",
            "total_debt",
            "cash_and_equivalents",
            "cash",
            "preferred_equity",
            "non_controlling_interest",
            "minority_interest",
        )
        return _financial_result(
            "enterprise_value",
            value,
            latest.period_start,
            latest.period_end,
            context,
            "EV = market cap + interest-bearing debt + preferred equity + non-controlling interest - cash",
            {
                **market_inputs,
                "interest_bearing_debt": debt,
                "preferred_equity": preferred,
                "non_controlling_interest": minority,
                "cash_and_equivalents": cash,
                "ev_quality": "basic_ev" if warnings else "full_ev",
                "market_price_date": price_date,
            },
            fact_ids,
            latest.source_urls(
                "market_cap",
                "shares_outstanding",
                "interest_bearing_debt",
                "total_debt",
                "cash_and_equivalents",
                "cash",
                "preferred_equity",
                "non_controlling_interest",
                "minority_interest",
            ),
            source_price_ids=price_ids,
            price_source=price_source,
            unit="currency",
            currency=latest.currency or context.currency,
            warnings=tuple(warnings),
        )

    def _fcf_yield(
        self,
        context: CalculationContext,
        fcf_ttm: MetricResult | None,
        latest: FinancialPeriod | None,
    ) -> MetricResult:
        market_cap, market_inputs, market_fact_ids, price_ids, price_source, price_date, reason = _market_cap(context, latest)
        if fcf_ttm is None or fcf_ttm.value is None:
            return _missing_financial("fcf_yield", fcf_ttm.missing_reason if fcf_ttm else "missing_fcf_ttm", context)
        if market_cap is None:
            return _missing_financial("fcf_yield", reason or "missing_market_cap", context)
        if market_cap == 0:
            return _missing_financial("fcf_yield", "zero_denominator", context)
        return _financial_result(
            "fcf_yield",
            fcf_ttm.value / market_cap,
            fcf_ttm.period_start,
            fcf_ttm.period_end,
            context,
            "FCF Yield = FCF TTM / equity market capitalization",
            {**market_inputs, "fcf_ttm": fcf_ttm.value, "market_price_date": price_date},
            fcf_ttm.source_fact_ids + market_fact_ids,
            fcf_ttm.source_urls,
            source_price_ids=price_ids,
            price_source=price_source,
        )

    def _net_debt_to_ebitda(self, net_debt: MetricResult | None, ebitda: MetricResult | None) -> MetricResult:
        if net_debt is None or net_debt.value is None:
            return MetricResult(code="net_debt_to_ebitda", value=None, quality_status="missing", missing_reason=net_debt.missing_reason if net_debt else "missing_net_debt")
        if ebitda is None or ebitda.value is None:
            return MetricResult(code="net_debt_to_ebitda", value=None, quality_status="missing", missing_reason=ebitda.missing_reason if ebitda else "missing_ebitda")
        if ebitda.value <= 0:
            return MetricResult(code="net_debt_to_ebitda", value=None, quality_status="not_applicable", missing_reason="not_applicable_non_positive_ebitda")
        return MetricResult(
            code="net_debt_to_ebitda",
            value=net_debt.value / ebitda.value,
            formula="Net Debt / EBITDA = net debt / EBITDA TTM",
            formula_version="2.0.0",
            input_values={"net_debt": net_debt.value, "ebitda_ttm": ebitda.value},
            source_fact_ids=net_debt.source_fact_ids + ebitda.source_fact_ids,
            source_urls=net_debt.source_urls + ebitda.source_urls,
        )

    def _ev_to_ebitda(
        self,
        context: CalculationContext,
        ev: MetricResult | None,
        ebitda: MetricResult | None,
    ) -> MetricResult:
        if _industry_not_applicable(context.industry):
            return MetricResult(code="ev_to_ebitda", value=None, quality_status="not_applicable", missing_reason="not_applicable_industry")
        if ev is None or ev.value is None:
            return MetricResult(code="ev_to_ebitda", value=None, quality_status="missing", missing_reason=ev.missing_reason if ev else "missing_enterprise_value")
        if ebitda is None or ebitda.value is None:
            return MetricResult(code="ev_to_ebitda", value=None, quality_status="missing", missing_reason=ebitda.missing_reason if ebitda else "missing_ebitda")
        if ebitda.value <= 0:
            return MetricResult(code="ev_to_ebitda", value=None, quality_status="not_applicable", missing_reason="not_applicable_non_positive_ebitda")
        return MetricResult(
            code="ev_to_ebitda",
            value=ev.value / ebitda.value,
            formula="EV / EBITDA = enterprise value / EBITDA TTM",
            formula_version="2.0.0",
            input_values={"enterprise_value": ev.value, "ebitda_ttm": ebitda.value},
            source_fact_ids=ev.source_fact_ids + ebitda.source_fact_ids,
            source_urls=ev.source_urls + ebitda.source_urls,
            source_price_ids=ev.source_price_ids,
            price_source=ev.price_source,
        )

    def _pe_ttm(
        self,
        context: CalculationContext,
        net_profit_ttm: MetricResult | None,
        latest: FinancialPeriod | None,
    ) -> MetricResult:
        market_cap, market_inputs, market_fact_ids, price_ids, price_source, price_date, reason = _market_cap(context, latest)
        if net_profit_ttm is None or net_profit_ttm.value is None:
            return _missing_financial("pe_ttm", net_profit_ttm.missing_reason if net_profit_ttm else "missing_net_profit_ttm", context)
        if net_profit_ttm.value <= 0:
            return MetricResult(code="pe_ttm", value=None, quality_status="not_applicable", missing_reason="not_applicable_negative_earnings")
        if market_cap is None:
            return _missing_financial("pe_ttm", reason or "missing_market_cap", context)
        return _financial_result(
            "pe_ttm",
            market_cap / net_profit_ttm.value,
            net_profit_ttm.period_start,
            net_profit_ttm.period_end,
            context,
            "PE TTM = market cap / net profit attributable to parent TTM",
            {**market_inputs, "net_profit_ttm": net_profit_ttm.value, "market_price_date": price_date},
            net_profit_ttm.source_fact_ids + market_fact_ids,
            net_profit_ttm.source_urls,
            source_price_ids=price_ids,
            price_source=price_source,
        )

    def _roic(
        self,
        context: CalculationContext,
        quarters: tuple[NormalizedQuarter, ...],
        latest: FinancialPeriod | None,
    ) -> MetricResult:
        if _industry_not_applicable(context.industry):
            return MetricResult(code="roic", value=None, quality_status="not_applicable", missing_reason="not_applicable_industry")
        ebit, ebit_q, ebit_reason = self.periods.ttm(quarters, "ebit")
        if ebit_reason or ebit is None:
            return _missing_financial("roic", "missing_ebit_ttm", context)
        tax, tax_q, _tax_reason = self.periods.ttm(quarters, "income_tax")
        pbt, pbt_q, _pbt_reason = self.periods.ttm(quarters, "profit_before_tax")
        tax_rate = 0.25
        warnings: list[str] = []
        if tax is not None and pbt not in (None, 0):
            tax_rate = max(0.0, min(0.5, tax / pbt))
        else:
            warnings.append("normalized_tax_rate_assumption_used")
        invested_periods = sorted(
            [period for period in context.financial_periods if period.value("total_equity", "equity_parent") is not None],
            key=lambda period: period.period_end,
        )
        if len(invested_periods) < 2:
            return _missing_financial("roic", "missing_average_invested_capital", context)
        begin = invested_periods[-2]
        end = invested_periods[-1]
        begin_capital = _invested_capital(begin)
        end_capital = _invested_capital(end)
        if begin_capital is None or end_capital is None:
            return _missing_financial("roic", "missing_invested_capital_components", context)
        average_invested = (begin_capital + end_capital) / 2
        if average_invested == 0:
            return _missing_financial("roic", "zero_denominator", context)
        nopat = ebit * (1 - tax_rate)
        fact_ids = (
            _quarter_fact_ids(ebit_q, "ebit")
            + _quarter_fact_ids(tax_q, "income_tax")
            + _quarter_fact_ids(pbt_q, "profit_before_tax")
            + begin.fact_ids("interest_bearing_debt", "total_debt", "total_equity", "equity_parent", "non_controlling_interest")
            + end.fact_ids("interest_bearing_debt", "total_debt", "total_equity", "equity_parent", "non_controlling_interest")
        )
        return _financial_result(
            "roic",
            nopat / average_invested,
            ebit_q[0].period_start,
            ebit_q[-1].period_end,
            context,
            "ROIC = EBIT TTM * (1 - normalized tax rate) / average invested capital",
            {
                "ebit_ttm": ebit,
                "tax_rate": tax_rate,
                "nopat": nopat,
                "begin_invested_capital": begin_capital,
                "end_invested_capital": end_capital,
                "average_invested_capital": average_invested,
            },
            fact_ids,
            _urls_for_ids(context.financial_periods, fact_ids),
            warnings=tuple(warnings),
        )


def _market_cap(
    context: CalculationContext,
    latest: FinancialPeriod | None,
) -> tuple[float | None, dict[str, object], tuple[int, ...], tuple[int, ...], str | None, str | None, str | None]:
    if latest is not None:
        direct = latest.value("market_cap")
        if direct is not None:
            return direct, {"market_cap": direct, "market_cap_source": "financial_fact"}, latest.fact_ids("market_cap"), tuple(), None, latest.period_end, None
    price = _latest_price(context.price_series, context.as_of_date)
    shares = latest.value("shares_outstanding") if latest else None
    if price is not None and shares is not None:
        return (
            price.close * shares,
            {"close": price.close, "shares_outstanding": shares},
            latest.fact_ids("shares_outstanding") if latest else tuple(),
            (price.id,) if price.id is not None else tuple(),
            price.data_source,
            price.trade_date,
            None,
        )
    return None, {}, tuple(), tuple(), None, None, "missing_market_cap"


def _latest_price(prices: tuple[PricePoint, ...], as_of_date: str | None) -> PricePoint | None:
    eligible = [price for price in prices if as_of_date is None or price.trade_date <= as_of_date]
    return sorted(eligible, key=lambda price: price.trade_date)[-1] if eligible else None


def _invested_capital(period: FinancialPeriod) -> float | None:
    debt = period.value("interest_bearing_debt", "total_debt")
    equity = period.value("total_equity", "equity_parent")
    if debt is None or equity is None:
        return None
    minority = period.value("non_controlling_interest", "minority_interest") or 0.0
    excess_cash = period.value("excess_cash") or 0.0
    return debt + equity + minority - excess_cash


def _financial_result(
    code: str,
    value: float,
    period_start: str | None,
    period_end: str | None,
    context: CalculationContext,
    formula: str,
    input_values: dict[str, object],
    source_fact_ids: tuple[int, ...],
    source_urls: tuple[str, ...],
    *,
    source_price_ids: tuple[int, ...] = (),
    price_source: str | None = None,
    unit: str = "ratio",
    currency: str | None = None,
    warnings: tuple[str, ...] = (),
) -> MetricResult:
    return MetricResult(
        code=code,
        value=value,
        period_start=period_start,
        period_end=period_end,
        as_of=context.as_of_date or period_end,
        currency=currency or context.currency,
        unit=unit,
        formula=formula,
        formula_version=context.calculation_version,
        input_values=input_values,
        source_fact_ids=tuple(dict.fromkeys(source_fact_ids)),
        source_urls=tuple(dict.fromkeys(source_urls)),
        source_price_ids=source_price_ids,
        price_source=price_source,
        quality_status="calculated_with_warnings" if warnings else "calculated",
        warnings=warnings,
    )


def _missing_financial(
    code: str,
    reason: str,
    context: CalculationContext,
    *,
    source_fact_ids: tuple[int, ...] = (),
) -> MetricResult:
    return MetricResult(
        code=code,
        value=None,
        as_of=context.as_of_date,
        currency=context.currency,
        formula_version=context.calculation_version,
        source_fact_ids=source_fact_ids,
        quality_status="missing",
        missing_reason=reason,
    )


def _latest_period(periods: tuple[FinancialPeriod, ...]) -> FinancialPeriod | None:
    return sorted(periods, key=lambda period: period.period_end)[-1] if periods else None


def _quarter_fact_ids(quarters: tuple[NormalizedQuarter, ...], code: str) -> tuple[int, ...]:
    ids: list[int] = []
    for quarter in quarters:
        ids.extend(quarter.fact_ids(code))
    return tuple(dict.fromkeys(ids))


def _quarter_urls(quarters: tuple[NormalizedQuarter, ...], code: str) -> tuple[str, ...]:
    urls: list[str] = []
    for quarter in quarters:
        urls.extend(quarter.source_urls(code))
    return tuple(dict.fromkeys(urls))


def _urls_for_ids(periods: tuple[FinancialPeriod, ...], fact_ids: tuple[int, ...]) -> tuple[str, ...]:
    urls: list[str] = []
    id_set = set(fact_ids)
    for period in periods:
        for code, ids in period.fact_ids_by_metric.items():
            if id_set.intersection(ids):
                urls.extend(period.source_urls_by_metric.get(code, ()))
    return tuple(dict.fromkeys(urls))


def _industry_not_applicable(industry: str | None) -> bool:
    if not industry:
        return False
    lowered = industry.lower()
    return any(token in lowered for token in NON_OPERATING_FINANCIAL_INDUSTRIES)
