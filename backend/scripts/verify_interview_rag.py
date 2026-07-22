"""Ad-hoc verification for interview RAG retrieval + prompt integration."""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import func, select

from app.config import settings
from app.db.database import async_session_factory
from app.interview.question_bank_retrieval import QuestionBankRetrieval
from app.interview.schemas import InterviewProfileUpdate
from app.interview.services import InterviewService
from app.models.database import InterviewQuestionEmbedding, User


async def main() -> None:
    async with async_session_factory() as db:
        emb_count = (
            await db.execute(select(func.count()).select_from(InterviewQuestionEmbedding))
        ).scalar()
        print("embeddings=", emb_count)
        print(
            "model=",
            settings.INTERVIEW_EMBEDDING_MODEL,
            "min_score=",
            settings.INTERVIEW_RAG_MIN_SCORE,
        )

        retriever = QuestionBankRetrieval(db)
        cases = [
            ("AI 应用工程", "RAG", "P6", "Trade-off"),
            ("AI 应用工程", "Agent", "P5", "Position"),
            ("AI 应用工程", "Memory", "P6", "Trade-off"),
            ("全栈", "SSE", "P6", "Trade-off"),
            ("前端", "React", "P6", "Trade-off"),
            ("后端", "UnknownTopicXYZ", "P6", "Trade-off"),
        ]
        print("\n=== retrieval ===")
        for role, topic, level, focus in cases:
            hit = await retriever.retrieve(
                role=role, topic=topic, level=level, focus_node=focus
            )
            if hit is None:
                print(f"[{topic}/{level}] MISS")
            else:
                print(
                    f"[{topic}/{level}] score={hit.retrieval_score:.4f} "
                    f"hit_topic={hit.topic} hit_level={hit.level}"
                )
                print(f"  Q: {hit.question}")
                print(f"  section: {hit.source_section}")
                print(f"  url: {hit.source_url}")

        print("\n=== next_training_prompt ===")
        user_id = uuid.uuid4()
        db.add(
            User(
                id=str(user_id),
                email=f"v{user_id.hex[:8]}@t.com",
                username=f"v{user_id.hex[:8]}",
                hashed_password="x",
                is_active=True,
            )
        )
        await db.commit()

        svc = InterviewService(db)
        await svc.update_profile(
            user_id,
            InterviewProfileUpdate(
                target_role="AI 应用工程",
                target_level="中级",
                salary_band="40-60k",
            ),
        )

        for topic in ("RAG", "Agent", "Memory", "SSE"):
            prompt = await svc.next_training_prompt(user_id, level="P6", topic=topic)
            src = prompt.question_source
            print(f"\n[{topic}] focus={prompt.focus_node}")
            print(f"  Q: {prompt.question}")
            print(f"  source: {src}")


if __name__ == "__main__":
    asyncio.run(main())
