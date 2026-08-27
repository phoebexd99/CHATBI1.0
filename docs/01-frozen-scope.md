# Frozen Scope — 4-day Portfolio Sprint

## Product promise

An operations user asks a business question in Chinese and receives a certified metric answer, executable SQL, a chart, an evidence trail, and a visible workflow trace without writing SQL.

## In scope

Three pages only: intelligent query, knowledge center, and evaluation center. The business domain is synthetic commerce. The semantic foundation is WrenAI Core/SDK behind an adapter; CHATBI owns context retrieval, orchestration, SQL safety, evaluation, and UI. Local live mode and GitHub Pages replay mode share the same presentation components.

## Out of scope

Multi-tenancy, SSO, arbitrary connectors, multi-database federation, full permission administration, knowledge publishing workflow, dashboard editing, and enterprise-grade RLS/CLS. They remain roadmap topics, not hidden MVP commitments.

## Four-day milestones

| Day | Exit criterion |
|---|---|
| 1 | One real question traverses UI → API → workflow → retrieval/semantic adapter → safety → DB and is covered by tests. |
| 2 | Broaden question coverage, knowledge UI, ambiguity handling, and trace UX. |
| 3 | Run 30-question evaluation, improve failures, complete evaluation center and replay fixtures. |
| 4 | Polish, screenshots/recording, GitHub Pages workflow, production roadmap and portfolio narrative. |

## Definition of done

The live demo is reproducible locally; static replay is independently viewable; secrets are environment-only; evaluation artifacts are committed; architecture, safety boundaries, limitations, and production path are explicit.

