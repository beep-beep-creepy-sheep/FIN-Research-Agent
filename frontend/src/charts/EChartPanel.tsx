"use client";

import { useEffect, useMemo, useRef } from "react";
import type { MarketChart } from "@/lib/api";

export function EChartPanel({ chart }: { chart: MarketChart }) {
  const elementRef = useRef<HTMLDivElement | null>(null);
  const option = useMemo(() => buildOption(chart), [chart]);

  useEffect(() => {
    if (!elementRef.current || chart.empty) return;
    let instance: { setOption: (value: EChartOption) => void; resize: () => void; dispose: () => void } | null = null;
    let active = true;
    const resize = () => instance?.resize();
    import("echarts").then((echarts) => {
      if (!active || !elementRef.current) return;
      instance = echarts.init(elementRef.current);
      instance.setOption(option);
      window.addEventListener("resize", resize);
    });
    return () => {
      active = false;
      window.removeEventListener("resize", resize);
      instance?.dispose();
    };
  }, [chart.empty, option]);

  return (
    <div className="rounded-md border border-line bg-white p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">{chart.title}</h2>
          <p className="mt-1 text-xs text-slate-500">
            {formatAsOf(chart.as_of)} · 频率：{chart.frequency ?? "未标注"} · 单位：{chart.unit}
            {chart.currency ? ` · 币种：${chart.currency}` : ""} · {chart.source}
          </p>
        </div>
        <span className="rounded bg-slate-100 px-2 py-1 text-xs text-slate-600">{chart.kind}</span>
      </div>
      {chart.empty ? (
        <div className="flex h-64 items-center justify-center rounded border border-dashed border-line bg-slate-50 text-sm text-slate-500">
          暂无可绘制数据
        </div>
      ) : (
        <div ref={elementRef} className="h-64 w-full" />
      )}
      {chart.note ? <p className="mt-3 text-xs leading-5 text-slate-500">{chart.note}</p> : null}
      {chart.warnings?.length ? (
        <p className="mt-2 text-xs leading-5 text-amber-700">提示：{chart.warnings.join("、")}</p>
      ) : null}
    </div>
  );
}

type EChartOption = Record<string, unknown>;

function buildOption(chart: MarketChart): EChartOption {
  const names = chart.data.map((item) => item.name);
  const values = chart.data.map((item) => numberValue(item.value));
  if (chart.kind === "pie") {
    return {
      color: ["#0f766e", "#b91c1c", "#64748b", "#ca8a04"],
      tooltip: { trigger: "item" },
      series: [
        {
          type: "pie",
          radius: ["42%", "72%"],
          data: chart.data.map((item) => ({ name: item.name, value: numberValue(item.value) })),
        },
      ],
    };
  }
  if (chart.kind === "candlestick") {
    return {
      color: ["#0f766e", "#b91c1c"],
      tooltip: { trigger: "axis" },
      grid: [
        { left: 48, right: 18, top: 18, height: 132 },
        { left: 48, right: 18, top: 178, height: 48 },
      ],
      xAxis: [
        { type: "category", data: names },
        { type: "category", data: names, gridIndex: 1, axisLabel: { show: false } },
      ],
      yAxis: [{ scale: true }, { gridIndex: 1, name: "量" }],
      series: [
        {
          type: "candlestick",
          data: chart.data.map((item) => {
            const row = item as Record<string, unknown>;
            return [
              numberValue(row.open as number | string | null),
              numberValue(row.close as number | string | null),
              numberValue(row.low as number | string | null),
              numberValue(row.high as number | string | null),
            ];
          }),
        },
        {
          type: "bar",
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: chart.data.map((item) => numberValue((item as Record<string, unknown>).volume as number | string | null)),
          barMaxWidth: 16,
        },
      ],
    };
  }
  if (chart.kind === "line") {
    const series = chart.series?.length ? chart.series : [{ name: chart.title, field: "value" }];
    return {
      color: ["#0f766e", "#2563eb", "#b91c1c", "#ca8a04"],
      tooltip: { trigger: "axis" },
      legend: { top: 0, right: 0 },
      grid: { left: 52, right: 18, top: 36, bottom: 44 },
      xAxis: { type: "category", data: names, axisLabel: { interval: 0, rotate: names.length > 6 ? 35 : 0 } },
      yAxis: { type: "value", name: chart.unit },
      series: series.map((item) => ({
        name: item.name,
        type: "line",
        smooth: true,
        showSymbol: false,
        data: chart.data.map((row) => numberValue((row as Record<string, unknown>)[item.field] as number | string | null)),
      })),
    };
  }
  return {
    color: ["#0f766e"],
    tooltip: { trigger: "axis" },
    grid: { left: 44, right: 18, top: 18, bottom: 44 },
    xAxis: { type: "category", data: names, axisLabel: { interval: 0, rotate: names.length > 6 ? 35 : 0 } },
    yAxis: { type: "value", name: chart.unit },
    series: [{ type: "bar", data: values, barMaxWidth: 32 }],
  };
}

function numberValue(value: number | string | null | undefined) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

function formatAsOf(value: string | null | undefined) {
  if (!value) return "时间：未生成";
  return `时间：${value}`;
}
