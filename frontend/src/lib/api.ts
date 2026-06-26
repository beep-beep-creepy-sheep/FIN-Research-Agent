const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

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

export type MarketChart = {
  id: string;
  title: string;
  kind: "pie" | "bar" | "histogram" | "line" | "candlestick";
  unit: string;
  as_of?: string | null;
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
  return fetchJson<MarketChart[]>(`/v1/companies/${symbol}/charts`);
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
  return fetchJson<Record<string, unknown>>("/v1/screener/query", {
    method: "POST",
    body: JSON.stringify(filters),
  });
}
