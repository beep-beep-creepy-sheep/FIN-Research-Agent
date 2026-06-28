"use client";

import { useState } from "react";
import { Button } from "@/components/Button";
import {
  createCompanyReport,
  reportHtmlUrl,
  reportMarkdownUrl,
  type InstitutionalReport,
} from "@/lib/api";

const SECTIONS = [
  "executive_summary",
  "financial_analysis",
  "peer_comparison",
  "valuation_lab",
  "risk_data_quality",
  "evidence_appendix",
  "methodology",
  "disclaimers",
];

export function InstitutionalReportPanel({ symbol }: { symbol: string }) {
  const [report, setReport] = useState<InstitutionalReport | null>(null);
  const [includeAi, setIncludeAi] = useState(false);
  const [strictAsOf, setStrictAsOf] = useState(true);
  const [language, setLanguage] = useState<"en" | "zh">("en");
  const [selected, setSelected] = useState<string[]>(SECTIONS);
  const [status, setStatus] = useState<"idle" | "loading" | "failed">("idle");
  const [error, setError] = useState<string | null>(null);

  async function generate() {
    setStatus("loading");
    setError(null);
    try {
      const result = await createCompanyReport(symbol, {
        strict_as_of: strictAsOf,
        include_ai: includeAi,
        include_markdown: true,
        include_html: true,
        include_evidence: true,
        force_rebuild: false,
        sections: selected,
        report_style: "institutional_full",
        language,
      });
      setReport(result);
      setStatus("idle");
    } catch (err) {
      setStatus("failed");
      setError(err instanceof Error ? err.message : "report_generation_failed");
    }
  }

  const validationStatus = String(report?.validation?.status ?? "not_run");
  const llmStatus = String(report?.llm?.status ?? (includeAi ? "not_run" : "disabled"));

  return (
    <div className="space-y-4">
      <div className="rounded border border-line bg-slate-50 p-3 text-sm text-slate-700">
        Not investment advice. This report uses local evidence and deterministic validation before display.
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <label className="rounded border border-line bg-white p-3 text-sm">
          <span className="block text-xs text-slate-500">Language</span>
          <select
            className="mt-2 w-full rounded border border-line bg-white px-2 py-2"
            value={language}
            onChange={(event) => setLanguage(event.target.value as "en" | "zh")}
          >
            <option value="en">English</option>
            <option value="zh">中文</option>
          </select>
        </label>
        <label className="flex items-center gap-2 rounded border border-line bg-white p-3 text-sm">
          <input type="checkbox" checked={strictAsOf} onChange={(event) => setStrictAsOf(event.target.checked)} />
          <span>Strict as-of</span>
        </label>
        <label className="flex items-center gap-2 rounded border border-line bg-white p-3 text-sm">
          <input type="checkbox" checked={includeAi} onChange={(event) => setIncludeAi(event.target.checked)} />
          <span>AI narrative</span>
        </label>
      </div>

      <div className="rounded border border-line bg-white p-3">
        <div className="mb-2 text-xs font-medium uppercase text-slate-500">Sections</div>
        <div className="grid gap-2 sm:grid-cols-2">
          {SECTIONS.map((section) => (
            <label key={section} className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={selected.includes(section)}
                onChange={(event) => {
                  setSelected((current) =>
                    event.target.checked ? [...current, section] : current.filter((item) => item !== section)
                  );
                }}
              />
              <span>{section.replaceAll("_", " ")}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button disabled={status === "loading" || selected.length === 0} onClick={generate}>
          {status === "loading" ? "Generating..." : "Generate Report"}
        </Button>
        <StatusBadge label="validation" value={validationStatus} />
        <StatusBadge label="AI" value={llmStatus} />
      </div>

      {status === "failed" ? (
        <div className="rounded border border-risk bg-white p-3 text-sm text-risk">
          {error ?? "Report generation failed. Check company data and local API status."}
        </div>
      ) : null}

      {report ? <ReportPreview report={report} /> : <EmptyState />}
    </div>
  );
}

function ReportPreview({ report }: { report: InstitutionalReport }) {
  const warnings = report.warnings ?? [];
  const coverage = report.evidence_coverage ?? {};
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-3">
        <Metric label="Run" value={report.run_id} />
        <Metric label="Evidence" value={`${coverage.referenced_evidence_count ?? 0}/${coverage.available_evidence_count ?? 0}`} />
        <Metric label="As of" value={report.as_of_date} />
      </div>
      {warnings.length ? (
        <div className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          {warnings.join("; ")}
        </div>
      ) : null}
      {report.limitations.length ? (
        <div className="rounded border border-line bg-slate-50 p-3 text-sm text-slate-700">
          {report.limitations.slice(0, 4).join("; ")}
        </div>
      ) : null}
      <div className="flex flex-wrap gap-2 text-sm">
        <a className="rounded border border-line px-3 py-2 text-accent" href={reportMarkdownUrl(report.run_id)}>
          Markdown
        </a>
        <a className="rounded border border-line px-3 py-2 text-accent" href={reportHtmlUrl(report.run_id)} target="_blank" rel="noreferrer">
          Print HTML
        </a>
      </div>
      <div className="max-h-96 space-y-2 overflow-auto">
        {report.sections.slice(0, 6).map((section) => (
          <div key={section.section_id} className="rounded border border-line bg-white p-3 text-sm">
            <div className="flex items-start justify-between gap-3">
              <div className="font-medium text-slate-900">{section.title}</div>
              <span className="rounded border border-line bg-slate-50 px-2 py-1 text-xs text-slate-600">{section.status}</span>
            </div>
            <pre className="mt-2 whitespace-pre-wrap break-words text-xs leading-5 text-slate-700">
              {JSON.stringify(section.content, null, 2)}
            </pre>
          </div>
        ))}
      </div>
    </div>
  );
}

function StatusBadge({ label, value }: { label: string; value: string }) {
  return (
    <span className="rounded border border-line bg-white px-3 py-2 text-xs text-slate-600">
      {label}: {value}
    </span>
  );
}

function Metric({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="rounded border border-line bg-slate-50 p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-1 break-words text-sm font-medium text-slate-900">{String(value ?? "none")}</div>
    </div>
  );
}

function EmptyState() {
  return (
    <p className="rounded border border-line bg-slate-50 p-3 text-sm text-slate-600">
      No report run yet. Generate a deterministic report after syncing company evidence.
    </p>
  );
}
