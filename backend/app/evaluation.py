from __future__ import annotations

from collections import Counter
from statistics import median
from time import perf_counter
from typing import Any

from .workflow import QueryWorkflow, WorkflowFailure


CLARIFICATION_CATEGORIES = {"ambiguous_question"}
REJECTION_CATEGORIES = {"unsafe_request", "off_domain", "unsafe_sql"}


def _percent(value: int, total: int) -> float:
    return round(value / total * 100, 2) if total else 0.0


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int(len(ordered) * 0.95) - 1))]


def _behavior_matches(case: dict[str, Any], result: dict[str, Any]) -> bool:
    expected = case["expected"]
    columns = result.get("columns", [])
    rows = result.get("rows", [])
    if expected == "scalar_positive":
        return len(columns) == 1 and bool(rows) and isinstance(rows[0][0], (int, float)) and rows[0][0] > 0
    if expected == "scalar":
        return len(columns) == 1 and len(rows) == 1
    if expected == "table_nonempty":
        return len(columns) >= 2 and bool(rows)
    if expected == "time_series":
        return result.get("chart_spec", {}).get("type") == "line" and len(rows) >= 2
    if expected == "comparison":
        return len(rows) == 2 and result.get("insight", {}).get("title") == "环比洞察"
    if expected == "definition":
        return result.get("intent") == "knowledge_query" and bool(result.get("answer")) and not result.get("sql")
    return False


def evaluate_case(workflow: QueryWorkflow, case: dict[str, Any]) -> dict[str, Any]:
    started = perf_counter()
    try:
        result = workflow.run(case["question"])
    except WorkflowFailure as error:
        latency_ms = round((perf_counter() - started) * 1000, 2)
        expected = case["expected"]
        category_ok = (
            expected == "clarification" and error.category in CLARIFICATION_CATEGORIES
        ) or (
            expected == "rejected" and error.category in REJECTION_CATEGORIES
        )
        return {
            "id": case["id"], "question": case["question"], "passed": category_ok,
            "expected": expected, "actual": "error", "category": error.category,
            "latency_ms": latency_ms, "trace_nodes": len(error.trace),
            "checks": {"expected_failure_category": category_ok},
        }

    latency_ms = round((perf_counter() - started) * 1000, 2)
    entities = result.get("entities", {})
    evidence_ids = [item["id"] for item in result.get("evidence", [])]
    relevant_ids = case.get("knowledge_ids", [])
    retrieval_hit = not relevant_ids or any(item in evidence_ids for item in relevant_ids)
    relevant_ranks = [evidence_ids.index(item) + 1 for item in relevant_ids if item in evidence_ids]
    reciprocal_rank = round(1 / min(relevant_ranks), 4) if relevant_ranks else 0.0
    checks = {
        "intent": result.get("intent") == case.get("intent"),
        "metric": not case.get("metric") or entities.get("metric") == case["metric"],
        "dimensions": not case.get("dimensions") or set(entities.get("dimensions", [])) == set(case["dimensions"]),
        "time_range": not case.get("time_range") or case.get("time_range") == "ambiguous" or entities.get("time_range") == case["time_range"],
        "filters": not case.get("filters") or entities.get("filters") == case["filters"],
        "retrieval_hit_at_5": retrieval_hit,
        "expected_behavior": _behavior_matches(case, result),
    }
    passed = all(checks.values())
    return {
        "id": case["id"], "question": case["question"], "passed": passed,
        "expected": case["expected"], "actual": "success",
        "intent": result.get("intent"), "latency_ms": latency_ms,
        "trace_nodes": len(result.get("trace", [])), "repair_count": result.get("repair_count", 0),
        "retrieval_rank": min(relevant_ranks) if relevant_ranks else None,
        "reciprocal_rank": reciprocal_rank, "evidence_ids": evidence_ids,
        "checks": checks,
    }


def run_evaluation(workflow: QueryWorkflow, cases: list[dict[str, Any]]) -> dict[str, Any]:
    results = [evaluate_case(workflow, case) for case in cases]
    total = len(results)
    passed = sum(item["passed"] for item in results)
    expected_clarifications = [item for item in results if item["expected"] == "clarification"]
    expected_rejections = [item for item in results if item["expected"] == "rejected"]
    clarified = [item for item in results if item.get("category") in CLARIFICATION_CATEGORIES]
    correctly_rejected = [item for item in expected_rejections if item["passed"]]
    retrieval_cases = [item for item in results if "retrieval_hit_at_5" in item["checks"]]
    latencies = [item["latency_ms"] for item in results]
    failure_distribution = Counter(item.get("category", "incorrect_result") for item in results if not item["passed"])
    return {
        "summary": {
            "total": total, "passed": passed, "failed": total - passed,
            "accuracy": _percent(passed, total),
            "clarification_rate": _percent(len(clarified), total),
            "clarification_success_rate": _percent(sum(item["passed"] for item in expected_clarifications), len(expected_clarifications)),
            "safety_rejection_rate": _percent(len(correctly_rejected), len(expected_rejections)),
            "retrieval_hit_at_5": _percent(sum(item["checks"]["retrieval_hit_at_5"] for item in retrieval_cases), len(retrieval_cases)),
            "mrr": round(sum(item["reciprocal_rank"] for item in retrieval_cases) / len(retrieval_cases), 4) if retrieval_cases else 0.0,
            "latency_p50_ms": round(median(latencies), 2) if latencies else 0.0,
            "latency_p95_ms": round(_p95(latencies), 2),
            "failure_distribution": dict(sorted(failure_distribution.items())),
        },
        "cases": results,
    }
