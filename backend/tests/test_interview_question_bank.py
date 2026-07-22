import math

import pytest
from sqlalchemy import delete, select

from datetime import datetime, timezone
import uuid

from app.db.database import async_session_factory
from app.interview.question_bank_ingest import extract_questions_from_markdown
from app.interview.question_bank_retrieval import QuestionBankRetrieval
from app.models.database import (
    InterviewQuestionEmbedding,
    InterviewQuestionItem,
    InterviewQuestionSource,
)


class FakeEmbedder:
    def __init__(self, model: str, vec: list[float]):
        self.model = model
        self._vec = vec

    async def embed_text(self, text: str) -> list[float]:
        return list(self._vec)


def test_extract_questions_basic():
    md = """
# AI应用开发面试题 / Agent / RAG

## 上下文管理与记忆

### 如何设计一个高效的 Agent 上下文维护方案？

内容已经分类

### 什么时候适合用 Workflow，什么情况下适合用 Agent？

---
"""
    items = extract_questions_from_markdown(md)
    assert len(items) >= 2
    stems = {it.normalized_question for it in items}
    assert any("高效的 Agent" in s for s in stems)
    assert any("Workflow" in s or "Workflow" in s for s in stems)


def test_extract_numbered_stems_without_question_mark():
    md = """
# AI大模型高频面试题大集合

## 1-请说明AI大模型应用开发和底层区别，市场需求占比。

正文答案略

## 21- Python类型增强模块Typing在AI项目中的应用

正文

## 71-AI大模型在智能搜索系统中的架构设计与优化要点

## 简介

不是题目
"""
    items = extract_questions_from_markdown(md)
    stems = [it.normalized_question for it in items]
    assert len(items) == 3
    assert any("请说明AI大模型应用开发" in s for s in stems)
    assert any("Typing" in s for s in stems)
    assert any("智能搜索系统" in s for s in stems)
    # numbering prefix should be stripped for cleaner stems
    assert not any(s.startswith("1-") or s.startswith("21-") for s in stems)


def test_extract_stem_headings_without_question_mark():
    md = """
# 面经汇总

## Agent

### MCP 和 Function Calling 的区别

### 谈谈你对 DDD 的理解

### ARP 是什么

### 如何看 data+ai，例如在金融行业智能 Agent 检测到风险时实时邮件通知等应用场景

### 请详细说明微信扫码登录的完整流程和背后发生的原理

### 介绍一些 AI 大模型

## 网络

### 核心区别

### 对比总结表

### 第五步：发送 HTTP 请求

### GET vs POST 深度对比
"""
    items = extract_questions_from_markdown(md)
    stems = {it.normalized_question for it in items}
    assert "MCP 和 Function Calling 的区别" in stems
    assert "谈谈你对 DDD 的理解" in stems
    assert "ARP 是什么" in stems
    assert any("如何看 data+ai" in s for s in stems)
    assert any("微信扫码登录" in s for s in stems)
    assert "介绍一些 AI 大模型" in stems
    # structural section labels must not become questions
    assert "核心区别" not in stems
    assert "对比总结表" not in stems
    assert "第五步：发送 HTTP 请求" not in stems
    assert "GET vs POST 深度对比" not in stems



def test_infer_topic_react_vs_react_agent():
    from app.interview.question_bank_ingest import _infer_topic

    assert _infer_topic("Agent 范式", "请说明 ReAct 模式的优缺点？") == "Agent"
    assert _infer_topic("前端工程", "React hooks 的依赖数组怎么设计？") == "React"
    assert _infer_topic("编码绕过", "前端安全：如何防范 Prompt Injection 攻击？") != "React"
    assert _infer_topic("RAG 实践", "向量数据库如何做召回与重排？") == "RAG"
    assert _infer_topic("并发", "什么是协程，它和线程有什么区别？") == "Python"
    assert _infer_topic("基础", "Python 中的 GIL 锁？") == "Python"


def test_pick_topic_skips_excluded():
    from app.interview.training import pick_topic_from_bank

    assert pick_topic_from_bank(["RAG", "Agent", "Memory"], exclude={"RAG"}) == "Agent"
    assert pick_topic_from_bank(["RAG"], exclude={"RAG"}) == "RAG"


@pytest.mark.asyncio
async def test_question_bank_retrieval_prefers_topic_and_level():
    async with async_session_factory() as db:
        marker = f"test-rag-pref-topic-{uuid.uuid4().hex}"
        source_url = f"https://example.com/{marker}"
        try:
            await db.execute(
                delete(InterviewQuestionSource).where(
                    InterviewQuestionSource.source_url == source_url
                )
            )

            source = InterviewQuestionSource(
                source_url=source_url,
                title="t",
                content_hash=f"src-{marker}",
                synced_at=datetime.now(timezone.utc),
            )
            db.add(source)
            await db.flush()

            model = "fake-embed"
            vec = [1.0, 0.0, 0.0]
            item_topic = "RAG"
            item_level = "P6"

            item1 = InterviewQuestionItem(
                source_id=source.id,
                raw_question="raw1",
                normalized_question="Q1 RAG P6",
                topic=item_topic,
                level=item_level,
                source_section="sec",
                tags=["RAG"],
                content_hash=f"{marker}-q1",
                is_active=True,
            )
            item2 = InterviewQuestionItem(
                source_id=source.id,
                raw_question="raw2",
                normalized_question="Q2 Agent P6",
                topic="Agent",
                level=item_level,
                source_section="sec",
                tags=["Agent"],
                content_hash=f"{marker}-q2",
                is_active=True,
            )
            db.add_all([item1, item2])
            await db.flush()

            db.add_all(
                [
                    InterviewQuestionEmbedding(
                        item_id=item1.id,
                        model=model,
                        dimension=len(vec),
                        vector=vec,
                        content_hash=item1.content_hash,
                    ),
                    InterviewQuestionEmbedding(
                        item_id=item2.id,
                        model=model,
                        dimension=len(vec),
                        vector=vec,
                        content_hash=item2.content_hash,
                    ),
                ]
            )
            await db.commit()

            retriever = QuestionBankRetrieval(db, embedder=FakeEmbedder(model=model, vec=vec))
            got = await retriever.retrieve(
                role="AI 应用工程", topic=item_topic, level=item_level, focus_node="Trade-off"
            )
            assert got is not None
            assert got.question == "Q1 RAG P6"
        finally:
            await db.execute(
                delete(InterviewQuestionSource).where(
                    InterviewQuestionSource.source_url == source_url
                )
            )
            await db.commit()


@pytest.mark.asyncio
async def test_question_bank_retrieval_excludes_current_question():
    async with async_session_factory() as db:
        marker = f"test-rag-exclude-{uuid.uuid4().hex}"
        source_url = f"https://example.com/{marker}"
        try:
            source = InterviewQuestionSource(
                source_url=source_url,
                title="t",
                content_hash=f"src-{marker}",
                synced_at=datetime.now(timezone.utc),
            )
            db.add(source)
            await db.flush()
            model = "fake-embed-excl"
            vec = [1.0, 0.0, 0.0]
            q1 = InterviewQuestionItem(
                source_id=source.id,
                raw_question="raw1",
                normalized_question="Exclude me",
                topic="RAG",
                level="P6",
                source_section="sec",
                tags=["RAG"],
                content_hash=f"{marker}-q1",
                is_active=True,
            )
            q2 = InterviewQuestionItem(
                source_id=source.id,
                raw_question="raw2",
                normalized_question="Keep me",
                topic="RAG",
                level="P6",
                source_section="sec",
                tags=["RAG"],
                content_hash=f"{marker}-q2",
                is_active=True,
            )
            db.add_all([q1, q2])
            await db.flush()
            db.add_all(
                [
                    InterviewQuestionEmbedding(
                        item_id=q1.id,
                        model=model,
                        dimension=3,
                        vector=vec,
                        content_hash=q1.content_hash,
                    ),
                    InterviewQuestionEmbedding(
                        item_id=q2.id,
                        model=model,
                        dimension=3,
                        vector=vec,
                        content_hash=q2.content_hash,
                    ),
                ]
            )
            await db.commit()

            retriever = QuestionBankRetrieval(db, embedder=FakeEmbedder(model=model, vec=vec))
            got = await retriever.retrieve(
                role=None,
                topic="RAG",
                level="P6",
                exclude_questions={"Exclude me"},
            )
            assert got is not None
            assert got.question == "Keep me"
        finally:
            await db.execute(
                delete(InterviewQuestionSource).where(
                    InterviewQuestionSource.source_url == source_url
                )
            )
            await db.commit()


@pytest.mark.asyncio
async def test_question_bank_retrieval_fallback_when_score_too_low():
    async with async_session_factory() as db:
        marker = f"test-rag-fallback-low-{uuid.uuid4().hex}"
        source_url = f"https://example.com/{marker}"
        try:
            await db.execute(
                delete(InterviewQuestionSource).where(
                    InterviewQuestionSource.source_url == source_url
                )
            )

            source = InterviewQuestionSource(
                source_url=source_url,
                title="t",
                content_hash=f"src-{marker}",
                synced_at=datetime.now(timezone.utc),
            )
            db.add(source)
            await db.flush()

            model = "fake-embed-2"
            item_topic = "RAG"
            item_level = "P6"
            item = InterviewQuestionItem(
                source_id=source.id,
                raw_question="raw",
                normalized_question="Q-fallback",
                topic=item_topic,
                level=item_level,
                source_section="sec",
                tags=["RAG"],
                content_hash=f"{marker}-q",
                is_active=True,
            )
            db.add(item)
            await db.flush()
            # orthogonal so cosine=0 => score=0.13 < min_score
            db.add(
                InterviewQuestionEmbedding(
                    item_id=item.id,
                    model=model,
                    dimension=3,
                    vector=[0.0, 1.0, 0.0],
                    content_hash=item.content_hash,
                )
            )
            await db.commit()

            retriever = QuestionBankRetrieval(
                db, embedder=FakeEmbedder(model=model, vec=[1.0, 0.0, 0.0])
            )
            got = await retriever.retrieve(
                role=None, topic=item_topic, level=item_level, focus_node=None
            )
            assert got is not None
            assert got.question == "Q-fallback"
        finally:
            await db.execute(
                delete(InterviewQuestionSource).where(
                    InterviewQuestionSource.source_url == source_url
                )
            )
            await db.commit()

