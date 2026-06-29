# Security Model

FIN Research Agent is a local-first research tool. It stores public-source research data and user-managed local research records. It is not a broker, account aggregator, or trading system.

## Defaults

- LLM off by default.
- Live official-source smoke off by default.
- External internet connectors off by default.
- CORS restricted to configured local frontend origins.
- Secrets redacted from config summaries and logs.
- Retrieved web/document content is treated as untrusted evidence.

## Guardrails

- No broker login, order placement, automatic trading, or automatic rebalancing.
- No target price, buy/sell/hold conclusion, promised return, or personal investment advice.
- AI cannot create facts, citations, or bypass report validation.
- Official artifact downloads keep HTTPS, domain allowlist, DNS private-IP, redirect, timeout, size, content-type/header, and PDF magic checks.
- Report HTML output escapes user/document content.

