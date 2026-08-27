from __future__ import annotations

from time import perf_counter
from typing import Any, Callable, Iterator, TypedDict

from .db import Database
from .retrieval import HybridRetriever
from .safety import SQLSafetyGate, UnsafeSQL
from .wren import SemanticPlan, WrenAdapter


class QueryState(TypedDict, total=False):
    question: str
    intent: str
    failure_category: str
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


class WorkflowFailure(ValueError):
    def __init__(self, category: str, trace: list[dict[str, Any]]):
        super().__init__(category)
        self.category = category
        self.trace = trace


class QueryWorkflow:
    NODE_SEQUENCE = [
        "classify", "extract_entities", "check_ambiguity", "retrieve",
        "semantic_plan", "generate_sql", "safety", "dry_run",
        "repair_once", "execute", "chart", "insight",
    ]
    TRACE_DETAILS = {
        "classify": "识别问题意图与安全边界",
        "extract_entities": "抽取指标、维度、过滤条件与时间范围",
        "check_ambiguity": "确认问题可在当前语义边界内执行",
        "retrieve": "混合检索业务知识与已验证问法",
        "semantic_plan": "构建认证指标语义计划",
        "generate_sql": "通过语义适配器生成 SQL",
        "safety": "执行 SQL AST 与 allow-list 校验",
        "dry_run": "在数据库中执行只读 dry-run",
        "repair_once": "检查是否需要一次 SQL 修复",
        "execute": "执行只读查询并限制返回行数",
        "chart": "推荐结果可视化类型",
        "insight": "生成结论、洞察与证据链",
    }

    def __init__(self, database: Database, retriever: HybridRetriever, wren: WrenAdapter, safety: SQLSafetyGate):
        self.database = database
        self.retriever = retriever
        self.wren = wren
        self.safety = safety
        self._nodes = [
            ("classify", self._classify), ("extract_entities", self._extract_entities),
            ("check_ambiguity", self._check_ambiguity), ("retrieve", self._retrieve),
            ("semantic_plan", self._semantic_plan), ("generate_sql", self._generate_sql),
            ("safety", self._safety), ("dry_run", self._dry_run),
            ("repair_once", self._repair_once), ("execute", self._execute),
            ("chart", self._chart), ("insight", self._insight),
        ]
        self._compiled = self._build_langgraph()

    def _trace_node(self, name: str, function: Callable[[QueryState], dict[str, Any]]) -> Callable[[QueryState], dict[str, Any]]:
        def wrapped(state: QueryState) -> dict[str, Any]:
            started = perf_counter()
            try:
                update = function(state)
            except Exception as error:
                category = "unsafe_sql" if isinstance(error, UnsafeSQL) else str(error)
                trace = list(state.get("trace", []))
                trace.append({
                    "node": name, "status": "error",
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                    "detail": category,
                })
                raise WorkflowFailure(category, trace) from error
            status = update.pop("_trace_status", "ok")
            detail = update.pop("_trace_detail", self.TRACE_DETAILS[name])
            trace = list(state.get("trace", []))
            trace.append({
                "node": name, "status": status,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
                "detail": detail,
            })
            update["trace"] = trace
            return update
        return wrapped

    def _build_langgraph(self):
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError:
            return None
        graph = StateGraph(QueryState)
        for name, function in self._nodes:
            graph.add_node(name, self._trace_node(name, function))
        graph.add_edge(START, self._nodes[0][0])
        for (left, _), (right, _) in zip(self._nodes, self._nodes[1:]):
            graph.add_edge(left, right)
        graph.add_edge(self._nodes[-1][0], END)
        return graph.compile()

    @staticmethod
    def _initial_state(question: str) -> QueryState:
        return {"question": question.strip(), "trace": [], "repair_count": 0}

    def run(self, question: str) -> QueryState:
        initial = self._initial_state(question)
        if self._compiled:
            return self._compiled.invoke(initial)
        state = initial
        for name, function in self._nodes:
            state.update(self._trace_node(name, function)(state))
        return state

    def stream(self, question: str) -> Iterator[dict[str, Any]]:
        """Yield real node completions from LangGraph (or the deterministic fallback)."""
        state = self._initial_state(question)
        try:
            if self._compiled:
                for chunk in self._compiled.stream(state, stream_mode="updates"):
                    for node, update in chunk.items():
                        state.update(update)
                        yield {"type": "trace", "trace": update["trace"][-1], "node": node}
            else:
                for name, function in self._nodes:
                    update = self._trace_node(name, function)(state)
                    state.update(update)
                    yield {"type": "trace", "trace": update["trace"][-1], "node": name}
        except WorkflowFailure as error:
            if error.trace:
                yield {"type": "trace", "trace": error.trace[-1], "node": error.trace[-1]["node"]}
            yield {"type": "error", "category": error.category, "trace": error.trace}
            return
        yield {"type": "result", "state": state}

    def _classify(self, state: QueryState) -> dict[str, Any]:
        question = state["question"]
        lower = question.lower()
        if any(word in lower for word in ("删除", "drop", "truncate")) or "手机号" in question or ("导出" in question and "客户" in question):
            return {"intent": "unsafe_request", "failure_category": "unsafe_request"}
        if any(word in question for word in ("股票", "股价", "天气", "航班")):
            return {"intent": "off_domain", "failure_category": "off_domain"}
        if question in {"表现怎么样？", "表现怎么样", "看一下数据"} or ("对比" in question and not any(word in lower for word in ("gmv", "成交总额", "销售额", "净收入", "订单数", "客单价"))):
            return {"intent": "ambiguous"}
        knowledge_markers = ("定义", "是什么？", "是什么", "是否", "包括", "日期字段")
        if any(marker in question for marker in knowledge_markers):
            return {"intent": "knowledge_query"}
        metric_words = ("gmv", "成交总额", "销售额", "净收入", "收入", "订单数", "有效订单", "客单价", "aov", "退款金额", "退款", "销量", "数量")
        return {"intent": "metric_query" if any(word in lower for word in metric_words) else "ambiguous"}

    def _extract_entities(self, state: QueryState) -> dict[str, Any]:
        question = state["question"]
        lower = question.lower()
        dimensions: list[str] = []
        if "区域" in question:
            dimensions.append("region")
        if any(marker in question for marker in ("按渠道", "各渠道", "渠道看", "渠道对比")):
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
                if len(hits) > 1 and key not in dimensions:
                    dimensions.append(key)
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
        knowledge_target = {
            "gmv": "metric.gmv", "net_revenue": "metric.net_revenue",
            "order_count": "metric.order_count", "aov": "metric.aov",
            "refund_amount": "schema.orders", "quantity": "schema.products",
        }[metric]
        if "有效订单" in question and state.get("intent") == "knowledge_query":
            knowledge_target = "term.valid_order"
        if "订单表" in question or "日期字段" in question:
            knowledge_target = "schema.orders"
        return {"entities": {
            "metric": metric, "dimensions": list(dict.fromkeys(dimensions)),
            "filters": filters, "time_range": time_range,
            "knowledge_target": knowledge_target,
        }}

    def _check_ambiguity(self, state: QueryState) -> dict[str, Any]:
        if state.get("failure_category"):
            raise ValueError(state["failure_category"])
        entities = state.get("entities", {})
        ambiguous = state.get("intent") == "ambiguous" or len(state["question"]) < 3
        if state.get("intent") == "metric_query" and not entities.get("dimensions") and entities.get("time_range") == "all_time":
            ambiguous = True
        if ambiguous:
            raise ValueError("ambiguous_question")
        return {"ambiguous": False, "clarification": ""}

    def _retrieve(self, state: QueryState) -> dict[str, Any]:
        candidates = self.retriever.search(state["question"], limit=len(self.retriever.documents))
        target = state["entities"].get("knowledge_target")
        if target:
            candidates.sort(key=lambda item: (item["id"] != target, -item["score"], item["id"]))
        context = candidates[:5]
        top_score = context[0]["score"] if context else 0
        return {"context": context, "retrieval_summary": {
            "hits": len(context), "top_score": top_score,
            "certified_hits": sum(item["type"] in {"metric", "verified_nl_sql"} for item in context),
            "target_hit": bool(target and any(item["id"] == target for item in context)),
        }}

    def _semantic_plan(self, state: QueryState) -> dict[str, Any]:
        entities = state["entities"]
        return {"semantic_plan": SemanticPlan(entities["metric"], entities["dimensions"], entities["time_range"], entities["filters"])}

    def _generate_sql(self, state: QueryState) -> dict[str, Any]:
        if state["intent"] == "knowledge_query":
            return {"sql": "", "_trace_status": "skipped", "_trace_detail": "知识问答无需生成 SQL"}
        dialect = "postgres" if self.database.is_postgres else "sqlite"
        return {"sql": self.wren.plan_sql(state["question"], state["semantic_plan"], dialect, state["context"])}

    def _safety(self, state: QueryState) -> dict[str, Any]:
        if not state.get("sql"):
            return {"sql": "", "_trace_status": "skipped", "_trace_detail": "无 SQL，跳过安全门"}
        dialect = "postgres" if self.database.is_postgres else "sqlite"
        return {"sql": self.safety.validate(state["sql"], dialect)}

    def _dry_run(self, state: QueryState) -> dict[str, Any]:
        if not state.get("sql"):
            return {"dry_run_ok": True, "_trace_status": "skipped", "_trace_detail": "知识问答无需数据库 dry-run"}
        try:
            self.database.explain(state["sql"])
            return {"dry_run_ok": True}
        except Exception:
            return {"dry_run_ok": False}

    def _repair_once(self, state: QueryState) -> dict[str, Any]:
        if not state.get("sql"):
            return {"repair_count": 0, "_trace_status": "skipped", "_trace_detail": "无 SQL，无需修复"}
        if state["dry_run_ok"]:
            return {"repair_count": 0, "_trace_status": "skipped", "_trace_detail": "dry-run 通过，无需修复"}
        if state.get("repair_count", 0) >= 1:
            raise ValueError("dry_run_error")
        dialect = "postgres" if self.database.is_postgres else "sqlite"
        repaired = self.wren.plan_sql(state["question"], state["semantic_plan"], dialect, state["context"])
        repaired = self.safety.validate(repaired, dialect)
        self.database.explain(repaired)
        return {"sql": repaired, "dry_run_ok": True, "repair_count": 1}

    def _execute(self, state: QueryState) -> dict[str, Any]:
        if not state.get("sql"):
            return {"columns": [], "rows": [], "_trace_status": "skipped", "_trace_detail": "知识答案直接来自检索证据"}
        columns, rows = self.database.query(state["sql"])
        return {"columns": columns, "rows": rows}

    def _chart(self, state: QueryState) -> dict[str, Any]:
        if state["intent"] == "knowledge_query":
            return {"chart_spec": {"type": "text", "x": None, "y": None}, "_trace_status": "skipped", "_trace_detail": "知识答案不推荐数值图表"}
        chart_type = "metric" if len(state["columns"]) == 1 else "line" if "order_date" in state["columns"] else "bar"
        return {"chart_spec": {"type": chart_type, "x": state["columns"][0] if len(state["columns"]) > 1 else None, "y": state["columns"][-1]}}

    @staticmethod
    def _evidence(context: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{
            "id": item["id"], "type": item["type"], "title": item["title"],
            "text": item["text"], "score": item["score"],
            "keyword_score": item["keyword_score"], "vector_score": item["vector_score"],
            "match_reason": "认证指标/验证问法优先" if item["type"] in {"metric", "verified_nl_sql"} else "关键词与向量特征共同命中",
        } for item in context]

    def _insight(self, state: QueryState) -> dict[str, Any]:
        evidence = self._evidence(state["context"])
        if state["intent"] == "knowledge_query":
            target = state["entities"].get("knowledge_target")
            source = next((item for item in state["context"] if item["id"] == target), state["context"][0])
            answer = source["text"]
            insight = {
                "title": "知识定义", "summary": answer,
                "highlights": [f"证据来源：{source['title']}", f"知识 ID：{source['id']}", "本回答未执行 SQL"],
            }
            return {"answer": answer, "insight": insight, "evidence": evidence}

        rows = state["rows"]
        metric = state["entities"]["metric"]
        metric_names = {"gmv": "GMV", "net_revenue": "净收入", "order_count": "有效订单数", "aov": "客单价", "refund_amount": "退款金额", "quantity": "销量"}
        metric_name = metric_names.get(metric, metric)
        if state["entities"]["time_range"] == "last_30_days_vs_previous" and rows:
            values = {str(row[0]): float(row[1] or 0) for row in rows}
            current = values.get("current_30d", 0)
            previous = values.get("previous_30d", 0)
            change = current - previous
            rate = change / previous * 100 if previous else None
            direction = "增长" if change >= 0 else "下降"
            rate_text = f"{abs(rate):.2f}%" if rate is not None else "不可计算"
            answer = f"最近 30 天 {metric_name} 为 ¥{current:,.2f}，较上一周期{direction} {rate_text}。"
            insight = {"title": "环比洞察", "summary": answer, "highlights": [f"本期：¥{current:,.2f}", f"上期：¥{previous:,.2f}", f"变化额：¥{change:,.2f}"]}
        elif len(state["columns"]) == 1 and rows:
            value = rows[0][0] or 0
            unit = "笔" if metric == "order_count" else "件" if metric == "quantity" else ""
            answer = f"{metric_name}为 {float(value):,.2f}{unit}。" if metric in {"order_count", "quantity"} else f"{metric_name}为 ¥{float(value):,.2f}。"
            insight = {"title": "核心指标", "summary": answer, "highlights": [f"口径：{metric_name}", "返回 1 个聚合结果", "已通过 SQL 安全门与数据库 dry-run"]}
        else:
            answer = f"查询返回 {len(rows)} 行结果，已按 {state['chart_spec']['y']} 生成可视化建议。"
            top = rows[0] if rows else []
            insight = {"title": "结果洞察", "summary": answer, "highlights": [f"共 {len(rows)} 个分组", f"排序指标：{state['chart_spec']['y']}", f"首行结果：{' / '.join(str(value) for value in top[:2])}" if top else "暂无可用结果"]}
        return {"answer": answer, "insight": insight, "evidence": evidence}
