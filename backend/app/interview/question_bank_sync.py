"""Incremental sync for the interview question bank (re-import)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.interview.embedding_service import EmbeddingError
from app.interview.question_bank_ingest import ParsedQuestion
from app.models.database import (
    InterviewQuestionEmbedding,
    InterviewQuestionItem,
    InterviewQuestionSource,
)

logger = logging.getLogger(__name__)


class Embedder(Protocol):
    model: str

    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class SyncResult:
    skipped: bool
    added: int = 0
    reactivated: int = 0
    deactivated: int = 0
    unchanged: int = 0
    embedded: int = 0


async def sync_question_bank(
    db: AsyncSession,
    *,
    source_url: str,
    title: str | None,
    document_hash: str,
    items: list[ParsedQuestion],
    embedder: Embedder | None = None,
    force: bool = False,
    skip_embedding: bool = False,
) -> SyncResult:
    """
    Sync a document's extracted questions into the bank.

    - If document_hash matches the stored source and force is False → no-op skip.
    - Questions present in extract → insert or reactivate (+ refresh metadata).
    - Questions absent from extract for this source → soft-delete (is_active=False).
    - New stems get embeddings when embedder is provided and skip_embedding is False.
    """
    result = await db.execute(
        select(InterviewQuestionSource).where(InterviewQuestionSource.source_url == source_url)
    )
    source = result.scalar_one_or_none()

    if source is not None and source.content_hash == document_hash and not force:
        logger.info("question_bank_sync_skipped", extra={"source_url": source_url})
        return SyncResult(skipped=True)

    now = datetime.now(timezone.utc)
    if source is None:
        source = InterviewQuestionSource(
            source_url=source_url,
            title=title,
            content_hash=document_hash,
            synced_at=now,
        )
        db.add(source)
        await db.flush()
    else:
        source.title = title
        source.content_hash = document_hash
        source.synced_at = now

    extracted_hashes = {q.content_hash for q in items}

    existing_rows = list(
        (
            await db.execute(
                select(InterviewQuestionItem).where(InterviewQuestionItem.source_id == source.id)
            )
        ).scalars()
    )

    deactivated = 0
    for row in existing_rows:
        if row.content_hash not in extracted_hashes and row.is_active:
            row.is_active = False
            deactivated += 1

    # Also look up by content_hash globally (unique constraint) for upsert.
    by_hash: dict[str, InterviewQuestionItem] = {}
    if extracted_hashes:
        found = list(
            (
                await db.execute(
                    select(InterviewQuestionItem).where(
                        InterviewQuestionItem.content_hash.in_(extracted_hashes)
                    )
                )
            ).scalars()
        )
        by_hash = {it.content_hash: it for it in found}

    added = 0
    reactivated = 0
    unchanged = 0
    new_items: list[InterviewQuestionItem] = []

    for q in items:
        existing = by_hash.get(q.content_hash)
        if existing is None:
            item = InterviewQuestionItem(
                source_id=source.id,
                raw_question=q.raw_question,
                normalized_question=q.normalized_question,
                topic=q.topic,
                level=q.level,
                source_section=q.source_section,
                tags=q.tags,
                content_hash=q.content_hash,
                is_active=True,
            )
            db.add(item)
            await db.flush()
            by_hash[q.content_hash] = item
            new_items.append(item)
            added += 1
            continue

        existing.source_id = source.id
        existing.raw_question = q.raw_question
        existing.normalized_question = q.normalized_question
        existing.topic = q.topic
        existing.level = q.level
        existing.source_section = q.source_section
        existing.tags = q.tags
        if not existing.is_active:
            existing.is_active = True
            reactivated += 1
        else:
            unchanged += 1

    embedded = 0
    if new_items and not skip_embedding and embedder is not None:
        try:
            vectors = await embedder.embed_texts([it.normalized_question for it in new_items])
            if len(vectors) != len(new_items):
                raise EmbeddingError("embedding count mismatch")
            model = embedder.model
            for item, vec in zip(new_items, vectors):
                emb_row = (
                    await db.execute(
                        select(InterviewQuestionEmbedding).where(
                            InterviewQuestionEmbedding.item_id == item.id,
                            InterviewQuestionEmbedding.model == model,
                        )
                    )
                ).scalar_one_or_none()
                if emb_row is None:
                    db.add(
                        InterviewQuestionEmbedding(
                            item_id=item.id,
                            model=model,
                            dimension=len(vec),
                            vector=vec,
                            content_hash=item.content_hash,
                        )
                    )
                else:
                    emb_row.dimension = len(vec)
                    emb_row.vector = vec
                    emb_row.content_hash = item.content_hash
                embedded += 1
        except EmbeddingError as exc:
            logger.warning("question_bank_sync_embed_failed", extra={"error": str(exc)})

    logger.info(
        "question_bank_sync_done",
        extra={
            "source_url": source_url,
            "added": added,
            "reactivated": reactivated,
            "deactivated": deactivated,
            "unchanged": unchanged,
            "embedded": embedded,
        },
    )
    return SyncResult(
        skipped=False,
        added=added,
        reactivated=reactivated,
        deactivated=deactivated,
        unchanged=unchanged,
        embedded=embedded,
    )
