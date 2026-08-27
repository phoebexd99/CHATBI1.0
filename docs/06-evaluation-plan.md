# Evaluation Plan

`evals/golden_questions.json` begins with 30 questions covering aggregate metrics, segmentation, trends, comparisons, terminology, ambiguity, and unsafe/off-domain requests. Each row records expected intent, metric, dimensions, time range, answer/query expectations, and relevant knowledge IDs.

Metrics:

- retrieval hit@k and MRR
- SQL parse/safety pass rate
- SQL executable rate
- execution accuracy against expected scalar/table results
- end-to-end answer correctness
- p50/p95 latency
- failure distribution by stable category

Results must be reproducible, timestamped, tied to a commit and configuration fingerprint, and retained under `evals/results/`. Day 1 tests the vertical slice; Day 3 runs and analyzes the full set rather than claiming unmeasured coverage.

## Day 3 measured baseline

Run the complete suite with:

```bash
python -m backend.scripts.run_evaluations --output evals/results/day3-full-2026-08-28.json --replay-output frontend/public/replay/evaluation-summary.json
```

The checked-in deterministic baseline passes 30/30 cases. It records 100% end-to-end accuracy, 10% clarification rate with 100% expected-clarification coverage, 100% safety rejection, 100% retrieval hit@5, and MRR 1.0. These values describe the synthetic SQLite/local-adapter fixture only; they are regression evidence, not a claim about production LLM generalization.

