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
