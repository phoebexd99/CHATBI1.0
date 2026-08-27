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

