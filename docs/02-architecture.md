# Architecture

## Current Day 1 architecture

```text
Next.js (live/replay)
  └─ POST /api/query
      └─ FastAPI
          └─ QueryGraph
              ├─ classify + entities + ambiguity
              ├─ HybridRetriever (keyword + deterministic vector)
              ├─ WrenAdapter interface
              │   ├─ HTTP Wren adapter when configured
              │   └─ LocalCertifiedMetricAdapter fallback
              ├─ SQLGlot safety gate
              ├─ dry-run / at most one repair
              ├─ read-only DB execution
              └─ chart + insight + evidence + trace
```

PostgreSQL + pgvector is the Compose target. SQLite is a development fallback solely to make local verification possible where Docker is unavailable. Knowledge is file-backed on Day 1, with the same document shape intended for pgvector ingestion.

## Target production architecture

The target separates API, orchestration workers, context service, Wren Core, PostgreSQL/pgvector, model gateway, observability, and evaluation jobs. It adds identity, policy enforcement, query quotas, RLS/CLS, audited knowledge releases, encrypted secret management, queue-backed execution, caching, and trace/metric export.

## Request contract

Every successful response includes `answer`, `sql`, `columns`, `rows`, `chart`, `evidence`, and ordered `trace`. Failures use stable categories such as `ambiguous_question`, `retrieval_miss`, `unsafe_sql`, `dry_run_error`, and `execution_error`.

