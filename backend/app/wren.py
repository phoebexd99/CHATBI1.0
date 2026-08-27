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
    filters: dict[str, str]


class WrenAdapter(Protocol):
    def plan_sql(self, question: str, plan: SemanticPlan, dialect: str, context: list[dict[str, Any]]) -> str: ...


class LocalCertifiedMetricAdapter:
    """Simplified deterministic adapter. Replace with WrenHTTPAdapter without changing graph nodes."""

    def plan_sql(self, question: str, plan: SemanticPlan, dialect: str, context: list[dict[str, Any]]) -> str:
        if plan.metric != "gmv":
            raise ValueError(f"Day 1 certified adapter does not yet support metric: {plan.metric}")
        dimensions = [item for item in plan.dimensions if item in {"region", "channel", "order_date"}]
        select_parts = dimensions + ["ROUND(SUM(gross_amount), 2) AS gmv"]
        where = ["status IN ('paid', 'refunded')"]
        if plan.time_range == "last_30_days":
            where.append("order_date >= CURRENT_DATE - INTERVAL '29 days'" if dialect == "postgres" else "order_date >= date('now', '-29 days')")
        if plan.time_range == "last_7_days":
            where.append("order_date >= CURRENT_DATE - INTERVAL '6 days'" if dialect == "postgres" else "order_date >= date('now', '-6 days')")
        for key, value in plan.filters.items():
            if key in {"region", "channel"}:
                safe_value = value.replace("'", "''")
                where.append(f"{key} = '{safe_value}'")
        sql = f"SELECT {', '.join(select_parts)} FROM orders WHERE {' AND '.join(where)}"
        if dimensions:
            sql += f" GROUP BY {', '.join(dimensions)} ORDER BY gmv DESC LIMIT 100"
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

