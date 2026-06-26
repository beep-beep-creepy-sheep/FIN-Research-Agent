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

export function getCompanySummary(symbol: string): Promise<CompanySummary> {
  return fetchJson<CompanySummary>(`/v1/companies/${symbol}/summary`);
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
