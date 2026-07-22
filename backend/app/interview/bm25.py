"""Lightweight BM25 + RRF helpers for interview question retrieval."""

from __future__ import annotations

import math
import re
from collections import defaultdict


def tokenize(text: str) -> list[str]:
    """Tokenize Latin words + CJK unigrams (short stems; no jieba dependency)."""
    tokens: list[str] = []
    for m in re.finditer(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text or ""):
        tokens.append(m.group(0).lower())
    return tokens


class BM25Index:
    """In-memory Okapi BM25 over a small candidate set."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._doc_ids: list[str] = []
        self._doc_freqs: list[dict[str, int]] = []
        self._doc_lens: list[int] = []
        self._avgdl: float = 0.0
        self._df: dict[str, int] = defaultdict(int)
        self._n = 0
        self._idf: dict[str, float] = {}

    def clear(self) -> None:
        self._doc_ids.clear()
        self._doc_freqs.clear()
        self._doc_lens.clear()
        self._avgdl = 0.0
        self._df.clear()
        self._n = 0
        self._idf.clear()

    def add_document(self, doc_id: str, text: str) -> None:
        tokens = tokenize(text)
        tf: dict[str, int] = defaultdict(int)
        for t in tokens:
            tf[t] += 1
        for t in tf:
            self._df[t] += 1
        self._doc_ids.append(doc_id)
        self._doc_freqs.append(dict(tf))
        self._doc_lens.append(len(tokens))
        self._n += 1
        self._avgdl = (sum(self._doc_lens) / self._n) if self._n else 0.0
        self._idf = {
            term: math.log(1.0 + (self._n - df + 0.5) / (df + 0.5))
            for term, df in self._df.items()
        }

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        if self._n == 0:
            return []
        q_terms = tokenize(query)
        if not q_terms:
            return []
        scores: list[tuple[str, float]] = []
        for i, doc_id in enumerate(self._doc_ids):
            score = 0.0
            dl = self._doc_lens[i]
            tf_map = self._doc_freqs[i]
            for term in q_terms:
                if term not in tf_map:
                    continue
                idf = self._idf.get(term, 0.0)
                tf = tf_map[term]
                denom = tf + self.k1 * (1 - self.b + self.b * dl / (self._avgdl or 1.0))
                score += idf * (tf * (self.k1 + 1)) / (denom or 1.0)
            if score > 0:
                scores.append((doc_id, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


def rrf_fuse(
    vector_ranked: list[tuple[str, float]],
    bm25_ranked: list[tuple[str, float]],
    *,
    k: int = 60,
) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion over two ranked lists (id, score)."""
    ranks: dict[str, float] = defaultdict(float)
    for rank, (doc_id, _) in enumerate(vector_ranked, start=1):
        ranks[doc_id] += 1.0 / (k + rank)
    for rank, (doc_id, _) in enumerate(bm25_ranked, start=1):
        ranks[doc_id] += 1.0 / (k + rank)
    return sorted(ranks.items(), key=lambda x: x[1], reverse=True)
