# Report Exports

Stage 6 reports are persisted as JSON and can be exported as Markdown or print-friendly HTML.

## JSON

Primary JSON is returned by:

- `GET /v1/companies/{symbol}/report`
- `POST /v1/companies/{symbol}/report`
- `GET /v1/report-runs/{run_id}`

The JSON payload includes report metadata, sections, validation, evidence coverage, warnings, limitations, LLM status, bundle hash, report hash, and report version. When requested, it also includes the evidence bundle.

## Markdown

Markdown export is available at:

```text
GET /v1/report-runs/{run_id}/markdown
```

Markdown includes the report heading, research-only disclaimer, as-of settings, validation status, evidence coverage, section content, and limitations. It is generated from the persisted validated report.

## Print-Friendly HTML

HTML export is available at:

```text
GET /v1/report-runs/{run_id}/html
```

The HTML is self-contained and intentionally simple for printing. It does not load external scripts or remote assets.

## Evidence And Validation Exports

Evidence and validation can be inspected separately:

```text
GET /v1/report-runs/{run_id}/evidence
GET /v1/report-runs/{run_id}/validation
```

These routes let users audit evidence IDs, source lineage, limitations, prompt-injection warnings, and unsupported-claim checks without parsing the full report.

## Frontend

The company page Institutional Report panel exposes:

- Report generation.
- Strict-as-of toggle.
- Deterministic/AI toggle.
- Language selector.
- Section selector.
- Validation status.
- Evidence coverage.
- Markdown export link.
- HTML print view link.
- Warning and limitation states.

## Known Limitations

- Export formatting is intentionally conservative and text-first.
- Regenerate-section is deterministic current-state unless an optional validated AI path is available.
- Live source coverage depends on data already persisted locally; live smoke remains opt-in.
