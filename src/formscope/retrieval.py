from __future__ import annotations

import re
from collections import Counter

STOPWORDS = {"about", "after", "again", "all", "also", "and", "any", "are", "because", "been", "before", "being", "between", "but", "can", "could", "did", "does", "for", "from", "had", "has", "have", "how", "into", "its", "more", "most", "not", "of", "on", "other", "our", "out", "over", "should", "some", "such", "than", "that", "the", "their", "them", "there", "these", "they", "this", "those", "through", "to", "under", "was", "were", "what", "when", "where", "which", "who", "will", "with", "would", "you"}


def terms(text: str) -> list[str]:
    return [token[:-1] if token.endswith("s") and len(token) > 4 else token for token in re.findall(r"[a-z0-9]+", text.casefold()) if len(token) > 2 and token not in STOPWORDS]


def split_passages(text: str, size: int = 1100, overlap: int = 180) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    passages = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            boundary = text.rfind(". ", start + size // 2, end)
            if boundary > start:
                end = boundary + 1
        passages.append(text[start:end].strip())
        if end == len(text):
            break
        start = max(end - overlap, start + 1)
    return passages


def rank_passages(question: str, passages: list[str], top_k: int = 5) -> list[dict[str, object]]:
    query = Counter(terms(question))
    if not query:
        return []
    ranked = []
    for index, passage in enumerate(passages):
        document = Counter(terms(passage))
        overlap = sum(min(count, document.get(token, 0)) for token, count in query.items())
        coverage = sum(token in document for token in query)
        score = (overlap + coverage) / max(1, len(query))
        if coverage >= min(2, len(query)):
            ranked.append({"rank": 0, "score": score, "text": passage, "passage_index": index})
    ranked.sort(key=lambda item: (item["score"], -int(item["passage_index"])), reverse=True)
    for rank, item in enumerate(ranked[:top_k], start=1):
        item["rank"] = rank
    return ranked[:top_k]
