from __future__ import annotations

from time import perf_counter
from typing import Any, Callable, TypedDict

from .db import Database
from .retrieval import HybridRetriever
from .safety import SQLSafetyGate
from .wren import SemanticPlan, WrenAdapter


class QueryState(TypedDict, total=False):
    question: str
    intent: str
    entities: dict[str, Any]
    ambiguous: bool
    clarification: str
    context: list[dict[str, Any]]
    semantic_plan: SemanticPlan
    sql: str
    dry_run_ok: bool
    repair_count: int
    columns: list[str]
    rows: list[list[Any]]
    chart_spec: dict[str, Any]
    answer: str
    evidence: list[dict[str, Any]]
    insight: dict[str, Any]
    retrieval_summary: dict[str, Any]
    trace: list[dict[str, Any]]


class QueryWorkflow:
    def __init__(self, database: Database, retriever: HybridRetriever, wren: WrenAdapter, safety: SQLSafetyGate):
        self.database = database
        self.retriever = retriever
        self.wren = wren
        self.safety = safety
        self._compiled = self._build_langgraph()

    def _trace_node(self, name: str, function: Callable[[QueryState], dict[str, Any]]) -> Callable[[QueryState], dict[str, Any]]:
        def wrapped(state: QueryState) -> dict[str, Any]:
            started = perf_counter()
            update = function(state)
            trace = list(state.get("trace", []))
            trace.append({"node": name, "status": "ok", "duration_ms": round((perf_counter() - started) * 1000, 2)})
            update["trace"] = trace
            return update
        return wrapped

    def _build_langgraph(self):
        # Implemented with LangGraph when installed; the fallback keeps local smoke tests runnable.
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError:
            return None
        graph = StateGraph(QueryState)
        nodes = [
            ("classify", self._classify), ("extract_entities", self._extract_entities),
            ("check_ambiguity", self._check_ambiguity), ("retrieve", self._retrieve),
            ("semantic_plan", self._semantic_plan), ("generate_sql", self._generate_sql),
            ("safety", self._safety), ("dry_run", self._dry_run),
            ("repair_once", self._repair_once), ("execute", self._execute),
            ("chart", self._chart), ("insight", self._insight),
        ]
        for name, function in nodes:
            graph.add_node(name, self._trace_node(name, function))
        graph.add_edge(START, "classify")
        for (left, _), (right, _) in zip(nodes, nodes[1:]):
            graph.add_edge(left, right)
        graph.add_edge("insight", END)
        return graph.compile()

    def run(self, question: str) -> QueryState:
        initial: QueryState = {"question": question.strip(), "trace": [], "repair_count": 0}
        if self._compiled:
            return self._compiled.invoke(initial)
        state = initial
        for name, function in [
            ("classify", self._classify), ("extract_entities", self._extract_entities),
            ("check_ambiguity", self._check_ambiguity), ("retrieve", self._retrieve),
            ("semantic_plan", self._semantic_plan), ("generate_sql", self._generate_sql),
            ("safety", self._safety), ("dry_run", self._dry_run),
            ("repair_once", self._repair_once), ("execute", self._execute),
            ("chart", self._chart), ("insight", self._insight),
        ]:
            state.update(self._trace_node(name, function)(state))
        return state

    def _classify(self, state: QueryState) -> dict[str, Any]:
        question = state["question"]
        if any(word in question for word in ("删除", "drop", "truncate", "导出手机号")):
            raise ValueError("unsafe_request")
        if any(word in question for word in ("股票", "股价", "天气", "航班")):
            raise ValueError("off_domain")
        metric_words = ("gmv", "成交总额", "销售额", "净收入", "收入", "订单数", "有效订单", "客单价", "aov", "退款金额", "退款", "销量", "数量")
        return {"intent": "metric_query" if any(word in question.lower() for word in metric_words) else "knowledge_query"}

    def _extract_entities(self, state: QueryState) -> dict[str, Any]:
        question = state["question"]
        dimensions = []
        if "区域" in question:
            dimensions.append("region")
        if "渠道" in question:
            dimensions.append("channel")
        if "每天" in question or "趋势" in question:
            dimensions.append("order_date")
        if "品类" in question:
            dimensions.append("category")
        filters: dict[str, Any] = {}
        for key, labels in (("region", ("华东", "华南", "华北", "西南")), ("channel", ("抖音", "天猫", "小程序"))):
            hits = [label for label in labels if label in question]
            if hits:
                filters[key] = hits[0] if len(hits) == 1 else hits
        lower = question.lower()
        metric = "gmv"
        if "净收入" in question or "net_revenue" in lower:
            metric = "net_revenue"
        elif "订单数" in question or "有效订单" in question or "order_count" in lower:
            metric = "order_count"
        elif "客单价" in question or "aov" in lower:
            metric = "aov"
        elif "退款金额" in question:
            metric = "refund_amount"
        elif "销量" in question or "数量" in question:
            metric = "quantity"
        if "两周" in question or "14 天" in question or "14天" in question:
            time_range = "last_14_days"
        elif "7 天" in question or "7天" in question:
            time_range = "last_7_days"
        elif "本月" in question:
            time_range = "this_month"
        elif "去年同期" in question:
            time_range = "last_year_same_period"
        elif "30 天" in question or "30天" in question:
            time_range = "last_30_days_vs_previous" if "环比" in question else "last_30_days"
        else:
            time_range = "all_time"
        return {"entities": {"metric": metric, "dimensions": list(dict.fromkeys(dimensions)), "filters": filters, "time_range": time_range}}

    def _check_ambiguity(self, state: QueryState) -> dict[str, Any]:
        question = state["question"]
        ambiguous = len(question) < 3 or question in {"表现怎么样？", "表现怎么样", "看一下数据"}
        entities = state.get("entities", {})
        if state.get("intent") == "metric_query" and not entities.get("dimensions") and entities.get("time_range") == "all_time":
            ambiguous = True
        if ambiguous:
            raise ValueError("ambiguous_question")
        return {"ambiguous": False, "clarification": ""}

    def _retrieve(self, state: QueryState) -> dict[str, Any]:
        context = self.retriever.search(state["question"], limit=5)
        top_score = context[0]["score"] if context else 0
        return {"context": context, "retrieval_summary": {"hits": len(context), "top_score": top_score, "certified_hits": sum(item["type"] in {"metric", "verified_nl_sql"} for item in context)}}

    def _semantic_plan(self, state: QueryState) -> dict[str, Any]:
        entities = state["entities"]
        return {"semantic_plan": SemanticPlan(entities["metric"], entities["dimensions"], entities["time_range"], entities["filters"])}

    def _generate_sql(self, state: QueryState) -> dict[str, Any]:
        dialect = "postgres" if self.database.is_postgres else "sqlite"
        return {"sql": self.wren.plan_sql(state["question"], state["semantic_plan"], dialect, state["context"])}

    def _safety(self, state: QueryState) -> dict[str, Any]:
        dialect = "postgres" if self.database.is_postgres else "sqlite"
        return {"sql": self.safety.validate(state["sql"], dialect)}

    def _dry_run(self, state: QueryState) -> dict[str, Any]:
        try:
            self.database.explain(state["sql"])
            return {"dry_run_ok": True}
        except Exception:
            return {"dry_run_ok": False}

    def _repair_once(self, state: QueryState) -> dict[str, Any]:
        if state["dry_run_ok"]:
            return {"repair_count": 0}
        if state.get("repair_count", 0) >= 1:
            raise ValueError("dry_run_error")
        dialect = "postgres" if self.database.is_postgres else "sqlite"
        repaired = self.wren.plan_sql(state["question"], state["semantic_plan"], dialect, state["context"])
        repaired = self.safety.validate(repaired, dialect)
        self.database.explain(repaired)
        return {"sql": repaired, "dry_run_ok": True, "repair_count": 1}

    def _execute(self, state: QueryState) -> dict[str, Any]:
        columns, rows = self.database.query(state["sql"])
        return {"columns": columns, "rows": rows}

    def _chart(self, state: QueryState) -> dict[str, Any]:
        chart_type = "metric" if len(state["columns"]) == 1 else "line" if "order_date" in state["columns"] else "bar"
        return {"chart_spec": {"type": chart_type, "x": state["columns"][0] if len(state["columns"]) > 1 else None, "y": state["columns"][-1]}}

    def _insight(self, state: QueryState) -> dict[str, Any]:
        rows = state["rows"]
        metric = state["entities"]["metric"]
        metric_names = {"gmv": "GMV", "net_revenue": "净收入", "order_count": "有效订单数", "aov": "客单价", "refund_amount": "退款金额", "quantity": "销量"}
        metric_name = metric_names.get(metric, metric)
        if len(state["columns"]) == 1 and rows:
            value = rows[0][0] or 0
            unit = "笔" if metric == "order_count" else "件" if metric == "quantity" else ""
            answer = f"{metric_name}为 {float(value):,.2f}{unit}。" if metric in {"order_count", "quantity"} else f"{metric_name}为 ¥{float(value):,.2f}。"
            insight = {"title": "核心指标", "summary": answer, "highlights": [f"口径：{metric_name}", f"返回 1 个聚合结果", "已通过 SQL 安全门与数据库 dry-run"]}
        else:
            answer = f"查询返回 {len(rows)} 行结果，已按 {state['chart_spec']['y']} 生成可视化建议。"
            top = rows[0] if rows else []
            insight = {"title": "结果洞察", "summary": answer, "highlights": [f"共 {len(rows)} 个分组", f"排序指标：{state['chart_spec']['y']}", f"首行结果：{' / '.join(str(value) for value in top[:2])}" if top else "暂无可用结果"]}
        evidence = [{"id": item["id"], "type": item["type"], "title": item["title"], "text": item["text"], "score": item["score"], "keyword_score": item["keyword_score"], "vector_score": item["vector_score"], "match_reason": "认证指标/验证问法优先" if item["type"] in {"metric", "verified_nl_sql"} else "关键词与向量特征共同命中"} for item in state["context"]]
        return {"answer": answer, "insight": insight, "evidence": evidence}

