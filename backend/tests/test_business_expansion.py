from datetime import date

from backend.app.db import Database, seed_sqlite
from backend.app.retrieval import HybridRetriever
from backend.app.safety import SQLSafetyGate
from backend.app.workflow import QueryWorkflow
from backend.app.wren import LocalCertifiedMetricAdapter, SemanticPlan


def make_workflow(tmp_path) -> tuple[Database, QueryWorkflow]:
    database = Database(f"sqlite:///{tmp_path / 'business-expansion.db'}")
    seed_sqlite(database, today=date.today())
    return database, QueryWorkflow(database, HybridRetriever(), LocalCertifiedMetricAdapter(), SQLSafetyGate())


def test_catalog_driven_campaign_metrics_and_arbitrary_days(tmp_path):
    _, workflow = make_workflow(tmp_path)

    result = workflow.run("最近 45 天各活动 ROAS 排名")

    assert result["entities"]["metric"] == "roas"
    assert result["entities"]["dimensions"] == ["campaign"]
    assert result["entities"]["time_range"] == "last_45_days"
    assert result["columns"] == ["campaign", "roas"]
    assert len(result["rows"]) == 4
    assert "campaign_daily" in result["sql"]


def test_filter_values_are_discovered_from_database_not_python_rules(tmp_path):
    database, workflow = make_workflow(tmp_path)
    with database.connect() as connection:
        connection.execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (9999, 1, date.today().isoformat(), "paid", "视频号", "东北", 880, 0, 0),
        )
        connection.commit()

    result = workflow.run("最近 30 天东北地区 GMV")

    assert result["entities"]["filters"] == {"region": "东北"}
    assert result["rows"][0][0] == 880
    assert "东北" in result["sql"]


def test_inventory_domain_supports_category_analysis(tmp_path):
    _, workflow = make_workflow(tmp_path)

    result = workflow.run("今天各品类可用库存")

    assert result["entities"]["metric"] == "available_inventory"
    assert result["entities"]["dimensions"] == ["category"]
    assert result["chart_spec"]["type"] == "bar"
    assert len(result["rows"]) == 4
    assert "inventory_snapshots" in result["sql"]


def test_marketing_metric_knowledge_answer_skips_sql(tmp_path):
    _, workflow = make_workflow(tmp_path)

    result = workflow.run("ROAS 的定义是什么？")

    assert result["intent"] == "knowledge_query"
    assert result["entities"]["knowledge_target"] == "metric.roas"
    assert result["sql"] == ""
    assert "归因收入" in result["answer"]


def test_postgres_campaign_sql_stays_inside_safety_boundary():
    adapter = LocalCertifiedMetricAdapter()
    sql = adapter.plan_sql(
        "最近 90 天各活动 ROAS 排名",
        SemanticPlan("roas", ["campaign"], "last_90_days", {}),
        "postgres",
        [],
    )

    validated = SQLSafetyGate().validate(sql, "postgres")

    assert "campaign_daily" in validated
    assert "INTERVAL '89 DAYS'" in validated
    assert "LIMIT 100" in validated
