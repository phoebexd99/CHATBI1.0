"""Validate and deterministically split reviewed business questions.

The input is a CSV exported from the intake template. It must contain a real
source_role and review_status=approved; example rows are rejected. Holdout is
selected at 20% within each expected/metric stratum using a stable hash, which
prevents accidental dependence on file order while keeping coverage balanced.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path


REQUIRED = {"source_id", "question", "intent", "expected", "source_role", "review_status"}


def read_intake(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or not rows[0]:
        raise ValueError("intake CSV is empty")
    missing = REQUIRED - set(rows[0])
    if missing:
        raise ValueError(f"missing intake columns: {', '.join(sorted(missing))}")
    seen_ids: set[str] = set()
    seen_questions: set[str] = set()
    approved: list[dict[str, str]] = []
    for row in rows:
        source_id = (row.get("source_id") or "").strip()
        question = (row.get("question") or "").strip()
        status = (row.get("review_status") or "").strip().lower()
        if status == "example":
            continue
        if status != "approved":
            raise ValueError(f"question {source_id or '<unknown>'} is not approved")
        if not source_id or not question or not (row.get("source_role") or "").strip():
            raise ValueError(f"question {source_id or '<unknown>'} is missing source_id, question, or source_role")
        if source_id in seen_ids or question in seen_questions:
            raise ValueError(f"duplicate source_id or question: {source_id}")
        seen_ids.add(source_id)
        seen_questions.add(question)
        approved.append(row)
    if len(approved) < 10:
        raise ValueError("at least 10 approved questions are required for a meaningful split")
    return approved


def split_questions(rows: list[dict[str, str]], holdout_ratio: float = 0.2) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    if not 0 < holdout_ratio < 1:
        raise ValueError("holdout_ratio must be between 0 and 1")
    strata: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        strata[f"{row.get('expected','')}|{row.get('metric','')}"] .append(row)
    golden: list[dict[str, str]] = []
    holdout: list[dict[str, str]] = []
    for group in strata.values():
        ordered = sorted(group, key=lambda row: hashlib.sha256(f"{row['source_id']}|{row['question']}".encode()).hexdigest())
        holdout_count = max(1, round(len(ordered) * holdout_ratio)) if len(ordered) > 1 else 0
        holdout.extend(ordered[:holdout_count])
        golden.extend(ordered[holdout_count:])
    return sorted(golden, key=lambda row: row["source_id"]), sorted(holdout, key=lambda row: row["source_id"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--golden-output", type=Path, required=True)
    parser.add_argument("--holdout-output", type=Path, required=True)
    args = parser.parse_args()
    rows = read_intake(args.input.resolve())
    golden, holdout = split_questions(rows)
    args.golden_output.write_text(json.dumps(golden, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.holdout_output.write_text(json.dumps(holdout, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"approved": len(rows), "golden": len(golden), "holdout": len(holdout)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
