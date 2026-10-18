from formscope.retrieval import rank_passages, split_passages


def test_rank_passages_returns_relevant_evidence_in_rank_order():
    passages = [
        "The company faces currency exchange risks in several markets.",
        "Supply chain disruptions may delay critical components and increase costs.",
        "Supply chain exposure was reviewed in prior filings.",
        "The board approved a new office location during the year.",
    ]

    result = rank_passages("What supply chain risks could increase costs?", passages, 3)

    assert result[0]["text"] == passages[1]
    assert result[0]["rank"] == 1
    assert result[0]["score"] > result[-1]["score"]


def test_split_passages_covers_long_text_with_overlap():
    text = ". ".join(f"Sentence {index} explains a filing risk." for index in range(80))

    result = split_passages(text, size=300, overlap=60)

    assert len(result) > 1
    assert "Sentence 0" in result[0]
    assert "Sentence 79" in result[-1]


def test_rank_passages_returns_empty_for_queries_without_terms():
    assert rank_passages("a to of", ["Supply chain risk disclosure"], 3) == []
