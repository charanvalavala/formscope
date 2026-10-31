import numpy as np
from formscope import semantic


def test_semantic_search_ranks_paraphrase_and_filters_weak_matches(monkeypatch):
    monkeypatch.setattr(
        semantic, "passage_vectors", lambda texts: np.array([[1.0, 0.0], [0.0, 1.0]])
    )
    monkeypatch.setattr(semantic, "embed", lambda texts: np.array([[1.0, 0.0]]))
    results = semantic.rank_semantic(
        "Vendor disruption", ["Supplier dependence", "Dividend policy"]
    )
    assert [row["passage_index"] for row in results] == [0]


def test_hybrid_preserves_sources_when_results_overlap(monkeypatch):
    from formscope import retrieval

    monkeypatch.setattr(
        semantic,
        "rank_semantic",
        lambda *args: [{"passage_index": 1}, {"passage_index": 0}],
    )
    monkeypatch.setattr(
        retrieval, "rank_passages", lambda *args: [{"passage_index": 1}]
    )
    results = semantic.rank_hybrid("question", ["first", "second"], 2)
    assert results[0]["text"] == "second"
    assert len({row["passage_index"] for row in results}) == 2
