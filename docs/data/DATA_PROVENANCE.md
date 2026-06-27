# Data Provenance

Filing records retain source ID, source document ID, canonical URL, download URL, source tier, verification status, SHA-256, publication date, report period, and archive paths.

Documents link to filings. Chunks link to documents and filings and retain page number, parser version, source URL, and content hash.

Financial facts may link to filings through `filing_id`; unofficial sources are blocked from directly writing formal facts.
