# Production Readiness Plan

No cloud resource, firewall rule, credential, or production database is changed by this plan. Each stage has an explicit entry gate and rollback boundary.

## Stage 0 — Current portfolio baseline

- GitHub Pages hosts read-only Replay fixtures.
- Local Live mode uses FastAPI, real LangGraph SSE events, the RAG/Wren adapter boundary, SQLGlot safety, and SQLite or PostgreSQL.
- The 30-question deterministic Golden suite is the merge gate.

## Stage 1 — Deployable service boundary

- Package frontend and API as separately versioned images.
- Put FastAPI behind TLS and a reverse proxy that does not buffer SSE.
- Keep PostgreSQL private; expose no database port to the public internet.
- Store database, model, and Wren credentials in a managed secret store.
- Add health/readiness probes, migration jobs, request quotas, backups, and a documented rollback to the previous image/database migration.

Exit gate: staging smoke tests, SSE proxy test, restore drill, and zero secrets in image/repository.

## Stage 2 — Authentication, authorization, and RLS

- Validate OIDC access tokens at the API boundary and propagate a stable user/tenant context.
- Map business roles to metric, dimension, column, and row policies before SQL generation.
- Enforce PostgreSQL RLS with transaction-scoped identity variables; do not rely on prompt instructions for authorization.
- Record immutable audit events for question, policy decision, SQL fingerprint, row count, and evidence IDs without logging sensitive row values.

Exit gate: cross-tenant isolation tests, privilege-escalation tests, policy-denial UX, and audited break-glass access.

## Stage 3 — pgvector knowledge service

- Replace deterministic feature hashing with versioned embedding models and pgvector indexes.
- Build idempotent ingestion for Schema, certified metrics, terms, and verified NL–SQL documents.
- Add document ownership, status, release version, validity window, and rollback metadata.
- Tune hybrid lexical/vector ranking against the Golden set and a separate holdout set.

Exit gate: retrieval quality does not regress, stale releases can be rolled back, and all answer evidence resolves to a published version.

## Stage 4 — Production Wren integration

- Deploy Wren Core behind a private service endpoint and keep the existing adapter contract.
- Version semantic models independently from application releases.
- Add strict timeouts, bounded retries, circuit breaking, and explicit fallback behavior.
- Run generated SQL through the existing CHATBI safety and dry-run gates regardless of Wren provenance.

Exit gate: contract tests for supported metrics/dialects, failure injection, and semantic-model rollback.

## Stage 5 — Observability and operations

- Emit one trace ID across FastAPI, LangGraph nodes, retrieval, Wren, safety, and database execution.
- Export OpenTelemetry traces plus latency, error-category, retrieval, repair, row-count, and token/cost metrics.
- Define SLOs and alerts for availability, p95 latency, unsafe-SQL attempts, retrieval misses, and evaluation regressions.
- Keep prompts, SQL values, and retrieved content redacted by default; sample only approved metadata.

Exit gate: dashboards, alerts, on-call runbooks, load tests, and a staging incident drill.

## Recommended order

Deploy a private staging environment first, then add identity/RLS, then pgvector, then production Wren, and finally broaden traffic under observability. Public Live access should wait until Stages 1–2 pass; GitHub Pages Replay can remain public throughout because it contains only checked-in synthetic fixtures.
