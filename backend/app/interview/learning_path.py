"""Map guide 6-stage learning path → existing interview topics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LearningStage:
    id: str
    title: str
    goal: str
    topics: tuple[str, ...]
    comic: str | None
    days_hint: str


# Aligned with ai-agent-interview-guide docs/00-学习路线图 (compressed onto our topics).
LEARNING_STAGES: tuple[LearningStage, ...] = (
    LearningStage(
        id="s1_llm_prompt",
        title="大模型与 Prompt",
        goal="Transformer / Token 直觉 + 结构化提示、Few-shot、CoT",
        topics=("LLM",),
        comic="01-什么是Agent.png",
        days_hint="约 60～80 天",
    ),
    LearningStage(
        id="s2_rag",
        title="RAG 技术",
        goal="分块、检索、重排与幻觉治理能串成一条链路",
        topics=("RAG",),
        comic="03-RAG流程.png",
        days_hint="约 30～40 天",
    ),
    LearningStage(
        id="s3_agent_tools",
        title="Agent 框架与工具",
        goal="ReAct / LangGraph / Tool calling / MCP 能讲清取舍",
        topics=("Agent", "LangGraph"),
        comic="02-ReAct循环.png",
        days_hint="约 35～45 天",
    ),
    LearningStage(
        id="s4_memory_multi",
        title="记忆与多智能体",
        goal="短长期记忆设计；多 Agent 协作可结合 Agent 主题巩固",
        topics=("Memory",),
        comic="05-记忆系统.png",
        days_hint="约 30～40 天",
    ),
    LearningStage(
        id="s5_engineering",
        title="工程化与项目表达",
        goal="可观测、熔断降级、成本；项目题能走到取舍与证据",
        topics=("可观测性", "Agent 评测"),
        comic="06-面试场景.png",
        days_hint="约 40～50 天",
    ),
)

TOPIC_COMIC: dict[str, str] = {
    "LLM": "01-什么是Agent.png",
    "Agent": "01-什么是Agent.png",
    "LangGraph": "02-ReAct循环.png",
    "RAG": "03-RAG流程.png",
    "Memory": "05-记忆系统.png",
    "可观测性": "06-面试场景.png",
    "Agent 评测": "04-多Agent协作.png",
}

COMIC_PUBLIC_PREFIX = "/interview/comics/"


def comic_url_for_topic(topic: str | None) -> str | None:
    if not topic:
        return None
    name = TOPIC_COMIC.get(topic) or TOPIC_COMIC.get(topic.strip())
    if not name:
        for key, filename in TOPIC_COMIC.items():
            if key.lower() in topic.lower() or topic.lower() in key.lower():
                name = filename
                break
    if not name:
        return None
    return f"{COMIC_PUBLIC_PREFIX}{name}"


def _stage_covered(stage: LearningStage, committed_topics: set[str]) -> bool:
    """A stage is covered when at least one of its topics has a committed attempt."""
    committed_l = {t.lower() for t in committed_topics}
    return any(t.lower() in committed_l for t in stage.topics)


def recommend_learning_path(
    *,
    committed_topics: set[str],
    role_topics: list[str] | None = None,
) -> dict[str, Any]:
    """
    Recommend the first incomplete stage as next_module.
    Stages whose topics are entirely outside the role bank stay listed but
    are skipped for "next" when role_topics is provided.
    """
    role_set = {t.lower() for t in (role_topics or [])} if role_topics else None
    stages_out: list[dict[str, Any]] = []
    next_module: dict[str, Any] | None = None

    for stage in LEARNING_STAGES:
        done = _stage_covered(stage, committed_topics)
        relevant = True
        if role_set is not None:
            relevant = any(t.lower() in role_set for t in stage.topics) or not role_set
        primary_topic = stage.topics[0]
        for t in stage.topics:
            if role_set is None or t.lower() in role_set:
                primary_topic = t
                break
        row = {
            "id": stage.id,
            "title": stage.title,
            "goal": stage.goal,
            "topics": list(stage.topics),
            "primary_topic": primary_topic,
            "comic_url": f"{COMIC_PUBLIC_PREFIX}{stage.comic}" if stage.comic else None,
            "days_hint": stage.days_hint,
            "done": done,
            "relevant": relevant,
        }
        stages_out.append(row)
        if next_module is None and relevant and not done:
            next_module = {
                "stage_id": stage.id,
                "title": stage.title,
                "topic": primary_topic,
                "goal": stage.goal,
                "comic_url": row["comic_url"],
                "reason": f"阶段「{stage.title}」尚未完成闭环，建议先练「{primary_topic}」",
            }

    if next_module is None:
        next_module = {
            "stage_id": None,
            "title": "巩固与拓宽",
            "topic": (role_topics[0] if role_topics else "Agent"),
            "goal": "路线阶段已基本覆盖，可复习卡或换项目模拟加深证据",
            "comic_url": f"{COMIC_PUBLIC_PREFIX}06-面试场景.png",
            "reason": "学习路线相关主题均已有闭环，保持复习或开「项目模拟」",
        }

    done_count = sum(1 for s in stages_out if s["done"] and s["relevant"])
    relevant_count = sum(1 for s in stages_out if s["relevant"]) or 1
    return {
        "stages": stages_out,
        "next_module": next_module,
        "done_count": done_count,
        "total_relevant": relevant_count,
    }
