from backend.app.retrieval import HybridRetriever


def test_gmv_question_retrieves_metric():
    results = HybridRetriever().search("最近 30 天 GMV 是多少？")
    assert "metric.gmv" in {item["id"] for item in results[:3]}
    assert all("keyword_score" in item and "vector_score" in item for item in results)

