from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from .config import Settings


@dataclass
class SemanticPlan:
    metric: str
    dimensions: list[str]
    time_range: str
    filters: dict[str, Any]


class WrenAdapter(Protocol):
    def plan_sql(self, question: str, plan: SemanticPlan, dialect: str, context: list[dict[str, Any]]) -> str: ...


class LocalCertifiedMetricAdapter:
    """Deterministic local semantic adapter for the Day 2 demo coverage."""

    def plan_sql(self, question: str, plan: SemanticPlan, dialect: str, context: list[dict[str, Any]]) -> str:
        metric_sql = {
            "gmv": ("ROUND(SUM(orders.gross_amount), 2)", "gmv"),
            "net_revenue": ("ROUND(SUM(orders.gross_amount - orders.discount_amount - orders.refund_amount), 2)", "net_revenue"),
            "order_count": ("COUNT(DISTINCT orders.order_id)", "order_count"),
            "aov": ("ROUND(SUM(orders.gross_amount) / NULLIF(COUNT(DISTINCT orders.order_id), 0), 2)", "aov"),
            "refund_amount": ("ROUND(SUM(orders.refund_amount), 2)", "refund_amount"),
            "quantity": ("SUM(order_items.quantity)", "quantity"),
        }
        if plan.metric not in metric_sql:
            raise ValueError(f"Local certified adapter does not support metric: {plan.metric}")
        dimensions = [item for item in plan.dimensions if item in {"region", "channel", "order_date", "category"}]
        metric_expression, metric_alias = metric_sql[plan.metric]
        select_parts = [f"orders.{item}" if item in {"region", "channel", "order_date"} else "products.category" for item in dimensions]
        select_parts.append(f"{metric_expression} AS {metric_alias}")
        where = ["status IN ('paid', 'refunded')"]
        date_field = "orders.order_date"
        if plan.time_range in {"last_7_days", "last_14_days", "last_30_days"}:
            days = {"last_7_days": 6, "last_14_days": 13, "last_30_days": 29}[plan.time_range]
            where.append(f"{date_field} >= CURRENT_DATE - INTERVAL '{days} days'" if dialect == "postgres" else f"{date_field} >= date('now', '-{days} days')")
        elif plan.time_range == "this_month":
            where.append("orders.order_date >= date_trunc('month', CURRENT_DATE)" if dialect == "postgres" else "orders.order_date >= date('now', 'start of month')")
        elif plan.time_range == "last_year_same_period":
            if dialect == "postgres":
                where.extend(["orders.order_date >= CURRENT_DATE - INTERVAL '1 year' - INTERVAL '29 days'", "orders.order_date <= CURRENT_DATE - INTERVAL '1 year'"])
            else:
                where.extend(["orders.order_date >= date('now', '-1 year', '-29 days')", "orders.order_date <= date('now', '-1 year')"])
        elif plan.time_range == "last_30_days_vs_previous":
            period_expression = "CASE WHEN orders.order_date >= CURRENT_DATE - INTERVAL '29 days' THEN 'current_30d' ELSE 'previous_30d' END" if dialect == "postgres" else "CASE WHEN orders.order_date >= date('now', '-29 days') THEN 'current_30d' ELSE 'previous_30d' END"
            select_parts.insert(0, f"{period_expression} AS period")
            where.append("orders.order_date >= CURRENT_DATE - INTERVAL '59 days'" if dialect == "postgres" else "orders.order_date >= date('now', '-59 days')")
        joins = ""
        if "category" in dimensions or plan.metric == "quantity":
            joins = " JOIN order_items ON order_items.order_id = orders.order_id JOIN products ON products.product_id = order_items.product_id"
        for key, value in plan.filters.items():
            if key in {"region", "channel"}:
                values = value if isinstance(value, list) else [value]
                safe_values = [str(item).replace("'", "''") for item in values]
                where.append(f"orders.{key} IN ({', '.join(repr(item) for item in safe_values)})")
        sql = f"SELECT {', '.join(select_parts)} FROM orders{joins} WHERE {' AND '.join(where)}"
        if dimensions:
            group_parts = [f"orders.{item}" if item in {"region", "channel", "order_date"} else "products.category" for item in dimensions]
            sql += f" GROUP BY {', '.join(group_parts)} ORDER BY {metric_alias} DESC LIMIT 100"
        elif plan.time_range == "last_30_days_vs_previous":
            sql += " GROUP BY period ORDER BY period LIMIT 2"
        else:
            sql += " LIMIT 1"
        return sql


class WrenHTTPAdapter:
    """Design-aligned HTTP boundary for a configured Wren Core gateway."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def plan_sql(self, question: str, plan: SemanticPlan, dialect: str, context: list[dict[str, Any]]) -> str:
        headers = {"Authorization": f"Bearer {self.settings.wren_api_key}"} if self.settings.wren_api_key else {}
        response = httpx.post(
            f"{self.settings.wren_base_url.rstrip('/')}/v1/plan",
            json={"question": question, "semantic_plan": plan.__dict__, "dialect": dialect, "context": context},
            headers=headers,
            timeout=self.settings.wren_timeout_seconds,
        )
        response.raise_for_status()
        sql = response.json().get("sql")
        if not sql:
            raise ValueError("Wren response did not contain SQL")
        return sql


def make_wren_adapter(settings: Settings) -> WrenAdapter:
    return WrenHTTPAdapter(settings) if settings.wren_base_url else LocalCertifiedMetricAdapter()

