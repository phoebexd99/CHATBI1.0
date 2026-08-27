from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import platform
import subprocess

from backend.app.db import Database, seed_sqlite
from backend.app.evaluation import run_evaluation
from backend.app.retrieval import HybridRetriever, ROOT
from backend.app.safety import SQLSafetyGate
from backend.app.workflow import QueryWorkflow
from backend.app.wren import LocalCertifiedMetricAdapter


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CHATBI 30-question Golden evaluation.")
    parser.add_argument("--output", type=Path, default=ROOT / "evals" / "results" / f"day3-full-{datetime.now().date().isoformat()}.json")
    parser.add_argument("--database", type=Path, default=ROOT / "evals" / ".day3-evaluation.db")
    parser.add_argument("--replay-output", type=Path, default=None, help="Optional GitHub Pages replay fixture path.")
    args = parser.parse_args()

    args.database.unlink(missing_ok=True)
    database = Database(f"sqlite:///{args.database}")
    seed_sqlite(database)
    workflow = QueryWorkflow(database, HybridRetriever(), LocalCertifiedMetricAdapter(), SQLSafetyGate())
    cases = json.loads((ROOT / "evals" / "golden_questions.json").read_text(encoding="utf-8"))
    evaluation = run_evaluation(workflow, cases)
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        commit = "unknown"
    artifact = {
        "run_id": f"day3-full-{datetime.now().astimezone().isoformat(timespec='seconds')}",
        "scope": "30-question Golden evaluation",
        "commit": commit,
        "environment": {
            "python": platform.python_version(), "database": "SQLite deterministic fixture",
            "semantic_adapter": "local_certified_metric", "retrieval": "keyword_plus_feature_hash",
        },
        **evaluation,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.replay_output:
        args.replay_output.parent.mkdir(parents=True, exist_ok=True)
        replay = {"total": len(cases), "questions": cases, "latest_result": artifact}
        args.replay_output.write_text(json.dumps(replay, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact["summary"], ensure_ascii=False, indent=2))
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
