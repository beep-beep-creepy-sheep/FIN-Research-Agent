# Peer Selection

Peer selection uses local company metadata and structured facts only.

Signals:

- Industry and broad sector.
- Exchange and inferred listing board.
- Manual peer overrides marked with `source=manual`.
- Exclude symbols and min/max peer count.

Rules:

- Unknown industry returns `insufficient_peer_data`.
- Banks are not mixed with manufacturing or consumer companies.
- No fake companies are added to fill peer counts.
- Candidate reasons, similarity scores, source, limitations, and missing lineage are returned.
- Peer sets are versioned and persisted by hash.

Known limits:

- Sector is inferred from available industry text until richer issuer classification exists.
- Market cap and revenue scale are included when local structured facts support them.
