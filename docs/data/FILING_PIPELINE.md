# Filing Pipeline

The pipeline is adapter-first and repository-safe:

`resolve company -> list filings -> normalize metadata -> idempotent filing upsert -> archive raw metadata -> download artifact -> hash -> parse pages -> replace chunks -> quality checks`

API POST endpoints return a job ID. Worker execution performs network and parsing work.
