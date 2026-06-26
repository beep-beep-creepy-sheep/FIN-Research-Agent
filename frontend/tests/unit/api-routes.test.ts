import { afterEach, describe, expect, it, vi } from "vitest";
import {
  API_ROUTES,
  createResearchRun,
  getAiStatus,
  getCompanyCharts,
  getCompanyMetrics,
  getConnectors,
  getMarketOverview,
  queryScreener,
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
    expect(API_ROUTES.screenerQuery).toBe("/v1/screener/query");
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
