"""Retrieve interview questions from the local RAG bank (hybrid vector + BM25)."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.interview.bm25 import BM25Index, rrf_fuse
from app.interview.embedding_service import EmbeddingError, OllamaEmbeddingService
from app.interview.rerank import lexical_rerank
from app.models.database import (
    InterviewQuestionEmbedding,
    InterviewQuestionItem,
    InterviewQuestionSource,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetrievedQuestion:
    item_id: str
    question: str
    topic: str
    level: str
    source_url: str | None
    source_title: str | None
    source_section: str | None
    retrieval_score: float
    retrieval_mode: str = "hybrid"
    degraded: bool = False
    degraded_reason: str | None = None
    vector_score: float | None = None
    bm25_score: float | None = None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def build_retrieval_query(
    *,
    role: str | None,
    topic: str,
    level: str,
    focus_node: str | None = None,
) -> str:
    parts = [p for p in [role, topic, level, focus_node] if p]
    return " ".join(parts)


def retrieval_span_dict(q: RetrievedQuestion | None) -> dict | None:
    if q is None:
        return None
    return {
        "mode": q.retrieval_mode,
        "score": q.retrieval_score,
        "vector_score": q.vector_score,
        "bm25_score": q.bm25_score,
        "degraded": q.degraded,
        "degraded_reason": q.degraded_reason,
        "item_id": q.item_id,
        "topic": q.topic,
        "level": q.level,
        "source_section": q.source_section,
    }


class QuestionBankRetrieval:
    def __init__(self, db: AsyncSession, embedder: OllamaEmbeddingService | None = None):
        self.db = db
        self.embedder = embedder or OllamaEmbeddingService()

    async def retrieve(
        self,
        *,
        role: str | None,
        topic: str,
        level: str,
        focus_node: str | None = None,
        exclude_questions: set[str] | None = None,
        prefer_source_url_substr: str | None = None,
        prefer_source_section_substr: str | None = None,
    ) -> RetrievedQuestion | None:
        return await self.retrieve_with_meta(
            role=role,
            topic=topic,
            level=level,
            focus_node=focus_node,
            exclude_questions=exclude_questions,
            prefer_source_url_substr=prefer_source_url_substr,
            prefer_source_section_substr=prefer_source_section_substr,
        )

    async def retrieve_with_meta(
        self,
        *,
        role: str | None,
        topic: str,
        level: str,
        focus_node: str | None = None,
        exclude_questions: set[str] | None = None,
        prefer_source_url_substr: str | None = None,
        prefer_source_section_substr: str | None = None,
    ) -> RetrievedQuestion | None:
        exclude = {q.strip() for q in (exclude_questions or set()) if q and q.strip()}
        query_text = build_retrieval_query(
            role=role, topic=topic, level=level, focus_node=focus_node
        )
        try:
            query_vec = await self.embedder.embed_text(query_text)
        except EmbeddingError as exc:
            reason = "embedding_circuit_open" if "熔断" in str(exc) or "circuit" in str(exc).lower() else "embedding_failed"
            logger.warning("question_bank_retrieval_embed_failed", extra={"error": str(exc), "reason": reason})
            fallback = await self._metadata_fallback(
                topic=topic,
                level=level,
                exclude_questions=exclude,
                prefer_source_url_substr=prefer_source_url_substr,
                prefer_source_section_substr=prefer_source_section_substr,
                degraded_reason=reason,
            )
            return fallback

        stmt = (
            select(InterviewQuestionItem, InterviewQuestionEmbedding, InterviewQuestionSource)
            .join(
                InterviewQuestionEmbedding,
                InterviewQuestionEmbedding.item_id == InterviewQuestionItem.id,
            )
            .join(
                InterviewQuestionSource,
                InterviewQuestionSource.id == InterviewQuestionItem.source_id,
            )
            .where(
                InterviewQuestionItem.is_active.is_(True),
                InterviewQuestionEmbedding.model == self.embedder.model,
            )
        )
        result = await self.db.execute(stmt)
        rows = result.all()
        if not rows:
            return await self._metadata_fallback(
                topic=topic,
                level=level,
                exclude_questions=exclude,
                prefer_source_url_substr=prefer_source_url_substr,
                prefer_source_section_substr=prefer_source_section_substr,
                degraded_reason="empty_embedding_index",
            )

        topic_rows = [
            (item, emb, source)
            for item, emb, source in rows
            if item.topic.lower() == topic.lower()
        ]
        candidate_rows = topic_rows or []
        if prefer_source_url_substr or prefer_source_section_substr:
            preferred = []
            for item, emb, source in candidate_rows or rows:
                url = (source.source_url or "").lower()
                section = (item.source_section or "").lower()
                if prefer_source_url_substr and prefer_source_url_substr.lower() not in url:
                    continue
                if prefer_source_section_substr and prefer_source_section_substr.lower() not in section:
                    continue
                preferred.append((item, emb, source))
            if preferred:
                candidate_rows = preferred
            elif not candidate_rows:
                candidate_rows = preferred
        if not candidate_rows:
            return await self._metadata_fallback(
                topic=topic,
                level=level,
                exclude_questions=exclude,
                prefer_source_url_substr=prefer_source_url_substr,
                prefer_source_section_substr=prefer_source_section_substr,
                degraded_reason="no_topic_candidates",
            )

        by_id: dict[str, tuple[InterviewQuestionItem, InterviewQuestionSource]] = {}
        vector_ranked: list[tuple[str, float]] = []
        bm25 = BM25Index()
        vector_scores: dict[str, float] = {}

        for item, emb, source in candidate_rows:
            if item.normalized_question in exclude:
                continue
            by_id[item.id] = (item, source)
            score = cosine_similarity(query_vec, list(emb.vector or []))
            if item.level == level:
                score += 0.05
            url = (source.source_url or "").lower()
            section = (item.source_section or "").lower()
            if prefer_source_url_substr and prefer_source_url_substr.lower() in url:
                score += 0.08
            if prefer_source_section_substr and prefer_source_section_substr.lower() in section:
                score += 0.12
            vector_scores[item.id] = score
            vector_ranked.append((item.id, score))
            bm25_text = " ".join(
                filter(
                    None,
                    [
                        item.normalized_question,
                        item.topic,
                        item.level,
                        item.source_section or "",
                        " ".join(item.tags or []),
                    ],
                )
            )
            bm25.add_document(item.id, bm25_text)

        if not vector_ranked:
            return await self._metadata_fallback(
                topic=topic,
                level=level,
                exclude_questions=exclude,
                prefer_source_url_substr=prefer_source_url_substr,
                prefer_source_section_substr=prefer_source_section_substr,
                degraded_reason="all_excluded",
            )

        vector_ranked.sort(key=lambda x: x[1], reverse=True)
        bm25_ranked = bm25.search(query_text, top_k=max(settings.INTERVIEW_RAG_TOP_K * 4, 20))
        bm25_scores = {doc_id: score for doc_id, score in bm25_ranked}

        use_hybrid = bool(getattr(settings, "INTERVIEW_RAG_HYBRID", True))
        if use_hybrid and bm25_ranked:
            fused = rrf_fuse(vector_ranked, bm25_ranked, k=60)
            # Blend RRF with vector score for absolute thresholding
            scored: list[tuple[float, str]] = []
            for doc_id, rrf_score in fused:
                v = vector_scores.get(doc_id, 0.0)
                scored.append((rrf_score * 10.0 + v, doc_id))
            scored.sort(key=lambda x: x[0], reverse=True)
            mode = "hybrid"
        else:
            scored = [(s, i) for i, s in vector_ranked]
            scored.sort(key=lambda x: x[0], reverse=True)
            mode = "vector"

        # Optional lexical rerank of top pool (P2 light; no CrossEncoder dependency)
        top_pool = scored[: max(settings.INTERVIEW_RAG_TOP_K * 3, 10)]
        if getattr(settings, "INTERVIEW_RERANK_MODE", "lexical") == "lexical" and top_pool:
            docs = []
            for score, doc_id in top_pool:
                item, _source = by_id[doc_id]
                docs.append((doc_id, item.normalized_question, score))
            reranked = lexical_rerank(query_text, docs, topic=topic, level=level)
            top_pool = [(s, i) for i, s in reranked]
            mode = f"{mode}+lexical"

        viable = [
            (score, doc_id)
            for score, doc_id in top_pool
            if vector_scores.get(doc_id, 0.0) >= settings.INTERVIEW_RAG_MIN_SCORE
            or (use_hybrid and bm25_scores.get(doc_id, 0.0) > 0)
        ]
        # Prefer items that pass vector threshold; else keep fused order
        pick_from = viable[: max(settings.INTERVIEW_RAG_TOP_K, 5)] or top_pool[:1]
        if not pick_from:
            return await self._metadata_fallback(
                topic=topic,
                level=level,
                exclude_questions=exclude,
                prefer_source_url_substr=prefer_source_url_substr,
                prefer_source_section_substr=prefer_source_section_substr,
                degraded_reason="low_score",
            )

        best_score, best_id = pick_from[0]
        # Guard: if best vector is far below min and no bm25, fall back
        if (
            vector_scores.get(best_id, 0.0) < settings.INTERVIEW_RAG_MIN_SCORE
            and bm25_scores.get(best_id, 0.0) <= 0
        ):
            fallback = await self._metadata_fallback(
                topic=topic,
                level=level,
                exclude_questions=exclude,
                prefer_source_url_substr=prefer_source_url_substr,
                prefer_source_section_substr=prefer_source_section_substr,
                degraded_reason="low_score",
            )
            if fallback:
                return fallback
            return None

        best_item, best_source = by_id[best_id]
        return RetrievedQuestion(
            item_id=best_item.id,
            question=best_item.normalized_question,
            topic=best_item.topic,
            level=best_item.level,
            source_url=best_source.source_url,
            source_title=best_source.title,
            source_section=best_item.source_section,
            retrieval_score=round(float(best_score), 4),
            retrieval_mode=mode,
            degraded=False,
            degraded_reason=None,
            vector_score=round(vector_scores.get(best_id, 0.0), 4),
            bm25_score=round(bm25_scores.get(best_id, 0.0), 4) if best_id in bm25_scores else None,
        )

    async def _metadata_fallback(
        self,
        *,
        topic: str,
        level: str,
        exclude_questions: set[str] | None = None,
        prefer_source_url_substr: str | None = None,
        prefer_source_section_substr: str | None = None,
        degraded_reason: str = "metadata_fallback",
    ) -> RetrievedQuestion | None:
        exclude = {q.strip() for q in (exclude_questions or set()) if q and q.strip()}
        stmt = (
            select(InterviewQuestionItem, InterviewQuestionSource)
            .join(
                InterviewQuestionSource,
                InterviewQuestionSource.id == InterviewQuestionItem.source_id,
            )
            .where(
                InterviewQuestionItem.is_active.is_(True),
                InterviewQuestionItem.topic == topic,
            )
            .order_by(
                (InterviewQuestionItem.level == level).desc(),
                InterviewQuestionItem.created_at.desc(),
            )
            .limit(40)
        )
        result = await self.db.execute(stmt)
        rows = result.all()
        preferred: list[tuple] = []
        general: list[tuple] = []
        for item, source in rows:
            if item.normalized_question in exclude:
                continue
            url = (source.source_url or "").lower()
            section = (item.source_section or "").lower()
            hit_url = (
                not prefer_source_url_substr
                or prefer_source_url_substr.lower() in url
            )
            hit_sec = (
                not prefer_source_section_substr
                or prefer_source_section_substr.lower() in section
            )
            if hit_url and hit_sec and (prefer_source_url_substr or prefer_source_section_substr):
                preferred.append((item, source))
            else:
                general.append((item, source))
        pick = preferred or general
        if not pick:
            return None
        item, source = pick[0]
        return RetrievedQuestion(
            item_id=item.id,
            question=item.normalized_question,
            topic=item.topic,
            level=item.level,
            source_url=source.source_url,
            source_title=source.title,
            source_section=item.source_section,
            retrieval_score=0.0,
            retrieval_mode="metadata_fallback",
            degraded=True,
            degraded_reason=degraded_reason,
            vector_score=None,
            bm25_score=None,
        )
