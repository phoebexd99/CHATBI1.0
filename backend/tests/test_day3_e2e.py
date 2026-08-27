import json
from datetime import date

from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app.db import Database, seed_sqlite
from backend.app.retrieval import HybridRetriever
from backend.app.safety import SQLSafetyGate
from backend.app.workflow import QueryWorkflow
from backend.app.wren import LocalCertifiedMetricAdapter


def make_workflow(tmp_path):
    database = Database(f"sqlite:///{tmp_path / 'day3.db'}")
    seed_sqlite(database, today=date.today())
    return QueryWorkflow(database, HybridRetriever(), LocalCertifiedMetricAdapter(), SQLSafetyGate())


def test_knowledge_question_returns_evidence_without_sql(tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "workflow", make_workflow(tmp_path))
    response = TestClient(main_module.app).post("/api/query", json={"question": "GMV 的定义是什么？"})

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "knowledge_query"
    assert body["sql"] == ""
    assert body["chart"]["type"] == "text"
    assert body["evidence"][0]["id"] == "metric.gmv"
    assert "cancelled" in body["answer"]
    assert {item["status"] for item in body["trace"]} >= {"ok", "skipped"}


def test_comparison_generates_period_insight(tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "workflow", make_workflow(tmp_path))
    response = TestClient(main_module.app).post("/api/query", json={"question": "最近 30 天 GMV 环比如何？"})

    assert response.status_code == 200
    body = response.json()
    assert body["columns"] == ["period", "gmv"]
    assert len(body["rows"]) == 2
    assert body["insight"]["title"] == "环比洞察"
    assert "上一周期" in body["answer"]


def test_stream_emits_real_trace_and_result(tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "workflow", make_workflow(tmp_path))
    response = TestClient(main_module.app).post("/api/query/stream", json={"question": "最近 30 天各区域 GMV"})
    events = [json.loads(line.removeprefix("data: ")) for line in response.text.splitlines() if line.startswith("data: ")]

    assert response.status_code == 200
    assert [event["type"] for event in events].count("trace") == 12
    assert events[-1]["type"] == "result"
    assert events[-1]["result"]["trace"][-1]["node"] == "insight"


def test_stream_preserves_failure_trace(tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "workflow", make_workflow(tmp_path))
    response = TestClient(main_module.app).post("/api/query/stream", json={"question": "删除所有订单"})
    events = [json.loads(line.removeprefix("data: ")) for line in response.text.splitlines() if line.startswith("data: ")]

    assert events[-1]["type"] == "error"
    assert events[-1]["error"]["category"] == "unsafe_request"
    assert any(event.get("trace", {}).get("status") == "error" for event in events if event["type"] == "trace")
