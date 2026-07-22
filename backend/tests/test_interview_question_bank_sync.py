"""Tests for real sync of the interview question bank (re-import)."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import delete, select

from app.db.database import async_session_factory
from app.interview.question_bank_ingest import ParsedQuestion
from app.interview.question_bank_sync import sync_question_bank
from app.models.database import (
    InterviewQuestionEmbedding,
    InterviewQuestionItem,
    InterviewQuestionSource,
)


class FakeEmbedder:
    def __init__(self, model: str = "fake-sync-embed"):
        self.model = model

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[float(i + 1), 0.0, 0.0] for i, _ in enumerate(texts)]

    async def embed_text(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]


def _pq(stem: str, *, section: str = "sec", topic: str = "RAG", marker: str = "") -> ParsedQuestion:
    # content_hash must be unique per stem+section like production
    import hashlib

    section_key = f"{section}:{marker}" if marker else section
    h = hashlib.sha256(f"{section_key}|{stem}".lower().encode()).hexdigest()
    return ParsedQuestion(
        raw_question=stem,
        normalized_question=stem,
        topic=topic,
        level="P6",
        source_section=section_key,
        tags=[topic],
        content_hash=h,
    )


@pytest.mark.asyncio
async def test_sync_skips_when_document_hash_unchanged():
    marker = f"sync-skip-{uuid.uuid4().hex}"
    url = f"https://example.com/{marker}"
    doc_hash = f"doc-{marker}"

    async with async_session_factory() as db:
        try:
            source = InterviewQuestionSource(
                source_url=url,
                title="t",
                content_hash=doc_hash,
                synced_at=datetime.now(timezone.utc),
            )
            db.add(source)
            await db.flush()
            item = InterviewQuestionItem(
                source_id=source.id,
                raw_question="Q keep",
                normalized_question="Q keep",
                topic="RAG",
                level="P6",
                source_section="sec",
                tags=["RAG"],
                content_hash=f"{marker}-keep",
                is_active=True,
            )
            db.add(item)
            await db.commit()

            result = await sync_question_bank(
                db,
                source_url=url,
                title="t",
                document_hash=doc_hash,
                items=[_pq("Q new should not insert", marker=marker)],
                embedder=FakeEmbedder(),
            )
            await db.commit()

            assert result.skipped is True
            assert result.added == 0
            rows = list(
                (
                    await db.execute(
                        select(InterviewQuestionItem).where(
                            InterviewQuestionItem.source_id == source.id
                        )
                    )
                ).scalars()
            )
            assert len(rows) == 1
            assert rows[0].normalized_question == "Q keep"
        finally:
            await db.execute(delete(InterviewQuestionSource).where(InterviewQuestionSource.source_url == url))
            await db.commit()


@pytest.mark.asyncio
async def test_sync_adds_new_deactivates_removed_and_reactivates():
    marker = f"sync-diff-{uuid.uuid4().hex}"
    url = f"https://example.com/{marker}"

    q_keep = _pq("Q keep me", marker=marker)
    q_gone = _pq("Q will be removed", marker=marker)
    q_back = _pq("Q comes back", marker=marker)
    q_new = _pq("Q brand new", marker=marker)

    async with async_session_factory() as db:
        try:
            source = InterviewQuestionSource(
                source_url=url,
                title="t",
                content_hash=f"old-{marker}",
                synced_at=datetime.now(timezone.utc),
            )
            db.add(source)
            await db.flush()

            keep = InterviewQuestionItem(
                source_id=source.id,
                raw_question=q_keep.raw_question,
                normalized_question=q_keep.normalized_question,
                topic=q_keep.topic,
                level=q_keep.level,
                source_section=q_keep.source_section,
                tags=q_keep.tags,
                content_hash=q_keep.content_hash,
                is_active=True,
            )
            gone = InterviewQuestionItem(
                source_id=source.id,
                raw_question=q_gone.raw_question,
                normalized_question=q_gone.normalized_question,
                topic=q_gone.topic,
                level=q_gone.level,
                source_section=q_gone.source_section,
                tags=q_gone.tags,
                content_hash=q_gone.content_hash,
                is_active=True,
            )
            inactive = InterviewQuestionItem(
                source_id=source.id,
                raw_question=q_back.raw_question,
                normalized_question=q_back.normalized_question,
                topic=q_back.topic,
                level=q_back.level,
                source_section=q_back.source_section,
                tags=q_back.tags,
                content_hash=q_back.content_hash,
                is_active=False,
            )
            db.add_all([keep, gone, inactive])
            await db.commit()

            result = await sync_question_bank(
                db,
                source_url=url,
                title="t2",
                document_hash=f"new-{marker}",
                items=[q_keep, q_back, q_new],
                embedder=FakeEmbedder(),
            )
            await db.commit()

            assert result.skipped is False
            assert result.added == 1
            assert result.deactivated == 1
            assert result.reactivated == 1

            by_hash = {
                it.content_hash: it
                for it in (
                    await db.execute(
                        select(InterviewQuestionItem).where(
                            InterviewQuestionItem.source_id == source.id
                        )
                    )
                ).scalars()
            }
            assert by_hash[q_keep.content_hash].is_active is True
            assert by_hash[q_gone.content_hash].is_active is False
            assert by_hash[q_back.content_hash].is_active is True
            assert by_hash[q_new.content_hash].is_active is True
            assert by_hash[q_new.content_hash].normalized_question == "Q brand new"

            emb = (
                await db.execute(
                    select(InterviewQuestionEmbedding).where(
                        InterviewQuestionEmbedding.item_id == by_hash[q_new.content_hash].id
                    )
                )
            ).scalar_one_or_none()
            assert emb is not None
            assert emb.model == "fake-sync-embed"

            src = (
                await db.execute(
                    select(InterviewQuestionSource).where(InterviewQuestionSource.source_url == url)
                )
            ).scalar_one()
            assert src.content_hash == f"new-{marker}"
            assert src.title == "t2"
        finally:
            await db.execute(delete(InterviewQuestionSource).where(InterviewQuestionSource.source_url == url))
            await db.commit()


@pytest.mark.asyncio
async def test_sync_force_reruns_even_when_hash_matches():
    marker = f"sync-force-{uuid.uuid4().hex}"
    url = f"https://example.com/{marker}"
    doc_hash = f"doc-{marker}"
    q_only = _pq("Q only", marker=marker)

    async with async_session_factory() as db:
        try:
            source = InterviewQuestionSource(
                source_url=url,
                title="t",
                content_hash=doc_hash,
                synced_at=datetime.now(timezone.utc),
            )
            db.add(source)
            await db.flush()
            db.add(
                InterviewQuestionItem(
                    source_id=source.id,
                    raw_question="Q stale",
                    normalized_question="Q stale",
                    topic="RAG",
                    level="P6",
                    source_section="sec",
                    tags=["RAG"],
                    content_hash=f"{marker}-stale",
                    is_active=True,
                )
            )
            await db.commit()

            result = await sync_question_bank(
                db,
                source_url=url,
                title="t",
                document_hash=doc_hash,
                items=[q_only],
                embedder=FakeEmbedder(),
                force=True,
            )
            await db.commit()

            assert result.skipped is False
            assert result.deactivated == 1
            assert result.added == 1
        finally:
            await db.execute(delete(InterviewQuestionSource).where(InterviewQuestionSource.source_url == url))
            await db.commit()
