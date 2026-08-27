from datetime import date

from backend.app.db import Database, seed_sqlite
from backend.app.retrieval import HybridRetriever
from backend.app.safety import SQLSafetyGate
from backend.app.workflow import QueryWorkflow
from backend.app.wren import LocalCertifiedMetricAdapter


def test_real_gmv_vertical_slice(tmp_path):
    database = Database(f"sqlite:///{tmp_path / 'test.db'}")
    seed_sqlite(database, today=date.today())
    workflow = QueryWorkflow(database, HybridRetriever(), LocalCertifiedMetricAdapter(), SQLSafetyGate())
    result = workflow.run("最近 30 天 GMV 是多少？")
    assert result["columns"] == ["gmv"]
    assert result["rows"][0][0] > 0
    assert result["dry_run_ok"] is True
    assert result["chart_spec"]["type"] == "metric"
    assert [item["node"] for item in result["trace"]] == [
        "classify", "extract_entities", "check_ambiguity", "retrieve", "semantic_plan",
        "generate_sql", "safety", "dry_run", "repair_once", "execute", "chart", "insight",
    ]


def test_day2_metric_coverage_and_explainability(tmp_path):
    database = Database(f"sqlite:///{tmp_path / 'day2.db'}")
    seed_sqlite(database, today=date.today())
    workflow = QueryWorkflow(database, HybridRetriever(), LocalCertifiedMetricAdapter(), SQLSafetyGate())

    result = workflow.run("按渠道看近 30 天 GMV")

    assert result["entities"]["metric"] == "gmv"
    assert result["entities"]["dimensions"] == ["channel"]
    assert result["rows"]
    assert result["retrieval_summary"]["certified_hits"] >= 1
    assert result["insight"]["highlights"]
    assert all("text" in item and "match_reason" in item for item in result["evidence"])


def test_day2_ambiguity_and_off_domain_boundaries(tmp_path):
    database = Database(f"sqlite:///{tmp_path / 'boundaries.db'}")
    seed_sqlite(database, today=date.today())
    workflow = QueryWorkflow(database, HybridRetriever(), LocalCertifiedMetricAdapter(), SQLSafetyGate())

    import pytest
    with pytest.raises(ValueError, match="ambiguous_question"):
        workflow.run("销售额是多少？")
    with pytest.raises(ValueError, match="off_domain"):
        workflow.run("告诉我明天的股票价格")
