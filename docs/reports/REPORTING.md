# Institutional Reporting

Stage 6 adds an institutional report layer that is evidence-first and local-first. It assembles a Research Evidence Bundle from persisted company metadata, financial facts, prices, filings, documents, data-quality issues, professional analysis, peers, peer metrics, and valuation runs.

## Evidence Bundle

The bundle is built by `ResearchEvidenceBundleBuilder` and includes:

- `symbol`, `as_of_date`, and `strict_as_of`.
- Sanitized company metadata.
- Financial facts filtered by publication date when strict-as-of is enabled.
- Local price series up to the report date.
- Stage 4 analysis output and Stage 5 peer/valuation output.
- Official filings and local document snippets.
- Evidence IDs with fact IDs, price IDs, filing IDs, document IDs, source URLs, period dates, units, and currencies where available.
- Prompt-injection warnings and known limitations.
- A deterministic `bundle_hash` that excludes volatile timestamps and local filesystem paths.

## Report Templates

The API accepts `report_style`:

- `institutional_full`
- `concise_committee_brief`
- `evidence_appendix_heavy`

The current implementation uses the same validated section schema for each style and can select subsets through the `sections` request field.

## AI Boundary

AI narration is optional and off by default. When enabled, the orchestration service sends only a bounded prompt containing the bundle hash, allowed evidence IDs, company metadata, and limitations.

The LLM may not create facts, metrics, citations, valuation inputs, or conclusions. If the local provider is disabled, unavailable, blocked by prompt-injection risk, or rejected by validation, the deterministic fallback is returned.

## Validation

`ReportClaimValidator` checks:

- Section evidence IDs exist in the bundle.
- Completed sections cite evidence except disclaimers.
- Forbidden advice wording is rejected.
- Local path leakage is rejected.
- Prompt-injection risk is surfaced as a warning.
- Missing official evidence is surfaced as a warning.

Unsupported claims cause the report to be rejected instead of persisted as a valid report.

## Prompt Injection Guard

Retrieved document text is treated as untrusted input. The guard scans titles and snippets for instruction-like text such as attempts to override prior instructions, reveal system prompts, bypass rules, fabricate content, or force trading-style outputs. Flagged bundles use deterministic fallback and carry validation warnings.

## Why This Is Not Investment Advice

The report is designed for public-information verification and audit trails. It does not connect to brokers, place orders, predict prices, promise returns, or provide personalized trading instructions. Valuation outputs remain scenario and evidence summaries only.

## No Single-Point Price Instruction

Stage 6 deliberately excludes single-point valuation instructions and trading ratings. The report can summarize Stage 5 scenario outputs, assumptions, sensitivities, evidence, and limitations, but it does not convert them into an action.

## LLM Unavailable Mode

If `LLM_ENABLED=false`, Ollama is not running, the model is missing, or the response fails validation, report generation still works through deterministic Python sections and exports.

## Stage 7 Handoff

Stage 7 may consume persisted reports, evidence coverage, validation status, warnings, and limitations. Stage 6 does not add portfolio management, risk budgets, alerts, event calendars, broker login, or automatic trading.
