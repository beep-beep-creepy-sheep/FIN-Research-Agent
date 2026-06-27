# Source Registry

Stage 3 registers CNINFO, SSE, SZSE, BSE, and optional SEC EDGAR through `OfficialSourceRegistry`.

Each source declares source ID, display name, tier, supported markets/exchanges, allowlisted domains, and rate-limit policy. Fixture contract status is separate from live smoke status.

Adapter selection has three layers:

- Source definition: metadata only.
- Fixture adapter: deterministic local/CI behavior, never live coverage.
- Live adapter: real official source access, enabled only by `OFFICIAL_SOURCE_MODE=live`.

CNINFO has a live listing adapter. SSE, SZSE, BSE, and SEC EDGAR remain fixture/defined only for live mode.
