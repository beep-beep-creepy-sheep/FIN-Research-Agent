"use client";

import { useEffect, useMemo, useRef } from "react";
import * as echarts from "echarts";
import type { MarketChart } from "@/lib/api";

export function EChartPanel({ chart }: { chart: MarketChart }) {
  const elementRef = useRef<HTMLDivElement | null>(null);
  const option = useMemo(() => buildOption(chart), [chart]);

  useEffect(() => {
    if (!elementRef.current || chart.empty) return;
    const instance = echarts.init(elementRef.current);
    instance.setOption(option);
    const resize = () => instance.resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      instance.dispose();
    };
  }, [chart.empty, option]);

  return (
    <div className="rounded-md border border-line bg-white p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">{chart.title}</h2>
          <p className="mt-1 text-xs text-slate-500">
            {formatAsOf(chart.as_of)} · 单位：{chart.unit} · {chart.source}
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
    </div>
  );
}

function buildOption(chart: MarketChart): echarts.EChartsOption {
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
  return {
    color: ["#0f766e"],
    tooltip: { trigger: "axis" },
    grid: { left: 44, right: 18, top: 18, bottom: 44 },
    xAxis: { type: "category", data: names, axisLabel: { interval: 0, rotate: names.length > 6 ? 35 : 0 } },
    yAxis: { type: "value", name: chart.unit },
    series: [{ type: "bar", data: values, barMaxWidth: 32 }],
  };
}

function numberValue(value: number | string | null) {
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
