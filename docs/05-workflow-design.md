# Workflow Design

The state machine is intentionally explicit:

1. classify intent
2. extract entities and time range
3. detect ambiguity
4. retrieve context
5. build semantic plan
6. generate SQL through the Wren adapter
7. validate with SQLGlot
8. Wren/database dry-run
9. repair at most once
10. execute read-only query
11. recommend chart
12. produce insight and evidence

Every node appends duration, status, and a compact payload to the trace. A failure exits with a stable category. Day 1 uses an in-process graph runner with LangGraph-compatible state boundaries; the optional LangGraph package is used when available, while node contracts remain framework-independent for reliable tests.

