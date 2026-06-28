# Analysis Framework

Fin Research Agent analysis is deterministic Python output built from local facts, metrics,
prices, filings, documents, citations, and data-quality issues.

## Core Objects

- `AnalysisContext`: company identity, industry, exchange, currency, as-of date, financial
  periods, metric observations, price analytics, filings, citations, data quality, source
  lineage, `strict_as_of`, and `analysis_version`.
- `AnalysisFinding`: category, title, severity, direction, summary, metric codes, values,
  periods, source fact IDs, price IDs, filing IDs, document IDs, citation IDs, evidence,
  assumptions, limitations, confidence, and `generated_by=deterministic_python`.
- `AnalysisSection`: grouped findings, qualitative state, supporting metrics, missing-data
  warnings, and limitations.
- `AnalysisReport`: executive summary, key findings, sections, industry output, market risk,
  data quality, evidence map, limitations, generated timestamp, and version.

## As-Of Rules

When `strict_as_of=true`, financial facts with publication dates after the selected date are
excluded before metrics or findings are produced. Missing publication dates are also excluded
under strict mode.

## AI Boundary

AI may explain an already-built deterministic report in future endpoints, but it must not create
financial facts, calculate metrics, invent citations, or add findings that do not reference
deterministic finding IDs.
