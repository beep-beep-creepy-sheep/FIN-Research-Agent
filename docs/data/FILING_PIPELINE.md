# Filing Pipeline

The pipeline is adapter-first and repository-safe:

`resolve company -> list filings -> normalize metadata -> idempotent filing upsert -> archive raw metadata -> download artifact -> hash -> parse pages -> replace chunks -> quality checks`

API POST endpoints return a job ID. Worker execution performs network and parsing work.

`download_filing` jobs now reconstruct filing metadata from the saved Filing row, select the configured fixture or live adapter by source ID, archive the artifact, and update download status. `retry_filing` chooses download retry when there is no local file or the prior download failed, and parse retry when parsing failed or needs reparse.
