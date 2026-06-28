# Stage 6: AI Orchestration And Institutional Reporting

Stage 6 adds an evidence-first institutional report layer over the existing company analysis, peer comparison, valuation lab, filings, documents, and data-quality records.

## Implemented

- Research evidence bundle builder with deterministic hashes, strict `as_of_date` filtering, evidence IDs, and redaction of local file paths.
- Deterministic institutional report builder with sections for metadata, summary, company profile, financial analysis, industry-pack analysis, peers, valuation lab, risk/data quality, evidence appendix, methodology, and disclaimers.
- Optional AI orchestration boundary for local Ollama-compatible narration. LLM usage defaults off and falls back to deterministic output when disabled, unavailable, prompt-injection risk is detected, or validation rejects the response.
- Prompt-injection guard for retrieved document text.
- Unsupported-claim and forbidden wording validation before persistence.
- Report persistence in `report_runs`, `report_sections`, and `ai_prompt_audits` via Alembic revision `0006_stage6_reports`.
- Report APIs:
  - `GET /v1/companies/{symbol}/report`
  - `POST /v1/companies/{symbol}/report`
  - `GET /v1/companies/{symbol}/report/latest`
  - `GET /v1/companies/{symbol}/report/runs`
  - `GET /v1/report-runs/{run_id}`
  - `GET /v1/report-runs/{run_id}/markdown`
  - `GET /v1/report-runs/{run_id}/html`
  - `GET /v1/report-runs/{run_id}/validation`
  - `GET /v1/report-runs/{run_id}/evidence`
  - `POST /v1/report-runs/{run_id}/regenerate-section`
- Markdown, JSON, and print-friendly HTML export surfaces.
- Company-page Institutional Report panel with deterministic/AI toggle, strict-as-of toggle, language selector, section selector, validation status, evidence coverage, preview, Markdown export, HTML print view, and warnings.

## Guardrails

- The report layer does not create financial facts, market data, valuation assumptions, citations, or conclusions with an LLM.
- All numeric facts must come from the persisted evidence bundle or deterministic services.
- Report outputs are for public-information verification and audit trails, not trading instructions or broker workflows.
- Retrieved web/document content is treated as untrusted data and scanned for prompt-injection patterns.
- Local filesystem paths are redacted from report evidence payloads.

## Known Limitations

- Local Ollama integration is an optional boundary; provider availability depends on local user configuration.
- Regenerate-section currently returns deterministic current-state status unless a validated AI path is enabled and accepted.
- Live source smoke remains opt-in; Stage 6 reports are designed to work from local persisted evidence.
- Benchmark analytics still require aligned benchmark inputs when a caller wants benchmark-derived metrics.
