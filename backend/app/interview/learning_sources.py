"""Reference catalog: Feishu handbooks + GitHub ai-agent-interview-guide."""

from __future__ import annotations

from dataclasses import dataclass

GITHUB_GUIDE_REPO = "https://github.com/bcefghj/ai-agent-interview-guide"
GITHUB_GUIDE_TREE = f"{GITHUB_GUIDE_REPO}/tree/main"


@dataclass(frozen=True)
class HandbookRef:
    title: str
    url: str
    topics: tuple[str, ...]


# Passwords are not stored in repo; users access Feishu docs with shared credentials.
HANDBOOKS: tuple[HandbookRef, ...] = (
    HandbookRef(
        "RAG 手册",
        "https://dqej47nflyz.feishu.cn/wiki/Xum4w0ksBiwgRTkFKeec2MYwnOp",
        ("RAG",),
    ),
    HandbookRef(
        "Agent 手册",
        "https://dqej47nflyz.feishu.cn/wiki/CkzZwmDPbiUvP5kVyiIcVQepnEf",
        ("Agent", "Memory", "LangGraph"),
    ),
    HandbookRef(
        "Transformer 手册",
        "https://dqej47nflyz.feishu.cn/wiki/UVG4wY8JxiIgnyka6dsc3xDanid",
        ("LLM",),
    ),
    HandbookRef(
        "LangChain 手册",
        "https://dqej47nflyz.feishu.cn/wiki/R3eXw8aXeiQqXxkYSrOcPHeznK6",
        ("Agent", "LangGraph"),
    ),
    HandbookRef(
        "LangGraph 手册",
        "https://dqej47nflyz.feishu.cn/wiki/CIPqwL3XkimM4Qk73ylc2RZMnrg",
        ("LangGraph", "Agent"),
    ),
    HandbookRef(
        "AI Harness 万字详解",
        "https://dqej47nflyz.feishu.cn/wiki/JxIcwQGKEiJKDnkjMmWcF3dAngd",
        ("Agent", "可观测性", "Agent 评测"),
    ),
)

STAGE_GITHUB_FILES: dict[str, tuple[str, ...]] = {
    "s1_llm_prompt": ("docs/07-大模型基础.md", "docs/09-Prompt工程.md", "docs/00-学习路线图.md"),
    "s2_rag": ("docs/03-RAG技术.md", "docs/00-学习路线图.md"),
    "s3_agent_tools": (
        "docs/01-基础概念.md",
        "docs/02-核心框架.md",
        "docs/04-工具调用.md",
        "docs/00-学习路线图.md",
    ),
    "s4_memory_multi": ("docs/05-记忆系统.md", "docs/06-多智能体.md"),
    "s5_engineering": ("docs/08-工程化实践.md", "docs/06-多智能体.md", "docs/06-面试场景.png"),
}

TOPIC_GITHUB_FILES: dict[str, tuple[str, ...]] = {
    "LLM": ("docs/07-大模型基础.md", "docs/09-Prompt工程.md"),
    "RAG": ("docs/03-RAG技术.md",),
    "Agent": ("docs/01-基础概念.md", "docs/02-核心框架.md", "docs/04-工具调用.md"),
    "LangGraph": ("docs/02-核心框架.md",),
    "Memory": ("docs/05-记忆系统.md",),
    "可观测性": ("docs/08-工程化实践.md",),
    "Agent 评测": ("docs/08-工程化实践.md",),
}


def handbooks_for_topic(topic: str) -> list[HandbookRef]:
    t = topic.lower()
    return [h for h in HANDBOOKS if any(x.lower() == t or t in x.lower() for x in h.topics)]


def github_files_for(stage_id: str | None, topic: str) -> list[str]:
    files: list[str] = []
    if stage_id and stage_id in STAGE_GITHUB_FILES:
        files.extend(STAGE_GITHUB_FILES[stage_id])
    files.extend(TOPIC_GITHUB_FILES.get(topic, ()))
    seen: set[str] = set()
    out: list[str] = []
    for f in files:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def format_source_links(stage_id: str | None, topic: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for hb in handbooks_for_topic(topic):
        links.append({"title": hb.title, "url": hb.url})
    links.append({"title": "ai-agent-interview-guide", "url": GITHUB_GUIDE_TREE})
    for rel in github_files_for(stage_id, topic):
        links.append(
            {
                "title": rel.split("/")[-1],
                "url": f"{GITHUB_GUIDE_REPO}/blob/main/{rel}",
            }
        )
    return links
