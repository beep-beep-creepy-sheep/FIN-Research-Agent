# Dependency Audit

Stage 8 dependency policy:

- Do not add paid API SDKs.
- Do not add Redis, Celery, Kafka, Elasticsearch, Kubernetes, or large service dependencies.
- Do not force breaking upgrades solely to silence moderate advisories.

Commands:

```bash
make python-audit
cd frontend && npm audit --audit-level=high
```

Known state from Stage 7: Python audit passed. npm high-severity gate passed; moderate Next/PostCSS advisories remained and were documented because the available fix required a breaking forced upgrade.

