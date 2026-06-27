# Stage 3: Official Source Coverage

Updated: 2026-06-26

## Goal

Build the official data, filing, document-provenance, and source-coverage layer for an evidence-first financial research terminal. Stage 3 creates traceable filing metadata, raw artifact archiving, page-aware document ingestion, data-quality issues, background jobs, and benchmark selection.

## Non-goals

- No DCF, full industry analysis, portfolio management, broker login, trading, social sentiment score, AI price prediction, or OCR system.
- No AI-generated financial facts.
- No fabricated filings, facts, chart points, citations, or benchmark prices.

## Current Ability

- Fixture-verified official source registry for CNINFO, SSE, SZSE, BSE, and optional SEC EDGAR definition.
- Filing metadata upsert with source tier, verification status, hash, archive path, and parse status.
- Secure artifact archive service with URL allowlist, private IP blocking, size limit, SHA-256, temp files, and atomic move.
- Page-aware parsing for PDF/text-like artifacts with deterministic chunks and parser version.
- Data-quality issue repository and API.
- Company benchmark auto-selection from exchange and board.

## Data Source Coverage Matrix

| Source | Tier | Markets | Exchanges | Listing | Download | Parse | Live smoke |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CNINFO | official | CN-A | SSE/SZSE/BSE | fixture verified | fixture verified | fixture verified | NOT_RUN |
| SSE | exchange | CN-A | SSE | fixture verified | fixture verified | fixture verified | NOT_RUN |
| SZSE | exchange | CN-A | SZSE | fixture verified | fixture verified | fixture verified | NOT_RUN |
| BSE | exchange | CN-A | BSE | fixture verified | fixture verified | fixture verified | NOT_RUN |
| SEC EDGAR | regulator | US | NYSE/NASDAQ/AMEX | defined | defined | defined | NOT_RUN |

## Standard Data Contract

Adapters return typed `SourceCompanyIdentity`, `FilingCandidate`, `FilingMetadata`, `DownloadedArtifact`, `FilingSyncResult`, and `ParseResult` objects. Adapters do not write the database directly; repositories perform idempotent persistence.

## Filing Lifecycle

`listed -> normalized -> saved -> download pending -> downloaded -> parsing -> parsed | parsed_with_warnings | ocr_required | failed`

## Download Lifecycle

The service validates URL scheme, HTTPS, allowlisted domain, DNS-resolved IP safety, size limits, PDF magic, then writes metadata and content by temp file plus atomic rename. Existing hashes are reused.

## Parse Lifecycle

Parsing is deterministic and page-aware. PDF uses `pypdf` when installed, with fallback text behavior for minimal fixtures. OCR is marked as required but not performed.

## Source Trust Tiers

`official`, `regulator`, `exchange`, and `issuer` are verification sources. `aggregator` may provide candidate facts. `media`, `community`, Agent Reach, Exa, RSS, direct web, and social sources cannot directly write `financial_facts`.

## Deduplication Strategy

Filing uniqueness is source ID plus source document ID or canonical URL. Artifacts are content-addressed by SHA-256 across sources.

## Conflict Handling

Conflicts and missing metadata are recorded as `data_quality_issues`. Severe conflicts are not auto-closed by AI.

## Data Retention

Raw metadata is retained under `data/raw/{source_id}/{symbol}/{year}/{source_document_id}/metadata.json`. Raw documents are retained under `data/documents/{source_id}/{symbol}/{year}/{sha256}.pdf`.

## Network Security

Official downloads require HTTP(S), official adapters prefer HTTPS, per-source domain allowlists, DNS IP checks, private/loopback/link-local/cloud-metadata blocking, redirect revalidation hooks, size limits, and no sensitive header logging.

## API Design

Stage 3 exposes source registry, source health, company filings sync/list, filing detail/retry, document detail/chunks, data-quality summary/issues, and company benchmark selection.

## UI Design

The company page includes filings, source tier, download status, parse status, verification status, sync/retry entry points, benchmark selection, and data-quality cards with empty and failure states.

## Test Plan

Tests use local fixtures or mocked services only. Coverage includes source adapter contracts, idempotent filing upsert, secure download checks, page-aware parsing, data-quality idempotence, benchmark selection, API empty/job states, and frontend render states.

## Acceptance Criteria

- Official source protocol and registry exist.
- CNINFO, SSE, SZSE, and BSE fixture contracts pass.
- At least one fixture A-share source completes list to frontend evidence flow.
- Filing, Document, Chunk, FinancialFact, and Citation lineage fields remain connected.
- No unofficial source writes formal financial facts.
- Background jobs create retryable records and avoid duplicate filings/chunks.

## Known External Limits

Live source smoke is intentionally disabled by default. Network blocks, anti-bot responses, and rate limits must be reported as blocked, not test pass.
