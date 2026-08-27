# Architecture Decision Records

## ADR-001 — Build around Wren, do not fork a full BI application

**Status:** accepted. Use WrenAI Core/SDK as the deterministic semantic/SQL planning boundary. Own the portfolio-differentiating context, orchestration, safety, evaluation, and UX. An adapter isolates API/version changes and enables Day 1 progress when Wren is unavailable.

## ADR-002 — Hybrid retrieval with a replaceable embedding implementation

**Status:** accepted. Day 1 combines lexical overlap and deterministic feature-hash vectors, preserving component scores and ranks in the trace. The interface can move to pgvector plus a production embedding model without changing workflow state.

## ADR-003 — PostgreSQL target, SQLite verification fallback

**Status:** accepted. PostgreSQL/pgvector is authoritative for Docker and deployment. SQLite is deliberately limited to local development and CI smoke tests; dialect differences are owned by the semantic adapter.

## ADR-004 — One graph, deterministic baseline first

**Status:** accepted. The graph exposes all required nodes even when early implementations are deterministic. Model calls are optional and OpenAI-compatible. This produces measurable baselines before adding probabilistic behavior.

## ADR-005 — Static replay is a product mode

**Status:** accepted. GitHub Pages hosts no backend. Checked-in, sanitized response fixtures use the same UI components as live mode, making evidence inspectable without credentials or infrastructure.

