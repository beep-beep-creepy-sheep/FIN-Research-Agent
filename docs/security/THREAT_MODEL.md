# Threat Model

## Main Risks

- Secret leakage through logs, status endpoints, frontend env vars, or committed files.
- Local path leakage through exceptions and report validation.
- Path traversal in uploaded/downloaded artifacts.
- SSRF through official artifact download URLs and redirects.
- Prompt injection from imported filings/documents.
- Unsafe report Markdown/HTML rendering.
- Large unbounded API queries causing local resource exhaustion.
- Dependency vulnerabilities.

## Controls

- Structured error contract with request IDs and path redaction.
- Typed settings validation and redacted config summaries.
- Download URL validation with HTTPS/domain/DNS/private-IP guards.
- Safe artifact path segments and content-size limits.
- Report claim validation and forbidden wording checks.
- Pagination limits on large result APIs.
- `make secret-scan`, `make python-audit`, and `npm audit --audit-level=high`.

