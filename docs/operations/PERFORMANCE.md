# Performance

Stage 8 keeps performance local and simple.

- Screener query limit: 1 to 200 rows.
- Screener export limit: 1 to 200 rows.
- Document search limit: 1 to 100 rows.
- Document chunk response limit: 1 to 500 chunks.
- Portfolio holdings/watch items/alert events limit: 1 to 500 rows.
- Calendar event limit: 1 to 500 rows.
- Report generation remains deterministic and bounded by local facts, filings, documents, and configured source limits.

No Redis, Celery, Kafka, Elasticsearch, streaming infrastructure, or silent stale fact cache is introduced.

