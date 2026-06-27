import { Card } from "@/components/Card";
import { EChartPanel } from "@/charts/EChartPanel";
import {
  getCompanyBenchmark,
  getCompanyCharts,
  getCompanyFilings,
  getCompanySummary,
  getDataQualityIssues,
  getDataQualitySummary,
  type CompanySummary,
  type FilingRecord,
  type MarketChart,
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
  const results = await Promise.allSettled([
    getCompanySummary(symbol),
    getCompanyCharts(symbol),
    getCompanyFilings(symbol),
    getCompanyBenchmark(symbol),
    getDataQualitySummary(),
    getDataQualityIssues(),
  ] as const);
  summary = settledValue(results[0], null);
  charts = settledValue(results[1], []);
  filings = settledValue(results[2], []);
  benchmark = settledValue(results[3], null);
  qualitySummary = settledValue(results[4], null);
  qualityIssues = settledValue(results[5], []);
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
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        {charts.map((chart) => (
          <EChartPanel key={chart.id} chart={chart} />
        ))}
      </div>
    </main>
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

function compactJson(value: unknown) {
  if (!value || (typeof value === "object" && Object.keys(value).length === 0)) return "无";
  return JSON.stringify(value);
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
