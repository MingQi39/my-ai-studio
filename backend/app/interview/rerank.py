"""Lightweight lexical rerank for interview question candidates (P2 default)."""

from __future__ import annotations

from app.interview.bm25 import tokenize


def lexical_rerank(
    query: str,
    docs: list[tuple[str, str, float]],
    *,
    topic: str | None = None,
    level: str | None = None,
) -> list[tuple[str, float]]:
    """Rerank (doc_id, text, prior_score) by query overlap + topic/level boost.

    Returns list of (doc_id, new_score) descending. No neural CrossEncoder dependency.
    """
    q_tokens = set(tokenize(query))
    topic_l = (topic or "").lower()
    level_l = (level or "").lower()
    scored: list[tuple[str, float]] = []
    for doc_id, text, prior in docs:
        t_tokens = set(tokenize(text))
        overlap = len(q_tokens & t_tokens) / max(len(q_tokens), 1)
        bonus = 0.0
        low = text.lower()
        if topic_l and topic_l in low:
            bonus += 0.05
        if level_l and level_l in low:
            bonus += 0.02
        scored.append((doc_id, float(prior) + overlap + bonus))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
