# Stage 4: Professional Financial Analysis

Updated: 2026-06-28

## Goal

Stage 4 adds a deterministic professional analysis layer on top of the Stage 2 metric engine
and Stage 3 source-provenance work. The output is structured research evidence, not
investment advice.

## Delivered Scope

- Analysis data contract: context, evidence references, findings, sections, scores, quality
  flags, risk flags, and reports.
- General company analysis sections for growth, profitability, cash-flow quality, balance
  sheet strength, efficiency, earnings quality, market risk, and data quality.
- Industry pack registry with `general`, `bank`, and `consumer_manufacturing` selection.
- Bank pack that avoids applying industrial metrics when a company is identified as a bank.
- Consumer/manufacturing pack with margin, demand, working-capital, cash-flow, and proxy
  analysis.
- Transparent research-quality scoring with component reasons and caveats.
- JSON and Markdown report rendering with evidence markers.
- Analysis API endpoints for reports, findings, quality, industry pack selection, and
  synchronous analysis runs.
- Company page Professional Analysis section with partial API failure handling.

## Non-Goals

- No full DCF model.
- No relative valuation lab.
- No target price.
- No trading signal.
- No portfolio management, broker login, automatic order placement, or AI price prediction.
- No paid data API dependency.

## Verification Notes

Stage 4 calculations use existing metric observations and deterministic Python rules. Missing
inputs return explicit `missing` or `insufficient` states. The system does not fabricate market
data, financial facts, chart points, citations, or filings to make a report look complete.

## Stage 5 Handoff

Stage 5 can build valuation or peer-comparison features on the deterministic report contract,
but must keep the same evidence lineage, strict as-of filtering, and no-advice boundary.
