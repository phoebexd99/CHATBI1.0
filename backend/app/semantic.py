from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def _normalized(text: str) -> str:
    return re.sub(r"\s+", "", text.lower())


@dataclass(frozen=True)
class MetricDefinition:
    id: str
    name: str
    display_name: str
    description: str
    aliases: tuple[str, ...]
    expression: str
    base_table: str
    date_field: str | None
    time_dimension: str | None
    base_filter: str | None
    joins: tuple[str, ...]
    dimensions: dict[str, str]
    dimension_joins: dict[str, tuple[str, ...]]
    expression_overrides: dict[str, str]
    filter_columns: dict[str, str]
    unit: str
    owner: str
    certified: bool


class SemanticCatalog:
    """Versioned, data-driven business semantics used by the local adapter.

    Production Wren can replace SQL planning, while this catalog remains useful
    for deterministic local development, retrieval targets, and evaluation.
    """

    def __init__(
        self,
        metrics_path: Path | None = None,
        dimensions_path: Path | None = None,
    ) -> None:
        if metrics_path is None:
            profile = os.getenv("CHATBI_DATA_PROFILE", "demo").strip().lower()
            filename = "metrics_olist.json" if profile == "olist" else "metrics.json"
            metrics_path = ROOT / "data" / filename
        metrics_payload = json.loads(metrics_path.read_text(encoding="utf-8"))
        self.metrics: dict[str, MetricDefinition] = {}
        for item in metrics_payload:
            metric = MetricDefinition(
                id=item["id"],
                name=item["name"],
                display_name=item["display_name"],
                description=item["description"],
                aliases=tuple(item.get("aliases", [])),
                expression=item["expression"],
                base_table=item["base_table"],
                date_field=item.get("date_field"),
                time_dimension=item.get("time_dimension"),
                base_filter=item.get("base_filter"),
                joins=tuple(item.get("joins", [])),
                dimensions=dict(item.get("dimensions", {})),
                dimension_joins={key: tuple(value) for key, value in item.get("dimension_joins", {}).items()},
                expression_overrides=dict(item.get("expression_overrides", {})),
                filter_columns=dict(item.get("filter_columns", {})),
                unit=item.get("unit", "number"),
                owner=item.get("owner", "经营分析"),
                certified=bool(item.get("certified", False)),
            )
            self.metrics[metric.name] = metric

        dimensions_payload = json.loads((dimensions_path or ROOT / "data" / "dimensions.json").read_text(encoding="utf-8"))
        self.dimensions: dict[str, dict[str, Any]] = {item["id"]: item for item in dimensions_payload}
        self._metric_aliases = sorted(
            (
                (_normalized(alias), metric.name)
                for metric in self.metrics.values()
                for alias in {*metric.aliases, metric.name, metric.display_name}
                if alias
            ),
            key=lambda item: (-len(item[0]), item[1]),
        )

    def metric(self, name: str) -> MetricDefinition:
        try:
            return self.metrics[name]
        except KeyError as error:
            raise ValueError(f"Unknown certified metric: {name}") from error

    def match_metric(self, question: str) -> str | None:
        normalized = _normalized(question)
        return next((name for alias, name in self._metric_aliases if alias in normalized), None)

    def match_requested_dimensions(self, question: str) -> list[str]:
        normalized = _normalized(question)
        matches: list[str] = []
        for dimension_id, definition in self.dimensions.items():
            aliases = definition.get("aliases", [])
            if any(_normalized(alias) in normalized for alias in aliases):
                matches.append(dimension_id)
        return matches

    @staticmethod
    def asks_for_time_series(question: str) -> bool:
        return any(marker in question for marker in ("每天", "每日", "按日", "逐日", "趋势"))

    def metric_aliases(self) -> tuple[str, ...]:
        return tuple(alias for metric in self.metrics.values() for alias in metric.aliases)

    def knowledge_id(self, metric_name: str) -> str:
        return self.metric(metric_name).id

    def display_name(self, metric_name: str) -> str:
        return self.metric(metric_name).display_name

    def unit(self, metric_name: str) -> str:
        return self.metric(metric_name).unit
