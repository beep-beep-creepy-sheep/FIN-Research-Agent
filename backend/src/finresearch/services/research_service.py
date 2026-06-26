from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from finresearch.repositories.research import ResearchRepository
from finresearch.settings import get_settings
from finresearch.ai.ollama import OllamaProvider
from finresearch.services.company_analysis import AnalysisResult, CompanyAnalysisService
from finresearch.services.external_research import ExternalResearchService


@dataclass(frozen=True)
class ExternalContext:
    items: list[dict[str, object]]
    warnings: list[str]
    coverage: list[str]


class ResearchService:
    def __init__(self, library_path: Path) -> None:
        self.analysis_service = CompanyAnalysisService(library_path)
        self.research_repo = ResearchRepository(library_path)
        self.external_research = ExternalResearchService()

    def create_structured_run(
        self,
        symbol: str,
        *,
        years: int = 5,
        as_of_date: str | None = None,
    ) -> dict[str, object]:
        result = self.analysis_service.execute(symbol, years=years, as_of_date=as_of_date)
        external_context = collect_external_context(self.external_research, result)
        markdown = render_markdown(result, external_context)
        llm_note = generate_llm_commentary(markdown, external_context)
        if llm_note:
            markdown = f"{markdown}\n## 本地模型综合研判\n\n{llm_note.strip()}\n"
        run_id = self.research_repo.save(
            query=f"analyze {symbol}",
            symbol=symbol,
            as_of_date=as_of_date,
            markdown=markdown,
            structured_result={
                **result.__dict__,
                "external_context": {
                    "items": external_context.items,
                    "warnings": external_context.warnings,
                    "coverage": external_context.coverage,
                },
            },
        )
        return {"id": run_id, "structured_result": result.__dict__, "report_markdown": markdown}

    def list_runs(self) -> list[dict[str, object]]:
        return self.research_repo.list()


def collect_external_context(service: ExternalResearchService, result: AnalysisResult) -> ExternalContext:
    company = result.company or {}
    name = display_company_name(result)
    query = f"{name} {result.symbol} 财报 业绩 风险 投资者 争议"
    warnings: list[str] = []
    items: list[dict[str, object]] = []
    coverage: list[str] = []

    try:
        health = service.health()
        for row in health:
            status = row.get("status")
            active = row.get("active_backend")
            if status == "available":
                coverage.append(f"{row.get('name')}: available via {active or 'default'}")
            elif row.get("name") in {"agent_reach", "direct_web", "rss"}:
                coverage.append(f"{row.get('name')}: {status} {row.get('last_error') or ''}".strip())
    except Exception as exc:
        warnings.append(f"connector_health:{exc}")

    google_news_feed = (
        "https://news.google.com/rss/search?q="
        f"{quote(query)}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    )
    bing_news_feed = "https://www.bing.com/news/search?q=" f"{quote(query)}&format=rss"
    for search_query, connectors, limit in [
        (query, ["agent_reach"], 8),
        (google_news_feed, ["rss"], 8),
        (bing_news_feed, ["rss"], 8),
    ]:
        try:
            found = service.search(search_query, connectors=connectors, limit=limit)
            warnings.extend(found.warnings)
            items.extend(found.items)
        except Exception as exc:
            warnings.append(f"{'+'.join(connectors)}:{exc}")

    return ExternalContext(items=dedupe_external_items(items), warnings=warnings, coverage=coverage)


def dedupe_external_items(items: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[str] = set()
    deduped: list[dict[str, object]] = []
    for item in items:
        key = str(item.get("url") or item.get("content_hash") or item.get("title"))
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:12]


def render_markdown(result: AnalysisResult, external_context: ExternalContext | None = None) -> str:
    external_context = external_context or ExternalContext(items=[], warnings=[], coverage=[])
    company = result.company or {}
    latest = result.periods[0] if result.periods else {}
    previous = comparable_previous_period(latest, result.periods)
    revenue_growth = growth(latest.get("revenue"), previous.get("revenue"))
    profit_growth = growth(latest.get("net_profit_parent") or latest.get("net_profit"), previous.get("net_profit_parent") or previous.get("net_profit"))
    advanced = advanced_metrics(latest, previous)
    lines = [
        f"# {display_company_name(result)} 专业研究记录",
        "",
        f"- 股票代码：{result.symbol}",
        f"- 生成时间：{result.generated_at}",
        f"- 数据范围：{len(result.periods)} 个财务期间",
        f"- 证据数量：{len(result.evidence)} 条本地文档证据",
        f"- 外部来源：{len(external_context.items)} 条网页/RSS/Agent Reach 来源",
        "",
        "## 1. 执行摘要",
        "",
        summary_sentence(result, revenue_growth, profit_growth),
        judgement_sentence(result, advanced, external_context),
        "",
        "## 2. 核心指标仪表盘",
        "",
    ]
    lines.extend(metric_lines(result, advanced))

    lines.extend(["", "## 3. 增长与盈利质量", ""])
    lines.append(f"- 营业收入同比变化：{percent_or_missing(revenue_growth)}，对比期间：{period_pair(latest, previous)}。")
    lines.append(f"- 归母净利润同比变化：{percent_or_missing(profit_growth)}，用于观察利润弹性是否强于收入。")
    if latest:
        lines.append(f"- 最新期间收入：{money(latest.get('revenue'))}；归母净利润：{money(latest.get('net_profit_parent') or latest.get('net_profit'))}；经营现金流：{money(latest.get('operating_cash_flow'))}。")
        lines.append(f"- 最新总资产：{money(latest.get('total_assets'))}；总负债：{money(latest.get('total_liabilities'))}；所有者权益：{money(latest.get('total_equity'))}。")
    lines.extend(quality_lines(result, advanced))

    lines.extend(["", "## 4. 资产负债与资本效率", ""])
    lines.append(f"- 资产负债率：{percent_or_missing(_float(result.metrics.get('liability_ratio')))}；债务/权益：{ratio_or_missing(advanced.get('debt_to_equity'))}。")
    lines.append(f"- 总资产周转率：{ratio_or_missing(advanced.get('asset_turnover'))}；权益乘数：{ratio_or_missing(advanced.get('equity_multiplier'))}。")
    lines.append("- 这些指标需要和行业、商业模式、预收款结构一起看；单家公司不能直接推出估值结论。")

    lines.extend(["", "## 5. 外部证据与市场讨论", ""])
    lines.extend(external_evidence_lines(external_context))

    lines.extend(["", "## 6. 本地文档证据", ""])
    if result.evidence:
        for index, item in enumerate(result.evidence[:8], start=1):
            lines.append(f"- [D{index}] {item.get('title') or item.get('source_path') or '本地文档'}：{compact_text(item.get('text'), 180)}")
    else:
        lines.append("- 尚未导入本地年报/公告/PDF。建议上传最新年报、季报、业绩说明会纪要和交易所问询函。")

    lines.extend(["", "## 7. 关键风险与反证清单", ""])
    lines.extend(risk_lines(result, advanced, external_context))

    lines.extend(["", "## 8. 数据缺口与渠道覆盖", ""])
    lines.extend(f"- {translate_gap(item)}" for item in (result.data_gaps or ["暂无明显缺口"]))
    if external_context.warnings:
        lines.extend(f"- 外部采集提示：{warning}" for warning in external_context.warnings[:8])
    if external_context.coverage:
        lines.extend(f"- 渠道状态：{item}" for item in external_context.coverage[:8])

    lines.extend(["", "## 9. 下一步核验清单", ""])
    lines.extend(
        [
            "- 导入最新年报或季报 PDF，核对收入、利润、现金流和资产负债表关键科目。",
            "- 补充同业公司数据，至少加入 3-5 家可比公司，形成行业分位数而不是孤立指标。",
            "- 配置 Twitter/雪球/Reddit/小红书登录态后重新生成报告，把投资者讨论、争议点和情绪变化纳入证据。",
            "- 对比官方公告发布日期，避免使用未来数据做历史时点判断。",
            "- 若要形成正式观点，加入估值、价格、分红、库存/渠道、管理层表述和监管问询的交叉验证。",
        ]
    )
    return "\n".join(lines) + "\n"


def generate_llm_commentary(markdown: str, external_context: ExternalContext | None = None) -> str | None:
    settings = get_settings()
    if not settings.llm_enabled or settings.llm_provider != "ollama":
        return None
    sources = "\n".join(
        f"- {item.get('title') or item.get('url')}: {compact_text(item.get('content'), 260)}"
        for item in (external_context.items if external_context else [])[:8]
    )
    prompt = (
        "你是专业但谨慎的财务研究员。只基于下面的结构化财务记录和外部来源摘要，生成中文综合研判。"
        "要求：不要推荐买卖；不要编造缺失数据；不要改变指标方向；每条判断都说明依据来自财务数据、外部来源或待核验。"
        "严格保留渠道状态原意：mcporter is not installed 只代表 Exa 语义搜索未配置，不代表 Agent Reach 未安装。"
        "输出 6-10 个要点，覆盖基本面、现金质量、资产负债、市场争议、数据缺口和下一步动作。"
        "如果外部来源不足，必须明确说覆盖不足。\n\n"
        f"【研究记录】\n{markdown[:9000]}\n\n【外部来源摘要】\n{sources[:5000]}"
    )
    try:
        return OllamaProvider(settings).generate(prompt)
    except Exception as exc:
        return f"- 本地模型暂不可用：{exc}"


def summary_sentence(result: AnalysisResult, revenue_growth: float | None, profit_growth: float | None) -> str:
    if not result.periods:
        return "当前缺少结构化财务数据，无法形成有效研究结论。"
    parts = ["公司已有结构化财务数据入库"]
    if revenue_growth is not None:
        parts.append(f"收入变化约 {revenue_growth:.2%}")
    if profit_growth is not None:
        parts.append(f"利润变化约 {profit_growth:.2%}")
    if result.metrics.get("net_margin") is not None:
        parts.append(f"净利率约 {float(result.metrics['net_margin']):.2%}")
    return "，".join(parts) + "。"


def display_company_name(result: AnalysisResult) -> str:
    company = result.company or {}
    raw_name = company.get("company_name") or company.get("name")
    name = str(raw_name).strip() if raw_name else ""
    known_names = {
        "600519": "贵州茅台",
    }
    if not name or name == result.symbol:
        return known_names.get(result.symbol, result.symbol)
    return name


def judgement_sentence(result: AnalysisResult, advanced: dict[str, float | None], external_context: ExternalContext) -> str:
    signals: list[str] = []
    cash_conversion = _float(result.metrics.get("cash_conversion"))
    if cash_conversion is not None:
        signals.append("现金含量较好" if cash_conversion >= 1 else "现金含量需要核验")
    liability_ratio = _float(result.metrics.get("liability_ratio"))
    if liability_ratio is not None:
        signals.append("负债率偏低" if liability_ratio < 0.3 else "负债率需要行业对比")
    if external_context.items:
        signals.append("已有外部新闻/RSS/网页证据进入记录")
    else:
        signals.append("外部市场讨论覆盖不足")
    return "初步判断：" + "，".join(signals) + "；该结论仍需年报原文和同业估值交叉验证。"


def advanced_metrics(latest: dict[str, object], previous: dict[str, object]) -> dict[str, float | None]:
    revenue = _float(latest.get("revenue"))
    net_profit = _float(latest.get("net_profit_parent") or latest.get("net_profit"))
    operating_cash_flow = _float(latest.get("operating_cash_flow"))
    total_assets = _float(latest.get("total_assets"))
    total_liabilities = _float(latest.get("total_liabilities"))
    total_equity = _float(latest.get("total_equity"))
    previous_assets = _float(previous.get("total_assets"))
    average_assets = _average(total_assets, previous_assets)
    return {
        "operating_cash_flow_margin": _divide(operating_cash_flow, revenue),
        "asset_turnover": _divide(revenue, average_assets),
        "debt_to_equity": _divide(total_liabilities, total_equity),
        "equity_multiplier": _divide(total_assets, total_equity),
        "return_on_assets": _divide(net_profit, average_assets),
    }


def metric_lines(result: AnalysisResult, advanced: dict[str, float | None]) -> list[str]:
    base = [
        ("净利率", metric_value("net_margin", result.metrics.get("net_margin"))),
        ("经营现金流/净利润", metric_value("cash_conversion", result.metrics.get("cash_conversion"))),
        ("资产负债率", metric_value("liability_ratio", result.metrics.get("liability_ratio"))),
        ("ROE 近似值", metric_value("roe_proxy", result.metrics.get("roe_proxy"))),
        ("经营现金流率", percent_or_missing(advanced.get("operating_cash_flow_margin"))),
        ("ROA 近似值", percent_or_missing(advanced.get("return_on_assets"))),
        ("总资产周转率", ratio_or_missing(advanced.get("asset_turnover"))),
        ("债务/权益", ratio_or_missing(advanced.get("debt_to_equity"))),
    ]
    return [f"- {label}：{value}" for label, value in base]


def quality_lines(result: AnalysisResult, advanced: dict[str, float | None]) -> list[str]:
    lines = ["", "## 3.1 现金流与利润质量", ""]
    cash_conversion = _float(result.metrics.get("cash_conversion"))
    cash_margin = advanced.get("operating_cash_flow_margin")
    if cash_conversion is None:
        lines.append("- 缺少经营现金流或净利润，暂不能判断利润现金含量。")
    elif cash_conversion >= 1:
        lines.append("- 经营现金流覆盖净利润较好，利润现金含量相对健康。")
    else:
        lines.append("- 经营现金流低于净利润，需要进一步核验回款、预收、存货、税费和季节性影响。")
    lines.append(f"- 经营现金流率：{percent_or_missing(cash_margin)}，可用于观察收入转化为现金的能力。")
    if result.quality_flags:
        lines.extend(f"- 质量旗标：{translate_gap(flag)}" for flag in result.quality_flags)
    return lines


def external_evidence_lines(context: ExternalContext) -> list[str]:
    if not context.items:
        return [
            "- 当前未取得可引用的外部来源。原因通常是 Exa/Twitter/雪球等渠道未配置，或网络/RSS 暂不可达。",
            "- 这会降低报告对市场讨论、争议点、短期舆情和非公告信息的覆盖度。",
        ]
    lines = []
    for index, item in enumerate(context.items[:10], start=1):
        title = item.get("title") or item.get("url") or "外部来源"
        platform = item.get("platform") or item.get("connector") or "web"
        url = item.get("url") or ""
        content = compact_text(item.get("content"), 220)
        lines.append(f"- [W{index}] {title}（{platform}）：{content} 来源：{url}")
    return lines


def risk_lines(result: AnalysisResult, advanced: dict[str, float | None], context: ExternalContext) -> list[str]:
    lines = [
        "- 单家公司指标不能替代同业对比；缺少估值、价格、分红和行业周期时，不能形成完整投资结论。",
        "- 若外部新闻和社媒讨论覆盖不足，短期争议、渠道反馈和市场预期变化可能漏掉。",
    ]
    cash_conversion = _float(result.metrics.get("cash_conversion"))
    if cash_conversion is not None and cash_conversion < 1:
        lines.append("- 现金流低于净利润是当前需要优先反证的项目。")
    if advanced.get("asset_turnover") is not None:
        lines.append("- 资产周转率应和历史区间及同业分位对比，避免只看绝对值。")
    if context.warnings:
        lines.append("- 外部采集存在警告，正式使用前需要补齐未配置渠道。")
    return lines


def growth(current: object, previous: object) -> float | None:
    try:
        current_number = float(current)  # type: ignore[arg-type]
        previous_number = float(previous)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if previous_number == 0:
        return None
    return current_number / previous_number - 1


def comparable_previous_period(
    latest: dict[str, object], periods: list[dict[str, object]]
) -> dict[str, object]:
    period_end = str(latest.get("period_end", ""))
    if len(period_end) < 10:
        return periods[1] if len(periods) > 1 else {}
    previous_year_period = f"{int(period_end[:4]) - 1}{period_end[4:]}"
    for period in periods[1:]:
        if str(period.get("period_end")) == previous_year_period:
            return period
    return periods[1] if len(periods) > 1 else {}


def period_pair(latest: dict[str, object], previous: dict[str, object]) -> str:
    return f"{latest.get('period_end') or '最新期间'} vs {previous.get('period_end') or '可比期间缺失'}"


def money(value: object) -> str:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "缺失"
    return f"{number / 100000000:.2f} 亿元"


def percent_or_missing(value: float | None) -> str:
    return "缺失" if value is None else f"{value:.2%}"


def ratio_or_missing(value: float | None) -> str:
    return "缺失" if value is None else f"{value:.2f} 倍"


def metric_label(key: str) -> str:
    return {
        "net_margin": "净利率",
        "cash_conversion": "经营现金流/净利润",
        "liability_ratio": "资产负债率",
        "roe_proxy": "ROE 近似值",
    }.get(key, key)


def metric_value(key: str, value: object) -> str:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "缺失" if value is None else str(value)
    if key in {"net_margin", "liability_ratio", "roe_proxy"}:
        return f"{number:.2%}"
    if key == "cash_conversion":
        return f"{number:.2f} 倍"
    return str(value)


def translate_gap(gap: str) -> str:
    return {
        "missing_structured_financial_facts": "缺少结构化财务数据",
        "missing_local_document_evidence": "尚未导入本地年报/公告/PDF 证据",
        "strict_as_of_enabled_unknown_publication_dates_excluded": "历史时点模式下已排除未知发布日期数据",
        "operating_cash_flow_below_net_profit": "经营现金流低于净利润",
    }.get(gap, gap)


def compact_text(value: object, limit: int = 160) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        return "暂无摘要"
    return text if len(text) <= limit else f"{text[:limit - 1]}..."


def _float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _divide(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _average(first: float | None, second: float | None) -> float | None:
    values = [value for value in [first, second] if value is not None]
    if not values:
        return None
    return sum(values) / len(values)
