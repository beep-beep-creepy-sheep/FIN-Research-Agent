# Evidence Map

Every material finding carries evidence references when the underlying metric exposes lineage.

## Supported Evidence

- `source_fact_ids` from structured financial facts.
- `source_price_ids` from price observations.
- `filing_ids` from official filing metadata when available.
- `document_ids` and page numbers when document chunks are wired into a finding.
- `source_urls` from issuer or official sources, excluding local absolute filesystem paths.

## Markdown Markers

Markdown reports keep compact evidence markers such as:

```text
[evidence:facts=1,2;prices=9]
```

If evidence is missing, the report uses:

```text
[evidence:missing]
```

Missing evidence is a limitation, not a reason to fabricate citations.
