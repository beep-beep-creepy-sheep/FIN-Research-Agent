const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const API_ROUTES = {
  companyCharts: (symbol: string) => `/v1/companies/${symbol}/charts`,
  companyChartAlias: (symbol: string) => `/v1/companies/${symbol}/chart`,
  companyPeers: (symbol: string) => `/v1/companies/${symbol}/peers`,
  companyPeerMetrics: (symbol: string) => `/v1/companies/${symbol}/peer-metrics`,
  companyValuation: (symbol: string) => `/v1/companies/${symbol}/valuation`,
  companyReport: (symbol: string) => `/v1/companies/${symbol}/report`,
  companyReportLatest: (symbol: string) => `/v1/companies/${symbol}/report/latest`,
  companyReportRuns: (symbol: string) => `/v1/companies/${symbol}/report/runs`,
  reportRun: (runId: string) => `/v1/report-runs/${runId}`,
  reportMarkdown: (runId: string) => `/v1/report-runs/${runId}/markdown`,
  reportHtml: (runId: string) => `/v1/report-runs/${runId}/html`,
  reportValidation: (runId: string) => `/v1/report-runs/${runId}/validation`,
  reportEvidence: (runId: string) => `/v1/report-runs/${runId}/evidence`,
  portfolios: "/v1/portfolios",
  portfolio: (portfolioId: string | number) => `/v1/portfolios/${portfolioId}`,
  portfolioHoldings: (portfolioId: string | number) => `/v1/portfolios/${portfolioId}/holdings`,
  portfolioWatchItems: (portfolioId: string | number) => `/v1/portfolios/${portfolioId}/watch-items`,
  portfolioSummary: (portfolioId: string | number) => `/v1/portfolios/${portfolioId}/summary`,
  portfolioExposure: (portfolioId: string | number) => `/v1/portfolios/${portfolioId}/exposure`,
  portfolioRisk: (portfolioId: string | number) => `/v1/portfolios/${portfolioId}/risk`,
  portfolioPerformance: (portfolioId: string | number) => `/v1/portfolios/${portfolioId}/performance`,
  portfolioDataQuality: (portfolioId: string | number) => `/v1/portfolios/${portfolioId}/data-quality`,
  portfolioReport: (portfolioId: string | number) => `/v1/portfolios/${portfolioId}/report`,
  portfolioAlertRules: (portfolioId: string | number) => `/v1/portfolios/${portfolioId}/alerts/rules`,
  portfolioAlertEvents: (portfolioId: string | number) => `/v1/portfolios/${portfolioId}/alerts/events`,
  portfolioAlertEvaluate: (portfolioId: string | number) => `/v1/portfolios/${portfolioId}/alerts/evaluate`,
  calendarEvents: "/v1/calendar/events",
  screenerQuery: "/v1/screener/query",
  screenerPresets: "/v1/screener/presets",
  screenerExport: "/v1/screener/export",
  screensQueryAlias: "/v1/screens/query",
} as const;

export type CompanySummary = {
  symbol: string;
  company?: Record<string, unknown> | null;
  periods: Array<Record<string, unknown>>;
  metrics: Record<string, unknown>;
  quality_flags: string[];
  evidence: Array<Record<string, unknown>>;
  data_gaps: string[];
  generated_at: string;
};

export type MetricObservation = {
  code: string;
  implementation_status?: string | null;
  value?: number | null;
  quality_status?: string | null;
  missing_reason?: string | null;
  warnings?: string[];
  formula?: string;
  inputs?: Record<string, unknown>;
  source_fact_ids?: number[];
  source_price_ids?: number[];
  as_of?: string | null;
  calculation_version?: string | null;
};

export type MarketChart = {
  id: string;
  title: string;
  kind: "pie" | "bar" | "histogram" | "line" | "candlestick";
  unit: string;
  as_of?: string | null;
  frequency?: string | null;
  currency?: string | null;
  updated_at?: string | null;
  quality_status?: string | null;
  warnings?: string[];
  error?: string | null;
  source: string;
  empty: boolean;
  note?: string;
  data: Array<Record<string, number | string | null | undefined> & { name: string }>;
  series?: Array<{ name: string; field: string }>;
};

export type MarketOverview = {
  market: string;
  snapshot: Record<string, unknown>;
  breadth: Record<string, unknown> | null;
  sectors: Array<Record<string, unknown>>;
  indices: Array<Record<string, unknown>>;
  movers: Record<string, Array<Record<string, unknown>>>;
  charts: MarketChart[];
  empty: boolean;
};

export type FilingRecord = {
  id: number;
  title?: string | null;
  filing_type?: string | null;
  report_period?: string | null;
  publication_date?: string | null;
  source_id?: string | null;
  source_tier?: string | null;
  verification_status?: string | null;
  download_status?: string | null;
  parse_status?: string | null;
  canonical_url?: string | null;
  sha256?: string | null;
  error_message?: string | null;
};

export type AnalysisFinding = {
  finding_id: string;
  category: string;
  title: string;
  severity: string;
  direction: string;
  summary: string;
  metric_codes?: string[];
  values_used?: Record<string, unknown>;
  source_fact_ids?: number[];
  source_price_ids?: number[];
  evidence?: Array<Record<string, unknown>>;
  limitations?: string[];
};

export type AnalysisReport = {
  symbol: string;
  executive_summary: string;
  key_findings: AnalysisFinding[];
  financial_profile: Record<string, unknown>;
  growth: Record<string, unknown>;
  profitability: Record<string, unknown>;
  cash_flow_quality: Record<string, unknown>;
  balance_sheet: Record<string, unknown>;
  efficiency: Record<string, unknown>;
  earnings_quality: Record<string, unknown>;
  industry_specific: Record<string, unknown>;
  market_risk: Record<string, unknown>;
  data_quality: Record<string, unknown>;
  evidence_map: Array<Record<string, unknown>>;
  scores: Array<Record<string, unknown>>;
  quality_flags: Array<Record<string, unknown>>;
  risk_flags: Array<Record<string, unknown>>;
  limitations: string[];
  markdown?: string | null;
  generated_at: string;
  analysis_version: string;
};

export type PeerSetResponse = {
  symbol: string;
  as_of_date: string;
  selected_symbols: string[];
  quality_flags: string[];
  limitations: string[];
  candidates: Array<Record<string, unknown>>;
};

export type PeerMetricsResponse = {
  symbol: string;
  columns: string[];
  rows: Array<Record<string, unknown>>;
  outlier_policy: string;
  limitations: string[];
};

export type ValuationResponse = {
  valuation_run_id: string;
  symbol: string;
  as_of_date: string;
  model_type: string;
  scenario_name: string;
  results: Record<string, unknown>;
  sensitivity?: Record<string, unknown> | null;
  evidence?: Record<string, unknown>;
  limitations: string[];
  not_investment_advice: boolean;
};

export type InstitutionalReportSection = {
  section_id: string;
  title: string;
  status: string;
  content: Record<string, unknown>;
  evidence_ids?: string[];
  limitations?: string[];
  generated_by?: string;
  validation_status?: string;
};

export type InstitutionalReport = {
  run_id: string;
  symbol: string;
  as_of_date: string;
  strict_as_of: boolean;
  report_style: string;
  language: string;
  sections: InstitutionalReportSection[];
  validation: Record<string, unknown>;
  evidence_coverage: Record<string, unknown>;
  warnings: string[];
  limitations: string[];
  llm: Record<string, unknown>;
  bundle_hash: string;
  report_hash: string;
  generated_at: string;
  report_version: string;
  markdown?: string | null;
  html?: string | null;
  evidence?: Record<string, unknown> | null;
};

export type ReportRequest = {
  as_of_date?: string | null;
  strict_as_of?: boolean;
  include_ai?: boolean;
  include_markdown?: boolean;
  include_html?: boolean;
  include_evidence?: boolean;
  force_rebuild?: boolean;
  sections?: string[];
  report_style?: string;
  language?: "en" | "zh";
};

export type PortfolioRecord = {
  id: number;
  name: string;
  description?: string | null;
  base_currency: string;
  portfolio_type: string;
  archived?: boolean;
  holdings_count?: number;
  watch_count?: number;
  open_alerts?: number;
  next_known_events?: number;
};

export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

export async function uploadDocument(formData: FormData): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE}/v1/documents/upload`, {
    method: "POST",
    body: formData,
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${await response.text()}`);
  }
  return response.json() as Promise<Record<string, unknown>>;
}

export function getCompanySummary(symbol: string): Promise<CompanySummary> {
  return fetchJson<CompanySummary>(`/v1/companies/${symbol}/summary`);
}

export function getCompanyCharts(symbol: string): Promise<MarketChart[]> {
  return fetchJson<MarketChart[]>(API_ROUTES.companyCharts(symbol));
}

export function getCompanyMetrics(symbol: string): Promise<MetricObservation[]> {
  return fetchJson<MetricObservation[]>(`/v1/financials/${symbol}/metrics`);
}

export function createSyncJob(symbol: string, years = 5): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>("/v1/jobs", {
    method: "POST",
    body: JSON.stringify({ symbol, years, job_type: "sync_company" }),
  });
}

export function getConnectors(): Promise<Array<Record<string, unknown>>> {
  return fetchJson<Array<Record<string, unknown>>>("/v1/connectors");
}

export function getJob(jobId: string | number): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(`/v1/jobs/${jobId}`);
}

export function createResearchRun(symbol: string, years = 5): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>("/v1/research-runs", {
    method: "POST",
    body: JSON.stringify({ symbol, years }),
  });
}

export function getResearchRuns(): Promise<Array<Record<string, unknown>>> {
  return fetchJson<Array<Record<string, unknown>>>("/v1/research-runs");
}

export function getAiStatus(): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>("/v1/ai/status");
}

export function getMarketOverview(market = "CN"): Promise<MarketOverview> {
  return fetchJson<MarketOverview>(`/v1/market/overview?market=${encodeURIComponent(market)}`);
}

export function createMarketSnapshotJob(market = "CN"): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>("/v1/jobs", {
    method: "POST",
    body: JSON.stringify({ job_type: "market_snapshot", market }),
  });
}

export function queryScreener(filters: Record<string, unknown>): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(API_ROUTES.screenerQuery, {
    method: "POST",
    body: JSON.stringify(filters),
  });
}

export function screenerExportUrl(fmt = "csv") {
  return `${API_BASE}${API_ROUTES.screenerExport}?fmt=${encodeURIComponent(fmt)}`;
}

export function getScreenerPresets(): Promise<Array<Record<string, unknown>>> {
  return fetchJson<Array<Record<string, unknown>>>(API_ROUTES.screenerPresets);
}

export function saveScreenerPreset(name: string, filters: Record<string, unknown>): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(API_ROUTES.screenerPresets, {
    method: "POST",
    body: JSON.stringify({ name, filters }),
  });
}

export function getCompanyPeers(symbol: string): Promise<PeerSetResponse> {
  return fetchJson<PeerSetResponse>(API_ROUTES.companyPeers(symbol));
}

export function getCompanyPeerMetrics(symbol: string): Promise<PeerMetricsResponse> {
  return fetchJson<PeerMetricsResponse>(API_ROUTES.companyPeerMetrics(symbol));
}

export function getCompanyValuation(symbol: string, modelType = "relative_valuation"): Promise<ValuationResponse> {
  return fetchJson<ValuationResponse>(`${API_ROUTES.companyValuation(symbol)}?model_type=${encodeURIComponent(modelType)}`);
}

export function getPortfolios(): Promise<PortfolioRecord[]> {
  return fetchJson<PortfolioRecord[]>(API_ROUTES.portfolios);
}

export function createPortfolio(payload: Record<string, unknown>): Promise<PortfolioRecord> {
  return fetchJson<PortfolioRecord>(API_ROUTES.portfolios, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getPortfolio(portfolioId: string | number): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(API_ROUTES.portfolio(portfolioId));
}

export function addPortfolioHolding(portfolioId: string | number, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(API_ROUTES.portfolioHoldings(portfolioId), {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function addPortfolioWatchItem(portfolioId: string | number, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(API_ROUTES.portfolioWatchItems(portfolioId), {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getPortfolioSummary(portfolioId: string | number): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(API_ROUTES.portfolioSummary(portfolioId));
}

export function getPortfolioExposure(portfolioId: string | number): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(API_ROUTES.portfolioExposure(portfolioId));
}

export function getPortfolioRisk(portfolioId: string | number): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(API_ROUTES.portfolioRisk(portfolioId));
}

export function getPortfolioPerformance(portfolioId: string | number): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(API_ROUTES.portfolioPerformance(portfolioId));
}

export function getPortfolioReport(portfolioId: string | number): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(API_ROUTES.portfolioReport(portfolioId));
}

export function createPortfolioAlertRule(portfolioId: string | number, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(API_ROUTES.portfolioAlertRules(portfolioId), {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function evaluatePortfolioAlerts(portfolioId: string | number): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(API_ROUTES.portfolioAlertEvaluate(portfolioId), { method: "POST" });
}

export function getCalendarEvents(query = ""): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(`${API_ROUTES.calendarEvents}${query}`);
}

export function createCalendarEvent(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(API_ROUTES.calendarEvents, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createCompanyReport(symbol: string, request: ReportRequest): Promise<InstitutionalReport> {
  return fetchJson<InstitutionalReport>(API_ROUTES.companyReport(symbol), {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function getCompanyReport(symbol: string): Promise<InstitutionalReport> {
  return fetchJson<InstitutionalReport>(`${API_ROUTES.companyReport(symbol)}?include_markdown=true&include_html=true&include_evidence=true`);
}

export function reportMarkdownUrl(runId: string) {
  return `${API_BASE}${API_ROUTES.reportMarkdown(runId)}`;
}

export function reportHtmlUrl(runId: string) {
  return `${API_BASE}${API_ROUTES.reportHtml(runId)}`;
}

export function getCompanyFilings(symbol: string): Promise<FilingRecord[]> {
  return fetchJson<FilingRecord[]>(`/v1/companies/${symbol}/filings`);
}

export function createOfficialFilingSyncJob(symbol: string): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(`/v1/companies/${symbol}/filings/sync`, {
    method: "POST",
    body: JSON.stringify({ source_ids: ["cninfo", "sse", "szse", "bse"], download: true, parse: true }),
  });
}

export function getCompanyBenchmark(symbol: string): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(`/v1/companies/${symbol}/benchmark`);
}

export function getCompanyAnalysis(symbol: string): Promise<AnalysisReport> {
  return fetchJson<AnalysisReport>(`/v1/companies/${symbol}/analysis?include_evidence=true`);
}

export function getDataQualitySummary(): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>("/v1/data-quality/summary");
}

export function getDataQualityIssues(): Promise<Array<Record<string, unknown>>> {
  return fetchJson<Array<Record<string, unknown>>>("/v1/data-quality/issues?limit=10");
}
