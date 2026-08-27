from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from .config import settings
from .db import Database
from .retrieval import HybridRetriever, ROOT
from .safety import SQLSafetyGate, UnsafeSQL
from .workflow import QueryState, QueryWorkflow, WorkflowFailure
from .wren import make_wren_adapter


class QueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)


database = Database(settings.database_url)
retriever = HybridRetriever()
workflow = QueryWorkflow(database, retriever, make_wren_adapter(settings), SQLSafetyGate())

app = FastAPI(title="CHATBI API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

ERROR_MESSAGES = {
    "ambiguous_question": "请补充明确的指标、时间范围或分析维度。",
    "unsafe_request": "该请求涉及数据修改或敏感信息导出，已被安全策略拒绝。",
    "off_domain": "该问题不属于当前经营分析数据域。",
    "unsafe_sql": "生成的 SQL 未通过安全校验。",
    "dry_run_error": "SQL 在数据库 dry-run 阶段失败。",
    "execution_error": "查询执行失败，请稍后重试。",
}


def _serialize_result(question: str, result: QueryState, started: float) -> dict:
    semantic_plan = result.get("semantic_plan")
    return {
        "question": question, "intent": result.get("intent"),
        "answer": result["answer"], "sql": result.get("sql", ""),
        "columns": result.get("columns", []), "rows": result.get("rows", []),
        "chart": result["chart_spec"], "entities": result.get("entities", {}),
        "semantic_plan": semantic_plan.__dict__ if semantic_plan else None,
        "insight": result.get("insight", {}),
        "retrieval_summary": result.get("retrieval_summary", {}),
        "evidence": result["evidence"], "trace": result["trace"],
        "latency_ms": round((perf_counter() - started) * 1000, 2),
    }


def _error_detail(category: str) -> dict:
    return {"category": category, "message": ERROR_MESSAGES.get(category, "该问题无法在当前安全与语义边界内执行。")}


@app.get("/api/health")
def health() -> dict:
    try:
        database.ping()
        db_status = "ok"
    except Exception as error:
        db_status = f"error:{type(error).__name__}"
    return {"status": "ok" if db_status == "ok" else "degraded", "database": db_status, "semantic_adapter": "wren_http" if settings.wren_base_url else "local_certified_metric"}


@app.post("/api/query")
def query(request: QueryRequest) -> dict:
    started = perf_counter()
    try:
        result = workflow.run(request.question)
    except (WorkflowFailure, ValueError, UnsafeSQL) as error:
        category = error.category if isinstance(error, WorkflowFailure) else str(error)
        raise HTTPException(status_code=422, detail=_error_detail(category)) from error
    return _serialize_result(request.question, result, started)


@app.post("/api/query/stream")
def query_stream(request: QueryRequest) -> StreamingResponse:
    def events():
        started = perf_counter()
        for event in workflow.stream(request.question):
            payload = event
            if event["type"] == "result":
                payload = {"type": "result", "result": _serialize_result(request.question, event["state"], started)}
            elif event["type"] == "error":
                payload = {"type": "error", "error": _error_detail(event["category"]), "trace": event.get("trace", [])}
            yield f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/knowledge")
def knowledge() -> dict:
    return {"items": retriever.documents, "counts": {kind: sum(item["type"] == kind for item in retriever.documents) for kind in ("schema", "metric", "term", "verified_nl_sql")}}


@app.get("/api/evals")
def evaluations() -> dict:
    questions = json.loads((ROOT / "evals" / "golden_questions.json").read_text(encoding="utf-8"))
    results = sorted((ROOT / "evals" / "results").glob("day3-full-*.json"), reverse=True)
    latest_result = json.loads(results[0].read_text(encoding="utf-8")) if results else None
    return {"total": len(questions), "questions": questions, "latest_result": latest_result}

