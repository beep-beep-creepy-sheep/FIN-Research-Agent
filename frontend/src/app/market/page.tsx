import Link from "next/link";
import { EChartPanel } from "@/charts/EChartPanel";
import { Card } from "@/components/Card";
import { MarketRefreshButton } from "@/features/market/MarketRefreshButton";
import { getMarketOverview } from "@/lib/api";

export default async function MarketPage() {
  const overview = await loadOverview();
  const snapshot = overview.snapshot;

  return (
    <main className="mx-auto max-w-7xl px-6 py-8">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-accent">Market Terminal · 本地快照</p>
          <h1 className="mt-1 text-3xl font-semibold">市场终端</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            {String(snapshot.headline ?? "市场快照尚未生成。")}
          </p>
        </div>
        <MarketRefreshButton market={overview.market} />
      </div>

      <div className="mb-4 grid gap-3 md:grid-cols-4">
        {summaryTiles(snapshot).map(([label, value]) => (
          <div key={label} className="rounded-md border border-line bg-white p-4">
            <div className="text-xs text-slate-500">{label}</div>
            <div className="mt-2 text-xl font-semibold text-slate-900">{value}</div>
          </div>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        {overview.charts.map((chart) => (
          <EChartPanel key={chart.id} chart={chart} />
        ))}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card title="涨幅前列">
          <MoverList rows={overview.movers.gainers ?? []} emptyText="暂无涨幅数据" />
        </Card>
        <Card title="跌幅前列">
          <MoverList rows={overview.movers.losers ?? []} emptyText="暂无跌幅数据" />
        </Card>
        <Card title="成交额前列">
          <MoverList rows={overview.movers.turnover ?? []} emptyText="暂无成交额数据" />
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[2fr_1fr]">
        <Card title="板块快照">
          {overview.sectors.length ? (
            <div className="max-h-96 overflow-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-xs text-slate-500">
                  <tr>
                    <th className="py-2">板块</th>
                    <th className="py-2">成分</th>
                    <th className="py-2">上涨</th>
                    <th className="py-2">下跌</th>
                    <th className="py-2">均涨跌</th>
                  </tr>
                </thead>
                <tbody>
                  {overview.sectors.map((sector) => (
                    <tr key={String(sector.sector_code)} className="border-t border-line">
                      <td className="py-2 font-medium">{String(sector.sector_name)}</td>
                      <td className="py-2">{formatNumber(sector.constituents_count)}</td>
                      <td className="py-2">{formatNumber(sector.advance_count)}</td>
                      <td className="py-2">{formatNumber(sector.decline_count)}</td>
                      <td className="py-2">{formatPercent(sector.avg_change_pct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty text="暂无板块快照；先同步公司行情或运行市场快照任务。" />
          )}
        </Card>
        <Card title="数据质量">
          <div className="space-y-3 text-sm text-slate-700">
            <KeyValue label="状态" value={String(snapshot.status ?? "unknown")} />
            <KeyValue label="市场" value={overview.market} />
            <KeyValue label="来源数" value={formatNumber(snapshot.source_count)} />
            <KeyValue label="证券覆盖" value={formatNumber(getNested(snapshot, "coverage", "security_quotes"))} />
            <KeyValue label="板块覆盖" value={formatNumber(getNested(snapshot, "coverage", "sectors"))} />
            <Link href="/" className="inline-block text-sm font-medium text-accent">
              返回工作台
            </Link>
          </div>
        </Card>
      </div>
    </main>
  );
}

async function loadOverview() {
  try {
    return await getMarketOverview("CN");
  } catch {
    return {
      market: "CN",
      snapshot: {
        status: "api_unavailable",
        headline: "后端 API 暂不可用。",
        summary: {},
        coverage: {},
        source_count: 0,
      },
      breadth: null,
      sectors: [],
      indices: [],
      movers: { gainers: [], losers: [], turnover: [] },
      charts: [],
      empty: true,
    };
  }
}

function summaryTiles(snapshot: Record<string, unknown>): Array<[string, string]> {
  return [
    ["证券覆盖", formatNumber(getNested(snapshot, "summary", "universe_count"))],
    ["上涨家数", formatNumber(getNested(snapshot, "summary", "advance_count"))],
    ["下跌家数", formatNumber(getNested(snapshot, "summary", "decline_count"))],
    ["成交额", formatMoney(getNested(snapshot, "summary", "total_amount"))],
  ];
}

function MoverList({ rows, emptyText }: { rows: Array<Record<string, unknown>>; emptyText: string }) {
  if (!rows.length) return <Empty text={emptyText} />;
  return (
    <div className="space-y-2">
      {rows.slice(0, 10).map((row) => (
        <Link
          key={`${String(row.symbol)}-${String(row.trade_date)}`}
          href={`/companies/${String(row.symbol)}`}
          className="grid grid-cols-[1fr_auto] gap-3 rounded border border-line bg-slate-50 p-3 text-sm"
        >
          <span>
            <span className="font-medium text-slate-900">{String(row.symbol)}</span>
            <span className="ml-2 text-slate-500">{String(row.name ?? "")}</span>
          </span>
          <span className={numberValue(row.change_pct) >= 0 ? "text-accent" : "text-risk"}>
            {formatPercent(row.change_pct)}
          </span>
        </Link>
      ))}
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="rounded border border-line bg-slate-50 p-3 text-sm text-slate-600">{text}</p>;
}

function KeyValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-line pb-2">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium text-slate-900">{value}</span>
    </div>
  );
}

function getNested(record: Record<string, unknown>, key: string, child: string) {
  const value = record[key];
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
  return (value as Record<string, unknown>)[child];
}

function numberValue(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

function formatNumber(value: unknown) {
  const number = numberValue(value);
  return number ? number.toLocaleString("zh-CN") : "0";
}

function formatPercent(value: unknown) {
  const number = numberValue(value);
  return `${(number * 100).toLocaleString("zh-CN", { maximumFractionDigits: 2, minimumFractionDigits: 2 })}%`;
}

function formatMoney(value: unknown) {
  const number = numberValue(value);
  if (!number) return "0";
  return `${(number / 100000000).toLocaleString("zh-CN", { maximumFractionDigits: 2 })} 亿`;
}
