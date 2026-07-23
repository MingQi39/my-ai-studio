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


@dataclass(frozen=True)
class PrimaryRef:
    """Best single click-through for a curriculum section's「对照」line."""

    label: str
    url: str


def _github_blob(rel: str, *, anchor: str | None = None) -> str:
    base = f"{GITHUB_GUIDE_REPO}/blob/main/{rel}"
    if not anchor:
        return base
    # GitHub keeps Unicode letters; spaces → hyphens; lowercase.
    slug = anchor.strip().lower().replace(" ", "-")
    return f"{base}#{slug}"


def _hb(title_substr: str) -> HandbookRef | None:
    for h in HANDBOOKS:
        if title_substr in h.title:
            return h
    return None


# Curated: section_title → primary click-through (GitHub+# when useful, else Feishu / file).
_SECTION_PRIMARY: dict[str, PrimaryRef] = {}


def _reg(section: str, label: str, url: str) -> None:
    _SECTION_PRIMARY[section] = PrimaryRef(label=label, url=url)


def _bootstrap_section_map() -> None:
    if _SECTION_PRIMARY:
        return
    tf = _hb("Transformer")
    rag = _hb("RAG")
    lg = _hb("LangGraph")
    harness = _hb("Harness")

    # s1 — Feishu for model basics; GitHub for Prompt chapters (+ optional #)
    if tf:
        _reg("Transformer 与注意力机制", f"{tf.title} · 注意力", tf.url)
        _reg("Token、上下文窗口与成本", f"{tf.title} · Token / 上下文", tf.url)
        _reg("温度、Top-p 与输出稳定性", f"{tf.title} · 采样参数", tf.url)
    _reg("结构化 Prompt 设计", "09-Prompt工程.md · 结构化提示", _github_blob("docs/09-Prompt工程.md"))
    _reg(
        "Few-shot 与示例选择",
        "09-Prompt工程.md · Few-shot",
        _github_blob("docs/09-Prompt工程.md", anchor="few-shot"),
    )
    _reg(
        "Chain-of-Thought 与推理链",
        "09-Prompt工程.md · CoT",
        _github_blob("docs/09-Prompt工程.md", anchor="chain-of-thought"),
    )

    # s2 — Feishu RAG handbook (stable); chunking → GitHub chapter file
    if rag:
        _reg("Embedding 与向量索引", f"{rag.title} · Embedding", rag.url)
        _reg("检索：向量 + 关键词混合", f"{rag.title} · 检索", rag.url)
        _reg("重排序（Rerank）", f"{rag.title} · 重排", rag.url)
        _reg("幻觉治理与引用", f"{rag.title} · 幻觉 / 引用", rag.url)
    _reg("文档分块（Chunking）策略", "03-RAG技术.md · 分块", _github_blob("docs/03-RAG技术.md"))

    # s3
    _reg("ReAct 循环", "01-基础概念.md · ReAct", _github_blob("docs/01-基础概念.md", anchor="react"))
    _reg(
        "LangGraph 与状态机",
        f"{lg.title} · 状态机" if lg else "02-核心框架.md · LangGraph",
        lg.url if lg else _github_blob("docs/02-核心框架.md", anchor="langgraph"),
    )
    _reg("Tool Calling 设计", "04-工具调用.md", _github_blob("docs/04-工具调用.md"))
    _reg("MCP 与工具生态", "04-工具调用.md · MCP", _github_blob("docs/04-工具调用.md", anchor="mcp"))

    # s4
    _reg("短期记忆（对话上下文）", "05-记忆系统.md · 短期", _github_blob("docs/05-记忆系统.md"))
    _reg("长期记忆存储", "05-记忆系统.md · 长期", _github_blob("docs/05-记忆系统.md"))
    _reg("多 Agent 协作模式", "06-多智能体.md", _github_blob("docs/06-多智能体.md"))

    # s5
    _reg("可观测性：日志、追踪、指标", "08-工程化实践.md · 可观测", _github_blob("docs/08-工程化实践.md"))
    _reg("熔断、降级与超时", "08-工程化实践.md · 熔断降级", _github_blob("docs/08-工程化实践.md"))
    _reg("Agent 评测", "08-工程化实践.md · 评测", _github_blob("docs/08-工程化实践.md"))
    if harness:
        _reg("项目表达与面试证据", f"{harness.title} · 面试表达", harness.url)
    else:
        _reg("项目表达与面试证据", "00-学习路线图.md · 面试", _github_blob("docs/00-学习路线图.md"))

    _reg("今日复习", "00-学习路线图.md", _github_blob("docs/00-学习路线图.md"))
    _reg("巩固拓宽", "00-学习路线图.md · 查漏补缺", _github_blob("docs/00-学习路线图.md"))


def primary_reference_for_section(
    section_title: str | None,
    *,
    topic: str,
    stage_id: str | None = None,
) -> PrimaryRef | None:
    """Resolve the best click-through for a handout「对照」line."""
    _bootstrap_section_map()
    section = (section_title or "").strip()
    if section and section in _SECTION_PRIMARY:
        return _SECTION_PRIMARY[section]

    handbooks = handbooks_for_topic(topic)
    if handbooks:
        hb = handbooks[0]
        return PrimaryRef(label=hb.title, url=hb.url)

    files = github_files_for(stage_id, topic)
    if files:
        rel = files[0]
        return PrimaryRef(label=rel.split("/")[-1], url=_github_blob(rel))

    return PrimaryRef(label="ai-agent-interview-guide", url=GITHUB_GUIDE_TREE)


def format_crosscheck_markdown(ref: PrimaryRef | None, section: str) -> str:
    """One Markdown list line for「对照」, clickable when ref is present."""
    sec = section.strip() or "今日章节"
    if ref and ref.url:
        return f"- **对照**：[{ref.label}]({ref.url}) · 用原文核对「{sec}」"
    return f"- **对照**：打开下方参考链接中与「{sec}」相关的手册章节，用原文核对一遍。"
