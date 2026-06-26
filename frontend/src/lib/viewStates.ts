import type { MarketChart, MarketOverview } from "./api";

export function marketOverviewState(overview: MarketOverview | null) {
  if (!overview) return "api_unavailable";
  if (overview.snapshot.status === "no_snapshot") return "no_snapshot";
  if (overview.empty) return "empty";
  return "ready";
}

export function chartDataState(chart: MarketChart | null) {
  if (!chart) return "card_failed";
  if (chart.error) return "card_failed";
  if (chart.empty || chart.data.length === 0) return "no_data";
  return "ready";
}

export function pageChartState(charts: Array<MarketChart | null>) {
  return {
    failedCards: charts.filter((chart) => chartDataState(chart) === "card_failed").length,
    readyCards: charts.filter((chart) => chartDataState(chart) === "ready").length,
    noDataCards: charts.filter((chart) => chartDataState(chart) === "no_data").length,
  };
}

export function validateScreenerSort(sortBy: string) {
  return ["revenue", "net_profit", "net_margin", "roe", "liability_ratio"].includes(sortBy);
}

export function screenerResultState(result: Record<string, unknown>) {
  const rows = Array.isArray(result.rows) ? result.rows : [];
  return {
    empty: rows.length === 0,
    count: Number(result.count ?? rows.length),
    offset: Number(result.offset ?? 0),
    limit: Number(result.limit ?? 50),
  };
}

export function researchRunState(run: Record<string, unknown>) {
  if (run.status === "failed") return "failed";
  if (run.status === "queued" || run.status === "running") return "in_progress";
  return "ready";
}

export function ollamaState(status: Record<string, unknown>) {
  if (status.provider !== "ollama") return "disabled";
  if (status.available === false) return "unavailable";
  if (status.model_present === false) return "model_missing";
  return "available";
}

export function connectorState(connector: Record<string, unknown>) {
  if (connector.enabled === false) return "disabled";
  if (connector.configured === false) return "not_configured";
  if (connector.available === false) return connector.status ?? "unavailable";
  return "available";
}
