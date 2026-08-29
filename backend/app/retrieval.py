from __future__ import annotations

from collections import Counter
import json
import math
import os
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def _features(text: str) -> Counter[str]:
    normalized = re.sub(r"\s+", "", text.lower())
    latin = re.findall(r"[a-z0-9_]+", normalized)
    chinese = [char for char in normalized if "\u4e00" <= char <= "\u9fff"]
    bigrams = [normalized[index:index + 2] for index in range(max(0, len(normalized) - 1))]
    return Counter(latin + chinese + bigrams)


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    dot = sum(value * right.get(key, 0) for key, value in left.items())
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


class HybridRetriever:
    """Simplified local hybrid retrieval; preserves trace fields used by pgvector target."""

    def __init__(self, knowledge_path: Path | None = None):
        if knowledge_path is None:
            profile = os.getenv("CHATBI_DATA_PROFILE", "demo").strip().lower()
            filename = "knowledge_olist.json" if profile == "olist" else "knowledge.json"
            knowledge_path = ROOT / "data" / filename
        path = knowledge_path
        self.documents: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        query_features = _features(query)
        normalized_query = re.sub(r"\s+", "", query.lower())
        scored = []
        for document in self.documents:
            haystack = " ".join([document["title"], document["text"], *document.get("tags", [])])
            features = _features(haystack)
            overlap = len(set(query_features) & set(features)) / max(1, len(set(query_features)))
            vector = _cosine(query_features, features)
            # Certified metric aliases receive a small, inspectable boost.
            metric_alias_hit = document["type"] == "metric" and any(
                re.sub(r"\s+", "", tag.lower()) in normalized_query
                for tag in document.get("tags", [])
            )
            score = 0.55 * overlap + 0.45 * vector + (0.35 if metric_alias_hit else 0.0)
            scored.append({
                "id": document["id"], "type": document["type"], "title": document["title"],
                "text": document["text"], "score": round(score, 4),
                "keyword_score": round(overlap, 4), "vector_score": round(vector, 4),
            })
        scored.sort(key=lambda item: (-item["score"], item["id"]))
        return scored[:limit]

