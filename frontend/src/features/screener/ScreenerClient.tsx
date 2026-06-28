"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { getScreenerPresets, queryScreener, saveScreenerPreset, screenerExportUrl } from "@/lib/api";

export function ScreenerClient() {
  const [rows, setRows] = useState<Array<Record<string, unknown>>>([]);
  const [message, setMessage] = useState("尚未查询");
  const [presets, setPresets] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    const form = new FormData(event.currentTarget);
    const filters = {
      q: text(form, "q"),
      market: text(form, "market"),
      exchange: text(form, "exchange"),
      industry: text(form, "industry"),
      listing_board: text(form, "listing_board"),
      min_revenue: number(form, "min_revenue"),
      min_market_cap: number(form, "min_market_cap"),
      min_revenue_growth: percent(form, "min_revenue_growth"),
      min_net_profit_growth: percent(form, "min_net_profit_growth"),
      min_gross_margin: percent(form, "min_gross_margin"),
      min_net_margin: percent(form, "min_net_margin"),
      min_roe: percent(form, "min_roe"),
      min_roic: percent(form, "min_roic"),
      min_fcf_yield: percent(form, "min_fcf_yield"),
      max_liability_ratio: percent(form, "max_liability_ratio"),
      max_net_debt_to_ebitda: number(form, "max_net_debt_to_ebitda"),
      min_current_ratio: number(form, "min_current_ratio"),
      max_pe_ttm: number(form, "max_pe_ttm"),
      max_ev_ebitda: number(form, "max_ev_ebitda"),
      include_missing: form.get("include_missing") === "on",
      sort_by: text(form, "sort_by") || "revenue",
      sort_direction: text(form, "sort_direction") || "desc",
      limit: number(form, "limit") || 50,
    };
    try {
      const result = await queryScreener(filters);
      const resultRows = Array.isArray(result.rows) ? result.rows : [];
      setRows(resultRows as Array<Record<string, unknown>>);
      const asOf = result.as_of ? `，截至 ${String(result.as_of)}` : "，当前无可用期间";
      setMessage(`返回 ${String(result.count ?? resultRows.length)} 条，本地来源：financial_facts${asOf}`);
    } catch (error) {
      setRows([]);
      setMessage(error instanceof Error ? error.message : "查询失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <form onSubmit={onSubmit} className="grid gap-3 rounded-md border border-line bg-white p-4 lg:grid-cols-4">
        <Input name="q" placeholder="代码或公司名" />
        <Input name="market" placeholder="市场，例如 CN" />
        <Input name="exchange" placeholder="交易所，例如 SSE" />
        <Input name="industry" placeholder="行业" />
        <select name="listing_board" className="rounded-md border border-line px-3 py-2 text-sm">
          <option value="">全部板块</option>
          <option value="sse_star">科创板</option>
          <option value="chinext">创业板</option>
          <option value="bse">北交所</option>
        </select>
        <Input name="min_revenue" placeholder="最低收入，元" inputMode="decimal" />
        <Input name="min_market_cap" placeholder="最低市值，元" inputMode="decimal" />
        <Input name="min_revenue_growth" placeholder="最低收入增速，%" inputMode="decimal" />
        <Input name="min_net_profit_growth" placeholder="最低净利增速，%" inputMode="decimal" />
        <Input name="min_gross_margin" placeholder="最低毛利率，%" inputMode="decimal" />
        <Input name="min_net_margin" placeholder="最低净利率，%" inputMode="decimal" />
        <Input name="min_roe" placeholder="最低 ROE，%" inputMode="decimal" />
        <Input name="min_roic" placeholder="最低 ROIC，%" inputMode="decimal" />
        <Input name="min_fcf_yield" placeholder="最低 FCF yield，%" inputMode="decimal" />
        <Input name="max_liability_ratio" placeholder="最高资产负债率，%" inputMode="decimal" />
        <Input name="max_net_debt_to_ebitda" placeholder="最高净债务/EBITDA" inputMode="decimal" />
        <Input name="min_current_ratio" placeholder="最低流动比率" inputMode="decimal" />
        <Input name="max_pe_ttm" placeholder="最高 PE TTM" inputMode="decimal" />
        <Input name="max_ev_ebitda" placeholder="最高 EV/EBITDA" inputMode="decimal" />
        <select name="sort_by" className="rounded-md border border-line px-3 py-2 text-sm">
          <option value="revenue">按收入</option>
          <option value="net_profit">按净利润</option>
          <option value="net_margin">按净利率</option>
          <option value="roe">按 ROE</option>
          <option value="liability_ratio">按资产负债率</option>
          <option value="market_cap">按市值</option>
          <option value="fcf_yield">按 FCF yield</option>
          <option value="pe_ttm">按 PE TTM</option>
          <option value="ev_ebitda">按 EV/EBITDA</option>
        </select>
        <select name="sort_direction" className="rounded-md border border-line px-3 py-2 text-sm">
          <option value="desc">降序</option>
          <option value="asc">升序</option>
        </select>
        <Input name="limit" defaultValue="50" inputMode="numeric" />
        <label className="flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm text-slate-700">
          <input name="include_missing" type="checkbox" />
          include_missing
        </label>
        <Button type="submit" disabled={loading} className="lg:col-span-2">
          {loading ? "查询中" : "运行筛选"}
        </Button>
        <Button type="button" className="lg:col-span-1" onClick={async () => {
          await saveScreenerPreset("stage5-current-screen", { min_roe: 0.1, include_missing: true });
          setPresets(await getScreenerPresets());
          setMessage("已保存 preset：stage5-current-screen");
        }}>
          保存 preset
        </Button>
        <a className="rounded-md border border-line bg-white px-3 py-2 text-center text-sm font-medium" href={screenerExportUrl("csv")}>
          导出 CSV
        </a>
      </form>

      <div className="text-sm text-slate-600">{message}</div>
      {presets.length ? (
        <div className="rounded-md border border-line bg-white p-3 text-sm text-slate-700">
          Presets: {presets.map((preset) => String(preset.name)).join("，")}
        </div>
      ) : null}
      <div className="overflow-hidden rounded-md border border-line bg-white">
        {rows.length ? (
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs text-slate-500">
              <tr>
                <th className="px-3 py-2">代码</th>
                <th className="px-3 py-2">名称</th>
                <th className="px-3 py-2">行业</th>
                <th className="px-3 py-2">期间</th>
                <th className="px-3 py-2">收入</th>
                <th className="px-3 py-2">净利率</th>
                <th className="px-3 py-2">ROE</th>
                <th className="px-3 py-2">资产负债率</th>
                <th className="px-3 py-2">数据质量</th>
                <th className="px-3 py-2">估值状态</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={String(row.symbol)} className="border-t border-line">
                  <td className="px-3 py-2 font-medium text-accent">
                    <Link href={`/companies/${String(row.symbol)}`}>{String(row.symbol)}</Link>
                  </td>
                  <td className="px-3 py-2">{String(row.company_name ?? "")}</td>
                  <td className="px-3 py-2">{String(row.industry ?? "")}</td>
                  <td className="px-3 py-2">{String(row.period_end ?? "")}</td>
                  <td className="px-3 py-2">{money(row.revenue)}</td>
                  <td className="px-3 py-2">{pct(row.net_margin)}</td>
                  <td className="px-3 py-2">{pct(row.roe)}</td>
                  <td className="px-3 py-2">{pct(row.liability_ratio)}</td>
                  <td className="px-3 py-2">{String(row.data_quality_status ?? "unknown")}</td>
                  <td className="px-3 py-2">{String(row.valuation_status ?? "insufficient_data")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="space-y-2 p-4 text-sm text-slate-600">
            <p>没有结果。请先同步公司财务数据，或放宽筛选条件。</p>
            <p>本地来源：financial_facts；空结果不会生成模拟公司或补全指标。</p>
          </div>
        )}
      </div>
    </div>
  );
}

function text(form: FormData, key: string) {
  const value = String(form.get(key) ?? "").trim();
  return value || undefined;
}

function number(form: FormData, key: string) {
  const value = text(form, key);
  if (!value) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function percent(form: FormData, key: string) {
  const value = number(form, key);
  return value === undefined ? undefined : value / 100;
}

function numeric(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

function money(value: unknown) {
  const parsed = numeric(value);
  if (parsed === undefined) return "无数据";
  return `${(parsed / 100000000).toLocaleString("zh-CN", { maximumFractionDigits: 2 })} 亿`;
}

function pct(value: unknown) {
  const parsed = numeric(value);
  if (parsed === undefined) return "无数据";
  return `${(parsed * 100).toLocaleString("zh-CN", { maximumFractionDigits: 2 })}%`;
}
