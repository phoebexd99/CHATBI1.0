import csv

import pytest

from backend.scripts.split_evaluations import read_intake, split_questions


def _write_csv(path, rows):
    fields = ["source_id", "question", "intent", "metric", "dimensions", "time_range", "expected", "source_role", "source_date", "notes", "review_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_question_intake_rejects_unapproved_rows(tmp_path):
    path = tmp_path / "intake.csv"
    rows = [{"source_id": "Q-1", "question": "GMV?", "intent": "metric_query", "metric": "gmv", "dimensions": "", "time_range": "all_time", "expected": "scalar", "source_role": "运营", "source_date": "2026-08-29", "notes": "", "review_status": "draft"}]
    _write_csv(path, rows)
    with pytest.raises(ValueError, match="not approved"):
        read_intake(path)


def test_split_is_deterministic_and_stratified(tmp_path):
    path = tmp_path / "intake.csv"
    rows = [{"source_id": f"Q-{i:02d}", "question": f"问题{i}", "intent": "metric_query", "metric": "gmv" if i < 5 else "order_count", "dimensions": "", "time_range": "all_time", "expected": "scalar", "source_role": "运营", "source_date": "2026-08-29", "notes": "", "review_status": "approved"} for i in range(10)]
    _write_csv(path, rows)
    approved = read_intake(path)
    golden_a, holdout_a = split_questions(approved)
    golden_b, holdout_b = split_questions(approved)
    assert [row["source_id"] for row in holdout_a] == [row["source_id"] for row in holdout_b]
    assert len(golden_a) + len(holdout_a) == 10
    assert holdout_a and golden_a
