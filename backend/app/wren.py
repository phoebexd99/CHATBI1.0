from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Protocol

import httpx

from .config import Settings
from .semantic import SemanticCatalog


@dataclass
class SemanticPlan:
    metric: str
    dimensions: list[str]
    time_range: str
    filters: dict[str, Any]


class WrenAdapter(Protocol):
    def plan_sql(self, question: str, plan: SemanticPlan, dialect: str, context: list[dict[str, Any]]) -> str: ...


class LocalCertifiedMetricAdapter:
    """Deterministic semantic adapter driven by the versioned metric catalog."""

    def __init__(self, catalog: SemanticCatalog | None = None):
        self.catalog = catalog or SemanticCatalog()

    @staticmethod
    def _time_predicates(time_range: str, date_field: str, dialect: str) -> tuple[list[str], str | None]:
        comparison = time_range.endswith("_vs_previous")
        base_range = time_range.removesuffix("_vs_previous")
        match = re.fullmatch(r"last_(\d+)_days", base_range)
        if match:
            days = int(match.group(1))
            offset = days - 1
            if comparison:
                total_offset = days * 2 - 1
                threshold = f"CURRENT_DATE - INTERVAL '{offset} days'" if dialect == "postgres" else f"date('now', '-{offset} days')"
                start = f"CURRENT_DATE - INTERVAL '{total_offset} days'" if dialect == "postgres" else f"date('now', '-{total_offset} days')"
                period = f"CASE WHEN {date_field} >= {threshold} THEN 'current_{days}d' ELSE 'previous_{days}d' END"
                return [f"{date_field} >= {start}"], period
            start = f"CURRENT_DATE - INTERVAL '{offset} days'" if dialect == "postgres" else f"date('now', '-{offset} days')"
            return [f"{date_field} >= {start}"], None
        if time_range == "today":
            return [f"{date_field} = CURRENT_DATE" if dialect == "postgres" else f"{date_field} = date('now')"], None
        if time_range == "this_week":
            start = "date_trunc('week', CURRENT_DATE)" if dialect == "postgres" else "date('now', '-' || ((cast(strftime('%w','now') as integer) + 6) % 7) || ' days')"
            return [f"{date_field} >= {start}"], None
        if time_range == "this_month":
            start = "date_trunc('month', CURRENT_DATE)" if dialect == "postgres" else "date('now', 'start of month')"
            return [f"{date_field} >= {start}"], None
        if time_range == "this_quarter":
            start = "date_trunc('quarter', CURRENT_DATE)" if dialect == "postgres" else "date('now', 'start of year', '+' || (((cast(strftime('%m','now') as integer) - 1) / 3) * 3) || ' months')"
            return [f"{date_field} >= {start}"], None
        if time_range == "this_year":
            start = "date_trunc('year', CURRENT_DATE)" if dialect == "postgres" else "date('now', 'start of year')"
            return [f"{date_field} >= {start}"], None
        if time_range == "last_year_same_period":
            if dialect == "postgres":
                return [f"{date_field} >= CURRENT_DATE - INTERVAL '1 year' - INTERVAL '29 days'", f"{date_field} <= CURRENT_DATE - INTERVAL '1 year'"], None
            return [f"{date_field} >= date('now', '-1 year', '-29 days')", f"{date_field} <= date('now', '-1 year')"], None
        return [], None

    def plan_sql(self, question: str, plan: SemanticPlan, dialect: str, context: list[dict[str, Any]]) -> str:
        metric = self.catalog.metric(plan.metric)
        unsupported = [item for item in plan.dimensions if item not in metric.dimensions]
        if unsupported:
            raise ValueError(f"unsupported_dimension:{','.join(unsupported)}")

        dimensions = list(dict.fromkeys(plan.dimensions))
        metric_expression = metric.expression
        for dimension in dimensions:
            if dimension in metric.expression_overrides:
                metric_expression = metric.expression_overrides[dimension]

        select_parts = [f"{metric.dimensions[item]} AS {item}" for item in dimensions]
        select_parts.append(f"{metric_expression} AS {metric.name}")
        where = [metric.base_filter] if metric.base_filter else []
        period_expression = None
        if metric.date_field:
            time_predicates, period_expression = self._time_predicates(plan.time_range, metric.date_field, dialect)
            where.extend(time_predicates)
            if period_expression:
                select_parts.insert(0, f"{period_expression} AS period")

        joins = list(metric.joins)
        for key in [*dimensions, *plan.filters.keys()]:
            joins.extend(metric.dimension_joins.get(key, ()))
        joins = list(dict.fromkeys(joins))

        for key, value in plan.filters.items():
            column = metric.filter_columns.get(key)
            if not column:
                raise ValueError(f"unsupported_filter:{key}")
            values = value if isinstance(value, list) else [value]
            safe_values = [str(item).replace("'", "''") for item in values]
            literals = ", ".join(f"'{item}'" for item in safe_values)
            where.append(f"{column} IN ({literals})")

        where_sql = f" WHERE {' AND '.join(where)}" if where else ""
        joins_sql = f" {' '.join(joins)}" if joins else ""
        sql = f"SELECT {', '.join(select_parts)} FROM {metric.base_table}{joins_sql}{where_sql}"
        group_parts = [metric.dimensions[item] for item in dimensions]
        if period_expression:
            group_parts.insert(0, "period")
        if group_parts:
            sql += f" GROUP BY {', '.join(group_parts)}"
        if dimensions:
            sql += f" ORDER BY {metric.name} DESC LIMIT 100"
        elif period_expression:
            sql += " ORDER BY period LIMIT 2"
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


def make_wren_adapter(settings: Settings, catalog: SemanticCatalog | None = None) -> WrenAdapter:
    return WrenHTTPAdapter(settings) if settings.wren_base_url else LocalCertifiedMetricAdapter(catalog)

