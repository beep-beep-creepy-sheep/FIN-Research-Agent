import { afterEach, describe, expect, it, vi } from "vitest";
import {
  API_ROUTES,
  createResearchRun,
  getAiStatus,
  getCompanyAnalysis,
  getCompanyCharts,
  getCompanyPeerMetrics,
  getCompanyPeers,
  getCompanyValuation,
  getCompanyMetrics,
  getConnectors,
  getMarketOverview,
  getScreenerPresets,
  queryScreener,
  saveScreenerPreset,
  screenerExportUrl,
} from "../../src/lib/api";
import {
  chartDataState,
  connectorState,
  marketOverviewState,
  metricObservationState,
  ollamaState,
  pageChartState,
  researchRunState,
  screenerResultState,
  validateScreenerSort,
} from "../../src/lib/viewStates";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("frontend API route contract", () => {
  it("uses canonical routes while documenting compatibility aliases", () => {
    expect(API_ROUTES.companyCharts("600519")).toBe("/v1/companies/600519/charts");
    expect(API_ROUTES.companyChartAlias("600519")).toBe("/v1/companies/600519/chart");
    expect(API_ROUTES.companyPeers("600519")).toBe("/v1/companies/600519/peers");
    expect(API_ROUTES.companyPeerMetrics("600519")).toBe("/v1/companies/600519/peer-metrics");
    expect(API_ROUTES.companyValuation("600519")).toBe("/v1/companies/600519/valuation");
    expect(API_ROUTES.screenerQuery).toBe("/v1/screener/query");
    expect(API_ROUTES.screenerPresets).toBe("/v1/screener/presets");
    expect(API_ROUTES.screenerExport).toBe("/v1/screener/export");
    expect(API_ROUTES.screensQueryAlias).toBe("/v1/screens/query");
  });

  it("surfaces market API failures instead of treating HTTP errors as empty data", async () => {
    mockFetch(503, { detail: "market unavailable" });

    await expect(getMarketOverview()).rejects.toThrow("API 503");
  });

  it("classifies no_snapshot as an explicit empty market state", () => {
    expect(
      marketOverviewState({
        market: "CN",
        snapshot: { status: "no_snapshot" },
        breadth: null,
        sectors: [],
        indices: [],
        movers: { gainers: [], losers: [], turnover: [] },
        charts: [],
        empty: true,
      })
    ).toBe("no_snapshot");
  });

  it("keeps a failed market card isolated from the rest of the page", () => {
    const summary = pageChartState([
      {
        id: "breadth",
        title: "涨跌家数",
        kind: "pie",
        unit: "家",
        source: "market_breadth_snapshots",
        empty: false,
        data: [{ name: "上涨", value: 1 }],
      },
      {
        id: "sector",
        title: "板块",
        kind: "bar",
        unit: "%",
        source: "sector_snapshots",
        empty: false,
        error: "source_timeout",
        data: [],
      },
    ]);

    expect(summary).toEqual({ failedCards: 1, readyCards: 1, noDataCards: 0 });
  });

  it("classifies K-line charts with no rows as no_data", async () => {
    mockFetch(200, [
      {
        id: "kline_volume",
        title: "K线与成交量",
        kind: "candlestick",
        unit: "CNY",
        source: "prices",
        empty: true,
        data: [],
      },
    ]);

    const charts = await getCompanyCharts("600519");
    expect(chartDataState(charts[0])).toBe("no_data");
  });

  it("classifies screener empty results and preserves pagination", () => {
    expect(screenerResultState({ rows: [], count: 0, offset: 50, limit: 25 })).toEqual({
      empty: true,
      count: 0,
      offset: 50,
      limit: 25,
    });
  });

  it("rejects invalid screener sort before presenting it as a valid option", async () => {
    expect(validateScreenerSort("made_up_metric")).toBe(false);
    mockFetch(400, { detail: "invalid_sort_by:made_up_metric" });

    await expect(queryScreener({ sort_by: "made_up_metric" })).rejects.toThrow(
      "invalid_sort_by"
    );
  });

  it("sends screener pagination parameters to the backend", async () => {
    const calls: RequestInit[] = [];
    vi.stubGlobal("fetch", async (_url: string, init?: RequestInit) => {
      calls.push(init ?? {});
      return jsonResponse(200, { rows: [], count: 0, offset: 100, limit: 50 });
    });

    await queryScreener({ offset: 100, limit: 50 });

    expect(JSON.parse(String(calls[0].body))).toMatchObject({ offset: 100, limit: 50 });
  });

  it("classifies failed background research runs", async () => {
    mockFetch(200, { id: 7, status: "failed", error_message: "connector timeout" });

    const run = await createResearchRun("600519");
    expect(researchRunState(run)).toBe("failed");
  });

  it("classifies Ollama unavailable status", async () => {
    mockFetch(200, { enabled: true, provider: "ollama", available: false });

    expect(ollamaState(await getAiStatus())).toBe("unavailable");
  });

  it("classifies disabled connectors without exposing secrets", async () => {
    mockFetch(200, [
      {
        name: "agent_reach_exa",
        enabled: false,
        configured: false,
        available: false,
        status: "disabled",
      },
    ]);

    const connectors = await getConnectors();
    expect(connectorState(connectors[0])).toBe("disabled");
    expect(JSON.stringify(connectors[0])).not.toMatch(/cookie|token|password/i);
  });

  it("classifies metric states without collapsing them into a generic empty state", async () => {
    mockFetch(200, [
      {
        code: "pe_ttm",
        implementation_status: "implemented",
        value: null,
        quality_status: "missing",
        missing_reason: "insufficient_contiguous_quarters",
      },
    ]);

    const metrics = await getCompanyMetrics("600519");

    expect(metricObservationState(metrics[0])).toBe("implemented_missing_data");
    expect(metricObservationState({ code: "beta", implementation_status: "defined_only" })).toBe(
      "not_implemented"
    );
    expect(
      metricObservationState({
        code: "ev_to_ebitda",
        implementation_status: "implemented",
        quality_status: "not_applicable",
      })
    ).toBe("not_applicable");
    expect(
      metricObservationState({
        code: "enterprise_value",
        implementation_status: "implemented",
        value: 10,
        warnings: ["basic_ev"],
      })
    ).toBe("calculated_with_warnings");
  });

  it("fetches deterministic professional analysis reports", async () => {
    mockFetch(200, {
      symbol: "600519",
      executive_summary: "deterministic report",
      key_findings: [],
      financial_profile: { industry_packs: ["general"] },
      growth: { state: "insufficient" },
      profitability: { state: "insufficient" },
      cash_flow_quality: { state: "insufficient" },
      balance_sheet: { state: "insufficient" },
      efficiency: { state: "insufficient" },
      earnings_quality: { state: "insufficient" },
      industry_specific: { state: "insufficient" },
      market_risk: { state: "insufficient" },
      data_quality: { state: "insufficient" },
      evidence_map: [],
      scores: [],
      quality_flags: [],
      risk_flags: [],
      limitations: [],
      generated_at: "2026-06-28T00:00:00Z",
      analysis_version: "4.0.0",
    });

    const report = await getCompanyAnalysis("600519");

    expect(report.analysis_version).toBe("4.0.0");
    expect(report.executive_summary).toContain("deterministic");
  });

  it("fetches stage 5 peers, valuation, presets, and export routes without advice wording", async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      return jsonResponse(200, {
        symbol: "600519",
        as_of_date: "2026-06-28",
        selected_symbols: ["600000"],
        quality_flags: [],
        limitations: [],
        candidates: [],
        columns: ["revenue"],
        rows: [],
        outlier_policy: "iqr",
        valuation_run_id: "val_1",
        model_type: "relative_valuation",
        scenario_name: "base",
        results: { models: [] },
        sensitivity: { table: [] },
        evidence: {},
        not_investment_advice: true,
      });
    });

    await getCompanyPeers("600519");
    await getCompanyPeerMetrics("600519");
    const valuation = await getCompanyValuation("600519", "dcf_owner_earnings");
    await getScreenerPresets();
    await saveScreenerPreset("stage5", { include_missing: true });

    expect(calls.map((call) => call.url).join("\n")).toContain("/v1/companies/600519/peers");
    expect(calls.map((call) => call.url).join("\n")).toContain("model_type=dcf_owner_earnings");
    expect(screenerExportUrl("csv")).toContain("/v1/screener/export?fmt=csv");
    expect(JSON.stringify(valuation).toLowerCase()).not.toMatch(/target price|买入|卖出|持有/);
  });
});

function mockFetch(status: number, payload: unknown) {
  vi.stubGlobal("fetch", async () => jsonResponse(status, payload));
}

function jsonResponse(status: number, payload: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(payload),
    json: async () => payload,
  } as Response;
}
