"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { queryScreener } from "@/lib/api";

export function ScreenerClient() {
  const [rows, setRows] = useState<Array<Record<string, unknown>>>([]);
  const [message, setMessage] = useState("尚未查询");
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    const form = new FormData(event.currentTarget);
    const filters = {
      q: text(form, "q"),
      industry: text(form, "industry"),
      min_revenue: number(form, "min_revenue"),
      min_net_margin: percent(form, "min_net_margin"),
      min_roe: percent(form, "min_roe"),
      max_liability_ratio: percent(form, "max_liability_ratio"),
      sort_by: text(form, "sort_by") || "revenue",
      limit: number(form, "limit") || 50,
    };
    try {
      const result = await queryScreener(filters);
      const resultRows = Array.isArray(result.rows) ? result.rows : [];
      setRows(resultRows as Array<Record<string, unknown>>);
      setMessage(`返回 ${String(result.count ?? resultRows.length)} 条，本地来源：financial_facts`);
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
        <Input name="industry" placeholder="行业" />
        <Input name="min_revenue" placeholder="最低收入，元" inputMode="decimal" />
        <Input name="min_net_margin" placeholder="最低净利率，%" inputMode="decimal" />
        <Input name="min_roe" placeholder="最低 ROE，%" inputMode="decimal" />
        <Input name="max_liability_ratio" placeholder="最高资产负债率，%" inputMode="decimal" />
        <select name="sort_by" className="rounded-md border border-line px-3 py-2 text-sm">
          <option value="revenue">按收入</option>
          <option value="net_profit">按净利润</option>
          <option value="net_margin">按净利率</option>
          <option value="roe">按 ROE</option>
          <option value="liability_ratio">按资产负债率</option>
        </select>
        <Input name="limit" defaultValue="50" inputMode="numeric" />
        <Button type="submit" disabled={loading} className="lg:col-span-4">
          {loading ? "查询中" : "运行筛选"}
        </Button>
      </form>

      <div className="text-sm text-slate-600">{message}</div>
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
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="p-4 text-sm text-slate-600">没有结果。请先同步公司财务数据，或放宽筛选条件。</p>
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
