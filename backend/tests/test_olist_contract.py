import json
from pathlib import Path

from backend.app.semantic import SemanticCatalog
from backend.app.safety import SQLSafetyGate, UnsafeSQL
from backend.app.wren import LocalCertifiedMetricAdapter, SemanticPlan


ROOT = Path(__file__).resolve().parents[2]


def test_olist_catalog_generates_safe_qualified_mart_sql(monkeypatch):
    monkeypatch.setenv("CHATBI_DATA_PROFILE", "olist")
    catalog = SemanticCatalog()
    query = LocalCertifiedMetricAdapter(catalog).plan_sql(
        "最近90天各品类Olist商品成交额",
        SemanticPlan("olist_gmv", ["category"], "last_90_days", {}),
        "postgres",
        [],
    )
    validated = SQLSafetyGate().validate(query, "postgres")
    assert "chatbi_mart" in validated
    assert "fct_order_item" in validated


def test_olist_migration_and_loader_are_source_shaped():
    migration = (ROOT / "data" / "postgres" / "003_olist_warehouse.sql").read_text(encoding="utf-8")
    loader = (ROOT / "backend" / "scripts" / "load_olist.py").read_text(encoding="utf-8")
    assert "CREATE SCHEMA IF NOT EXISTS chatbi_raw" in migration
    assert "fct_inventory_snapshot" in migration
    assert "olist_marketing_qualified_leads_dataset.csv" in loader
    assert "password" not in loader.lower()


def test_olist_metrics_have_catalog_shape():
    metrics = json.loads((ROOT / "data" / "metrics_olist.json").read_text(encoding="utf-8"))
    assert {item["name"] for item in metrics} >= {"olist_gmv", "olist_marketing_conversion_rate"}
    assert all(item["base_table"].startswith("chatbi_mart.") for item in metrics)


def test_safety_rejects_non_chatbi_schema_even_for_known_table():
    try:
        SQLSafetyGate().validate("SELECT * FROM private.fct_order LIMIT 1", "postgres")
    except UnsafeSQL as error:
        assert "Schema not allow-listed" in str(error)
    else:
        raise AssertionError("private schema must not pass the safety gate")


def test_olist_catalog_supports_historical_month_queries():
    catalog = SemanticCatalog(ROOT / "data" / "metrics_olist.json")
    query = LocalCertifiedMetricAdapter(catalog).plan_sql(
        "2017年11月Olist商品成交额",
        SemanticPlan("olist_gmv", [], "month_2017_11", {}),
        "postgres",
        [],
    )
    assert "DATE '2017-11-01'" in query
    assert "DATE '2017-12-01'" in query
