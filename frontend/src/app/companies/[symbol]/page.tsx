import { Card } from "@/components/Card";
import { EChartPanel } from "@/charts/EChartPanel";
import {
  getCompanyAnalysis,
  getCompanyBenchmark,
  getCompanyCharts,
  getCompanyFilings,
  getCompanyPeerMetrics,
  getCompanyPeers,
  getCompanySummary,
  getCompanyValuation,
  getDataQualityIssues,
  getDataQualitySummary,
  type AnalysisReport,
  type CompanySummary,
  type FilingRecord,
  type MarketChart,
  type PeerMetricsResponse,
  type PeerSetResponse,
  type ValuationResponse,
} from "@/lib/api";
import { SyncButton } from "@/features/SyncButton";
import { ResearchRuns } from "@/features/ResearchRuns";
import { FilingSyncButton } from "@/features/FilingSyncButton";

export default async function CompanyPage({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;
  let summary: CompanySummary | null = null;
  let charts: MarketChart[] = [];
  let filings: FilingRecord[] = [];
  let benchmark: Record<string, unknown> | null = null;
  let qualitySummary: Record<string, unknown> | null = null;
  let qualityIssues: Array<Record<string, unknown>> = [];
  let analysis: AnalysisReport | null = null;
  let peers: PeerSetResponse | null = null;
  let peerMetrics: PeerMetricsResponse | null = null;
  let relativeValuation: ValuationResponse | null = null;
  let dcfValuation: ValuationResponse | null = null;
  const results = await Promise.allSettled([
    getCompanySummary(symbol),
    getCompanyCharts(symbol),
    getCompanyFilings(symbol),
    getCompanyBenchmark(symbol),
    getDataQualitySummary(),
    getDataQualityIssues(),
    getCompanyAnalysis(symbol),
    getCompanyPeers(symbol),
    getCompanyPeerMetrics(symbol),
    getCompanyValuation(symbol, "relative_valuation"),
    getCompanyValuation(symbol, "dcf_owner_earnings"),
  ] as const);
  summary = settledValue(results[0], null);
  charts = settledValue(results[1], []);
  filings = settledValue(results[2], []);
  benchmark = settledValue(results[3], null);
  qualitySummary = settledValue(results[4], null);
  qualityIssues = settledValue(results[5], []);
  analysis = settledValue(results[6], null);
  peers = settledValue(results[7], null);
  peerMetrics = settledValue(results[8], null);
  relativeValuation = settledValue(results[9], null);
  dcfValuation = settledValue(results[10], null);
  const partialFailures = results.filter((result) => result.status === "rejected").length;

  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-accent">{symbol === "600519" ? "示例公司：贵州茅台" : "公司研究页"}</p>
          <h1 className="mt-1 text-3xl font-semibold">{getCompanyName(summary?.company, symbol) ?? symbol}</h1>
          <p className="mt-1 text-slate-600">同步数据后，这里会展示财务指标、数据来源和研究证据。</p>
        </div>
        <SyncButton symbol={symbol} />
      </div>

      {partialFailures ? (
        <div className="mb-4 rounded-md border border-risk bg-white p-4 text-sm text-risk">
          部分数据暂不可用，其他卡片仍可查看。
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="研究摘要">
          {summary?.periods?.length ? (
            <div className="space-y-3 text-sm leading-6 text-slate-700">
              <p>{buildSummary(symbol, summary.periods, summary.metrics)}</p>
              <div className="grid gap-2 sm:grid-cols-3">
                {summaryCards(summary.periods, summary.metrics).map(([label, value]) => (
                  <div key={label} className="rounded border border-line bg-slate-50 p-3">
                    <div className="text-xs text-slate-500">{label}</div>
                    <div className="mt-1 font-medium text-slate-900">{value}</div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <EmptyState text="同步财务数据后，这里会生成自动研究摘要。" />
          )}
        </Card>
        <Card title="研究记录">
          <ResearchRuns symbol={symbol} />
        </Card>
        <Card title="公司概览">
          <KeyValueGrid
            items={[
              ["代码", symbol],
              ["名称", getCompanyName(summary?.company, symbol) ?? (symbol === "600519" ? "贵州茅台" : "等待同步")],
              ["市场", getString(summary?.company, "market") ?? getString(summary?.company, "exchange") ?? "等待同步"],
              ["行业", getString(summary?.company, "industry") ?? "等待同步"],
            ]}
          />
        </Card>
        <Card title="核心指标">
          {summary?.metrics && Object.keys(summary.metrics).length ? (
            <KeyValueGrid items={Object.entries(summary.metrics).slice(0, 8).map(([key, value]) => [formatMetricLabel(key), formatMetricValue(key, value)])} />
          ) : (
            <EmptyState text="还没有可展示的指标。先点击右上角“同步数据”。" />
          )}
        </Card>
        <Card title="财务期间">
          {summary?.periods?.length ? (
            <div className="max-h-96 space-y-3 overflow-auto text-sm">
              {summary.periods.slice(0, 10).map((period, index) => (
                <div key={`${String(period.period_end ?? period.period ?? period.year ?? index)}`} className="rounded border border-line bg-slate-50 p-3">
                  <div className="font-medium text-slate-800">
                    {formatPeriod(String(period.period_end ?? period.period ?? period.year ?? `期间 ${index + 1}`))}
                  </div>
                  <dl className="mt-3 grid gap-2 sm:grid-cols-2">
                    {periodItems(period).map(([label, value]) => (
                      <div key={label}>
                        <dt className="text-xs text-slate-500">{label}</dt>
                        <dd className="font-medium text-slate-800">{formatMoney(value)}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState text="本地数据库里还没有该公司的财务期间数据。" />
          )}
        </Card>
        <Card title="证据与数据缺口">
          <div className="space-y-4">
            {summary?.evidence?.length ? (
              <ul className="space-y-2 text-sm">
                {summary.evidence.slice(0, 8).map((item, index) => (
                  <li key={index} className="rounded border border-line bg-slate-50 p-3">
                    {String(item.title ?? item.source ?? item.url ?? "证据记录")}
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState text="财务数据已经来自公开接口入库；本地年报、公告 PDF 或网页证据还没导入，所以这里暂时为空。" />
            )}
            {summary?.data_gaps?.length ? (
              <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                {summary.data_gaps.map(translateGap).join("；")}
              </div>
            ) : null}
          </div>
        </Card>
        <Card title="公告 / Filings">
          <div className="mb-3">
            <FilingSyncButton symbol={symbol} />
          </div>
          {filings.length ? (
            <div className="max-h-96 space-y-2 overflow-auto text-sm">
              {filings.map((filing) => (
                <div key={filing.id} className="rounded border border-line bg-slate-50 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="font-medium text-slate-900">{filing.title ?? "Untitled filing"}</div>
                      <div className="mt-1 text-xs text-slate-500">
                        {filing.filing_type ?? "unknown"} · {filing.report_period ?? "period missing"} ·{" "}
                        {filing.publication_date ?? "publication date missing"}
                      </div>
                    </div>
                    <span className="rounded border border-line bg-white px-2 py-1 text-xs text-slate-600">
                      {filing.source_id ?? "unknown"}
                    </span>
                  </div>
                  <div className="mt-3 grid gap-2 sm:grid-cols-3">
                    <StatusPill label="source" value={filing.source_tier ?? "unknown"} />
                    <StatusPill label="download" value={filing.download_status ?? "pending"} />
                    <StatusPill label="parse" value={filing.parse_status ?? "pending"} />
                  </div>
                  {filing.error_message ? <p className="mt-2 text-xs text-risk">{filing.error_message}</p> : null}
                </div>
              ))}
            </div>
          ) : (
            <EmptyState text="没有公告记录。点击同步会创建后台任务；真实下载和解析由 worker 执行。" />
          )}
        </Card>
        <Card title="Benchmark">
          {benchmark ? (
            <KeyValueGrid
              items={[
                ["基准代码", benchmark.benchmark_code ?? "未配置"],
                ["基准名称", benchmark.benchmark_name ?? "未配置"],
                ["选择来源", benchmark.benchmark_source ?? "unknown"],
                ["选择原因", benchmark.selection_reason ?? "unknown"],
                ["缺失原因", benchmark.missing_reason ?? "无"],
              ]}
            />
          ) : (
            <EmptyState text="基准选择信息暂不可用。" />
          )}
        </Card>
        <Card title="数据质量">
          <div className="space-y-3">
            <KeyValueGrid
              items={[
                ["Open issues", qualitySummary?.open_count ?? 0],
                ["By severity", compactJson(qualitySummary?.by_severity)],
                ["By source", compactJson(qualitySummary?.by_source)],
                ["By type", compactJson(qualitySummary?.by_type)],
              ]}
            />
            {qualityIssues.length ? (
              <ul className="space-y-2 text-sm">
                {qualityIssues.map((issue) => (
                  <li key={String(issue.id)} className="rounded border border-line bg-slate-50 p-3">
                    <span className="font-medium">{String(issue.issue_type)}</span>
                    <span className="ml-2 text-xs text-slate-500">
                      {String(issue.severity)} · {String(issue.status)} · {String(issue.source_id ?? "unknown")}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState text="当前没有数据质量问题；这也可能表示还没有运行官方公告同步。" />
            )}
          </div>
        </Card>
        <Card title="Professional Analysis">
          {analysis ? (
            <div className="space-y-4">
              <p className="text-sm leading-6 text-slate-700">{analysis.executive_summary}</p>
              <KeyValueGrid
                items={[
                  ["综合研究质量", formatScore(analysis.scores, "overall_research_quality_score")],
                  ["行业包", formatPackList(analysis.financial_profile.industry_packs)],
                  ["行业状态", String(analysis.financial_profile.industry ?? "unknown")],
                  ["证据数量", analysis.evidence_map.length],
                ]}
              />
              {analysis.key_findings.length ? (
                <div className="space-y-2">
                  {analysis.key_findings.slice(0, 5).map((finding) => (
                    <div key={finding.finding_id} className="rounded border border-line bg-slate-50 p-3 text-sm">
                      <div className="flex items-start justify-between gap-3">
                        <div className="font-medium text-slate-900">{finding.title}</div>
                        <span className="rounded border border-line bg-white px-2 py-1 text-xs text-slate-600">
                          {finding.direction}
                        </span>
                      </div>
                      <p className="mt-2 text-slate-700">{finding.summary}</p>
                      <p className="mt-2 text-xs text-slate-500">
                        evidence: facts {finding.source_fact_ids?.length ?? 0}, prices {finding.source_price_ids?.length ?? 0}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState text="专业分析已运行，但没有可展示的 finding。" />
              )}
              <AnalysisSectionState title="Growth" section={analysis.growth} />
              <AnalysisSectionState title="Industry Pack" section={analysis.industry_specific} />
              <AnalysisSectionState title="Quality & Risk" section={analysis.data_quality} />
              {analysis.quality_flags.length ? (
                <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                  {analysis.quality_flags.map((flag) => String(flag.message ?? flag.flag_id)).join("；")}
                </div>
              ) : null}
            </div>
          ) : (
            <EmptyState text="专业分析暂不可用；公司不存在或本地数据不足时会显示结构化缺失状态。" />
          )}
        </Card>
        <Card title="Peers">
          {peers ? (
            <div className="space-y-3">
              <KeyValueGrid
                items={[
                  ["同业数量", peers.selected_symbols.length],
                  ["质量状态", peers.quality_flags.length ? peers.quality_flags.join("；") : "available"],
                  ["版本", String(peers.as_of_date)],
                  ["来源", "local company metadata"],
                ]}
              />
              {peers.candidates.length ? (
                <div className="max-h-72 overflow-auto rounded border border-line">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-slate-50 text-xs text-slate-500">
                      <tr>
                        <th className="px-3 py-2">代码</th>
                        <th className="px-3 py-2">行业</th>
                        <th className="px-3 py-2">相似度</th>
                        <th className="px-3 py-2">原因</th>
                      </tr>
                    </thead>
                    <tbody>
                      {peers.candidates.map((candidate) => (
                        <tr key={String(candidate.symbol)} className="border-t border-line">
                          <td className="px-3 py-2 font-medium text-accent">{String(candidate.symbol)}</td>
                          <td className="px-3 py-2">{String(candidate.industry ?? "missing")}</td>
                          <td className="px-3 py-2">{formatValue(candidate.similarity_score)}</td>
                          <td className="px-3 py-2">{String(candidate.reason ?? "missing")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <EmptyState text="同业数据不足：需要本地公司行业、交易所和结构化财务事实。" />
              )}
              {peers.limitations.length ? <p className="text-xs text-slate-500">{peers.limitations.join("；")}</p> : null}
            </div>
          ) : (
            <EmptyState text="Peers section 暂不可用；公司不存在或行业元数据不足。" />
          )}
        </Card>
        <Card title="Peer Metrics Matrix">
          {peerMetrics?.rows?.length ? (
            <div className="space-y-3">
              <div className="max-h-80 overflow-auto rounded border border-line">
                <table className="w-full min-w-[760px] text-left text-xs">
                  <thead className="bg-slate-50 text-slate-500">
                    <tr>
                      <th className="px-3 py-2">代码</th>
                      {peerMetrics.columns.slice(0, 7).map((column) => (
                        <th key={column} className="px-3 py-2">{formatMetricLabel(column)}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {peerMetrics.rows.slice(0, 8).map((row) => {
                      const metrics = row.metrics as Record<string, Record<string, unknown>> | undefined;
                      return (
                        <tr key={String(row.symbol)} className="border-t border-line">
                          <td className="px-3 py-2 font-medium text-accent">{String(row.symbol)}</td>
                          {peerMetrics.columns.slice(0, 7).map((column) => (
                            <td key={column} className="px-3 py-2">
                              {formatMetricCell(metrics?.[column])}
                            </td>
                          ))}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-slate-500">异常值规则：{peerMetrics.outlier_policy}；缺失值不参与排名和分位。</p>
            </div>
          ) : (
            <EmptyState text="Peer Metrics Matrix 暂无可展示数据；不会用模拟公司或空值补齐。" />
          )}
        </Card>
        <Card title="Valuation Lab">
          <div className="space-y-4">
            <p className="rounded border border-line bg-slate-50 p-3 text-sm text-slate-700">
              估值情景范围、相对分位和敏感性分析仅用于研究核验，不是投资建议。
            </p>
            <ValuationBlock title="Relative Valuation" valuation={relativeValuation} />
            <ValuationBlock title="DCF / Owner Earnings Scenario" valuation={dcfValuation} />
          </div>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        {charts.map((chart) => (
          <EChartPanel key={chart.id} chart={chart} />
        ))}
      </div>
    </main>
  );
}

function ValuationBlock({ title, valuation }: { title: string; valuation: ValuationResponse | null }) {
  if (!valuation) return <EmptyState text={`${title} 暂不可用：本地证据或现金流历史不足。`} />;
  const status = getNestedString(valuation.results, ["status"]) ?? getNestedString(valuation.results, ["models", "0", "status"]) ?? "calculated";
  const sensitivity = Array.isArray(valuation.sensitivity?.table) ? valuation.sensitivity.table.length : 0;
  return (
    <div className="rounded border border-line bg-white p-3 text-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-medium text-slate-900">{title}</div>
          <div className="mt-1 text-xs text-slate-500">{valuation.model_type} · {valuation.scenario_name} · {valuation.as_of_date}</div>
        </div>
        <span className="rounded border border-line bg-slate-50 px-2 py-1 text-xs">{status}</span>
      </div>
      <KeyValueGrid
        items={[
          ["估值情景范围", summarizeValuationRange(valuation.results)],
          ["相对分位", summarizeRelativePercentile(valuation.results)],
          ["敏感性分析", sensitivity ? `${sensitivity} cells` : "insufficient_data"],
          ["不是投资建议", valuation.not_investment_advice ? "true" : "false"],
        ]}
      />
      {valuation.limitations?.length ? <p className="mt-3 text-xs text-slate-500">{valuation.limitations.join("；")}</p> : null}
    </div>
  );
}

function StatusPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-line bg-white px-2 py-1">
      <div className="text-[11px] uppercase text-slate-500">{label}</div>
      <div className="font-medium text-slate-800">{value}</div>
    </div>
  );
}

function KeyValueGrid({ items }: { items: Array<[string, unknown]> }) {
  return (
    <dl className="grid gap-3 text-sm sm:grid-cols-2">
      {items.map(([label, value]) => (
        <div key={label} className="rounded border border-line bg-slate-50 p-3">
          <dt className="text-xs text-slate-500">{label}</dt>
          <dd className="mt-1 font-medium text-slate-800">{formatValue(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function EmptyState({ text }: { text: string }) {
  return <p className="rounded border border-line bg-slate-50 p-3 text-sm text-slate-600">{text}</p>;
}

function AnalysisSectionState({ title, section }: { title: string; section: Record<string, unknown> }) {
  const warnings = Array.isArray(section.missing_data_warnings) ? section.missing_data_warnings : [];
  return (
    <div className="rounded border border-line bg-white p-3 text-sm">
      <div className="flex items-center justify-between gap-3">
        <div className="font-medium text-slate-900">{title}</div>
        <span className="text-xs text-slate-500">{String(section.state ?? "unknown")}</span>
      </div>
      {warnings.length ? <p className="mt-2 text-xs text-amber-700">{warnings.map(String).join("；")}</p> : null}
    </div>
  );
}

function settledValue<T>(result: PromiseSettledResult<T>, fallback: T): T {
  return result.status === "fulfilled" ? result.value : fallback;
}

function getCompanyName(company: Record<string, unknown> | null | undefined, symbol?: string) {
  const knownNames: Record<string, string> = {
    "600519": "贵州茅台",
  };
  const name = getString(company, "name") ?? getString(company, "company_name") ?? getString(company, "short_name");
  if (!name || name === symbol) return symbol ? knownNames[symbol] : undefined;
  return name;
}

function getString(record: Record<string, unknown> | null | undefined, key: string) {
  const value = record?.[key];
  return typeof value === "string" && value.trim() ? value : undefined;
}

function formatMetricLabel(label: string) {
  const labels: Record<string, string> = {
    net_margin: "净利率",
    cash_conversion: "经营现金流 / 净利润",
    liability_ratio: "资产负债率",
    roe_proxy: "ROE 近似值",
    gross_margin: "毛利率",
    roe: "净资产收益率",
  };
  return labels[label] ?? label.replaceAll("_", " ");
}

function formatValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "等待同步";
  if (typeof value === "number") return Number.isFinite(value) ? value.toLocaleString("zh-CN") : "无数据";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

function formatMetricCell(cell: Record<string, unknown> | undefined) {
  if (!cell) return "missing";
  if (cell.quality_status === "not_applicable") return "not_applicable";
  const value = cell.value;
  if (typeof value === "number") {
    const suffix = cell.percentile ? ` · P${Math.round(Number(cell.percentile) * 100)}` : "";
    return `${value.toLocaleString("zh-CN", { maximumFractionDigits: 2 })}${suffix}`;
  }
  return String(cell.missing_reason ?? "missing_data");
}

function getNestedString(record: Record<string, unknown>, path: string[]) {
  let current: unknown = record;
  for (const key of path) {
    if (Array.isArray(current)) {
      current = current[Number(key)];
    } else if (current && typeof current === "object") {
      current = (current as Record<string, unknown>)[key];
    } else {
      return undefined;
    }
  }
  return typeof current === "string" ? current : undefined;
}

function summarizeRelativePercentile(results: Record<string, unknown>) {
  const models = results.models;
  if (!Array.isArray(models)) return "insufficient_data";
  const first = models.find((item) => item && typeof item === "object" && typeof (item as Record<string, unknown>).peer_percentile === "number") as Record<string, unknown> | undefined;
  return first ? `${String(first.metric_code)} P${Math.round(Number(first.peer_percentile) * 100)}` : "insufficient_data";
}

function summarizeValuationRange(results: Record<string, unknown>) {
  const dcfResults = results.results;
  if (dcfResults && typeof dcfResults === "object") {
    const ev = (dcfResults as Record<string, unknown>).enterprise_value_range;
    if (ev && typeof ev === "object") {
      const base = (ev as Record<string, unknown>).base;
      return typeof base === "number" ? base.toLocaleString("zh-CN", { maximumFractionDigits: 0 }) : "insufficient_data";
    }
  }
  return "scenario range only";
}

function compactJson(value: unknown) {
  if (!value || (typeof value === "object" && Object.keys(value).length === 0)) return "无";
  return JSON.stringify(value);
}

function formatScore(scores: Array<Record<string, unknown>>, scoreId: string) {
  const score = scores.find((item) => item.score_id === scoreId);
  const value = score?.score;
  return typeof value === "number" ? value.toLocaleString("zh-CN", { maximumFractionDigits: 1 }) : "insufficient_data";
}

function formatPackList(value: unknown) {
  return Array.isArray(value) ? value.map(String).join(", ") : String(value ?? "general");
}

function formatPeriod(period: string) {
  if (period.endsWith("-03-31")) return `${period.slice(0, 4)} 一季报`;
  if (period.endsWith("-06-30")) return `${period.slice(0, 4)} 中报`;
  if (period.endsWith("-09-30")) return `${period.slice(0, 4)} 三季报`;
  if (period.endsWith("-12-31")) return `${period.slice(0, 4)} 年报`;
  return period;
}

function periodItems(period: Record<string, unknown>): Array<[string, unknown]> {
  const items: Array<[string, unknown]> = [
    ["营业收入", period.revenue],
    ["归母净利润", period.net_profit_parent ?? period.net_profit],
    ["经营现金流", period.operating_cash_flow],
    ["总资产", period.total_assets],
    ["总负债", period.total_liabilities],
    ["所有者权益", period.total_equity],
  ];
  return items.filter(([, value]) => value !== undefined && value !== null);
}

function formatMoney(value: unknown) {
  if (typeof value !== "number" || !Number.isFinite(value)) return formatValue(value);
  const yi = value / 100000000;
  return `${yi.toLocaleString("zh-CN", { maximumFractionDigits: 2, minimumFractionDigits: 2 })} 亿元`;
}

function translateGap(gap: string) {
  const gaps: Record<string, string> = {
    missing_structured_financial_facts: "还没有结构化财务数据",
    missing_local_document_evidence: "还没有导入本地公告/年报/网页证据",
    strict_as_of_enabled_unknown_publication_dates_excluded: "已按历史时点过滤未知发布日期数据",
  };
  return gaps[gap] ?? gap;
}

function buildSummary(symbol: string, periods: Array<Record<string, unknown>>, metrics: Record<string, unknown>) {
  const latest = periods[0] ?? {};
  const period = formatPeriod(String(latest.period_end ?? "最新期间"));
  const netMargin = formatMetricValue("net_margin", metrics.net_margin);
  const cash = formatMetricValue("cash_conversion", metrics.cash_conversion);
  return `${symbol} 已有 ${period} 等 ${periods.length} 个财务期间入库。最新净利率约 ${netMargin}，经营现金流/净利润约 ${cash}。这不是买卖建议，而是用于继续核验年报、公告和同业对比的研究起点。`;
}

function summaryCards(periods: Array<Record<string, unknown>>, metrics: Record<string, unknown>): Array<[string, string]> {
  const latest = periods[0] ?? {};
  return [
    ["最新收入", formatMoney(latest.revenue)],
    ["归母净利润", formatMoney(latest.net_profit_parent ?? latest.net_profit)],
    ["资产负债率", formatMetricValue("liability_ratio", metrics.liability_ratio)],
  ];
}

function formatMetricValue(key: string, value: unknown) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return formatValue(value);
  }
  if (["net_margin", "liability_ratio", "roe_proxy", "gross_margin", "roe"].includes(key)) {
    return `${(value * 100).toLocaleString("zh-CN", {
      maximumFractionDigits: 2,
      minimumFractionDigits: 2,
    })}%`;
  }
  if (key === "cash_conversion") {
    return `${value.toLocaleString("zh-CN", {
      maximumFractionDigits: 2,
      minimumFractionDigits: 2,
    })} 倍`;
  }
  return value.toLocaleString("zh-CN");
}
