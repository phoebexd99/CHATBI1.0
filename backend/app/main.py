from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import settings
from .db import Database
from .retrieval import HybridRetriever, ROOT
from .safety import SQLSafetyGate, UnsafeSQL
from .workflow import QueryWorkflow
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
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


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
    except (ValueError, UnsafeSQL) as error:
        raise HTTPException(status_code=422, detail={"category": str(error), "message": "该问题无法在当前安全与语义边界内执行。"}) from error
    return {
        "question": request.question, "answer": result["answer"], "sql": result["sql"],
        "columns": result["columns"], "rows": result["rows"], "chart": result["chart_spec"],
        "entities": result.get("entities", {}), "semantic_plan": result.get("semantic_plan").__dict__ if result.get("semantic_plan") else None,
        "insight": result.get("insight", {}), "retrieval_summary": result.get("retrieval_summary", {}),
        "evidence": result["evidence"], "trace": result["trace"],
        "latency_ms": round((perf_counter() - started) * 1000, 2),
    }


@app.get("/api/knowledge")
def knowledge() -> dict:
    return {"items": retriever.documents, "counts": {kind: sum(item["type"] == kind for item in retriever.documents) for kind in ("schema", "metric", "term", "verified_nl_sql")}}


@app.get("/api/evals")
def evaluations() -> dict:
    questions = json.loads((ROOT / "evals" / "golden_questions.json").read_text(encoding="utf-8"))
    return {"total": len(questions), "questions": questions, "latest_result": None}

