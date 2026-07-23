"""LLM-generated daily learning documents grounded in handbooks + question bank."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.interview.learning_curriculum import format_learning_doc_message, reading_unit_for_day
from app.interview.learning_sources import (
    format_crosscheck_markdown,
    format_source_links,
    github_files_for,
    handbooks_for_topic,
    primary_reference_for_section,
)
from app.interview.model_roles import resolve_model_role
from app.interview.question_bank_retrieval import QuestionBankRetrieval
from app.interview.schemas import PlanDayTask, TodayLearningDoc
from app.models.database import InterviewProfile, InterviewQuestionItem

logger = logging.getLogger(__name__)

DOC_FORMAT_VERSION = "qa_v1"

DAILY_DOC_SYSTEM = """你是「面试导航」学习教练。请生成一份用户打开就能直接学完的「今日学习讲义」。

硬性要求：
1. 内容必须可自学：包含概念讲解、机制说明、面试题、标准答案、答案解析。不要只给提纲或「去读某某文档」。
2. 优先对齐用户提供的飞书手册体系与 GitHub ai-agent-interview-guide 考点；不要编造虚假项目指标。
3. 每天 2～3 道核心面试题即可，但每题必须有完整可背诵/可口述的答案 + 为什么这样答的讲解。
4. 语言用中文，结构清晰，面向准备技术面试的工程师。
5. 必须严格使用以下 Markdown 标题（不要省略、不要改名）：

## 今日目标
（1～2 句：今天学什么、如何服务岗位/截止日期目标）

## 知识讲解
（800～1500 字量级即可；分小标题讲清概念、原理、关键机制。读完应能理解主题。）

## 面试题与详解
对每题使用固定子结构：

### Q1. （题目）
**答案**
（完整口述答案，分点写，可直接背/讲）

**讲解**
（为什么这样答、常见追问、易错点）

### Q2. …
（同上）

### Q3. …
（可选）

## 今日自测
（2～3 条：学完后立刻自检的口述/默写任务）

## 参考链接
（列出提供的手册与 GitHub 文件；知识讲解中的「对照」必须写成可点击的 Markdown 链接，使用用户消息里的「章节主链」，禁止只写「打开下方参考链接」。）"""


def _level_from_profile(profile: InterviewProfile) -> str:
    raw = (profile.target_level or "").strip()
    if raw in {"初级", "P5"}:
        return "P5"
    if raw in {"高级", "P7"}:
        return "P7"
    return "P6"


def _section_keywords(section_title: str | None, topic: str) -> set[str]:
    raw = f"{section_title or ''}".lower()
    topic_l = (topic or "").lower()
    # Prefer section tokens; topic alone is too broad (e.g. "LLM" matches every bank stem).
    parts = {p for p in raw.replace("、", " ").replace("/", " ").replace("与", " ").split() if len(p) >= 2}
    extras: set[str] = set()
    aliases = {
        "transformer": {"transformer", "注意力", "attention", "自注意力", "qkv", "q/k/v", "缩放点积"},
        "注意力": {"transformer", "注意力", "attention", "自注意力", "softmax"},
        "token": {"token", "上下文", "context", "窗口", "截断"},
        "few-shot": {"few-shot", "fewshot", "示例", "shot"},
        "prompt": {"prompt", "提示", "结构化", "约束"},
        "cot": {"cot", "chain-of-thought", "推理链", "思维链"},
        "温度": {"temperature", "top-p", "采样", "nucleus"},
        "分块": {"chunk", "分块", "overlap", "chunking"},
        "embedding": {"embedding", "向量", "hnsw", "索引"},
        "检索": {"检索", "bm25", "召回", "hyde", "rrf"},
        "重排": {"rerank", "重排", "重排序"},
        "幻觉": {"幻觉", "引用", "拒答", "grounding"},
    }
    blob = f"{raw} {topic_l}"
    for key, vals in aliases.items():
        if key in blob:
            extras |= vals
    return parts | extras


def _stem_relevance(stem: str, keywords: set[str]) -> int:
    text = stem.lower()
    return sum(1 for k in keywords if k.lower() in text)


async def _list_bank_stems(
    db: AsyncSession,
    topic: str,
    *,
    section_title: str | None = None,
    limit: int = 8,
    offset: int = 0,
) -> list[str]:
    result = await db.execute(
        select(InterviewQuestionItem.normalized_question, InterviewQuestionItem.source_section)
        .where(InterviewQuestionItem.is_active.is_(True), InterviewQuestionItem.topic == topic)
        .order_by(InterviewQuestionItem.created_at.asc())
        .offset(0)
        .limit(max(limit * 4, 24))
    )
    keywords = _section_keywords(section_title, topic)
    scored: list[tuple[int, str]] = []
    for q, section in result.all():
        if not q:
            continue
        label = f"[{section}] {q}" if section else q
        score = _stem_relevance(label, keywords)
        if section_title and section and section_title.lower() in str(section).lower():
            score += 3
        scored.append((score, label))
    scored.sort(key=lambda x: (-x[0], x[1]))
    # Prefer section-relevant; if none match, still return a slice for LLM context.
    relevant = [s for score, s in scored if score > 0]
    pool = relevant if relevant else [s for _, s in scored]
    start = offset % max(len(pool), 1) if pool else 0
    rotated = pool[start:] + pool[:start]
    return rotated[:limit]


async def gather_reference_stems(
    db: AsyncSession,
    *,
    profile: InterviewProfile,
    task: PlanDayTask,
    day_offset: int,
) -> list[str]:
    topic = task.topic
    level = _level_from_profile(profile)
    stems: list[str] = []
    keywords = _section_keywords(task.section_title, topic)

    retriever = QuestionBankRetrieval(db)
    for query_focus in (task.section_title, task.goal, topic):
        if not query_focus:
            continue
        hit = await retriever.retrieve(
            role=profile.target_role,
            topic=topic,
            level=level,
            focus_node=query_focus[:40] if len(query_focus) > 40 else query_focus,
            prefer_source_url_substr="ai-agent-interview-guide",
        )
        if hit and hit.question not in stems:
            stems.append(hit.question)

    offset = (day_offset * 3) % 15
    stems.extend(
        await _list_bank_stems(
            db, topic, section_title=task.section_title, limit=6, offset=offset
        )
    )
    scored: list[tuple[int, str]] = []
    seen: set[str] = set()
    for s in stems:
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        scored.append((_stem_relevance(s, keywords), s))
    scored.sort(key=lambda x: (-x[0], x[1]))
    relevant = [s for score, s in scored if score > 0]
    return (relevant or [s for _, s in scored])[:10]


def _build_user_prompt(
    *,
    profile: InterviewProfile,
    task: PlanDayTask,
    days_remaining: int | None,
    reference_stems: list[str],
) -> str:
    handbooks = handbooks_for_topic(task.topic)
    github_files = github_files_for(task.stage_id, task.topic)
    hb_lines = "\n".join(f"- {h.title}: {h.url}" for h in handbooks) or "- （无匹配手册，以 GitHub 指南为主）"
    gh_lines = "\n".join(f"- {GITHUB_BLOB}{f}" for f in github_files) or "- docs/00-学习路线图.md"

    bullets = "\n".join(f"- {b}" for b in (task.reading_bullets or ()))
    stems = "\n".join(f"- {s}" for s in reference_stems) or "- （题库暂无，请按章节纲要出题并给出完整答案）"
    section = task.section_title or task.title
    primary = primary_reference_for_section(section, topic=task.topic, stage_id=task.stage_id)
    primary_line = (
        f"- [{primary.label}]({primary.url})"
        if primary
        else "- （无单独主链，使用下方手册/GitHub 列表）"
    )

    return f"""## 用户目标
- 岗位：{profile.target_role or '未设置'}
- 级别：{profile.target_level or '中级'}
- 薪资带：{profile.salary_band or '未设置'}
- 目标达成日：{profile.target_deadline or '未设置'}
- 剩余天数：{days_remaining if days_remaining is not None else '未知'}

## 今日计划
- 日期：{task.date}
- 类型：{task.task_type}
- 主题：{task.topic}
- 阶段：{task.title}
- 章节：{section}
- 阶段目标：{task.goal}

## 今日必须覆盖的知识点
{bullets}

## 章节主链（知识讲解「对照」必须使用此 Markdown 链接，可点击）
{primary_line}

## 飞书手册（内容体系对齐这些手册）
{hb_lines}

## GitHub ai-agent-interview-guide 相关文件
{gh_lines}

## 题库考点（优先选与「今日章节」高度相关的题；勿选无关子题。每题写出完整答案与讲解）
{stems}

重要：今日章节是「{section}」。面试题必须围绕该章节与上方知识点，不要写成别的 Prompt/幻觉/评测子题（除非章节本身就是那个主题）。
知识讲解里每个要点的「对照」请写成 `- **对照**：[标题](url) · …`，url 优先用上方「章节主链」。
请直接输出完整讲义 Markdown。用户会靠这份文档自学，不要让他们再去别处找答案。
"""


GITHUB_BLOB = "https://github.com/bcefghj/ai-agent-interview-guide/blob/main/"


def _qa_block_from_bullet(index: int, bullet: str, topic: str, section: str) -> str:
    point = bullet.strip(" ·-")
    return f"""### Q{index}. 请用面试口述讲清：{point[:80]}{'…' if len(point) > 80 else ''}

**答案**
1. **是什么**：{point}。这是「{section}」里的核心点，属于 {topic} 体系。
2. **怎么工作**：先用自己的话复述机制（输入是什么、中间算什么、输出是什么）；再补一句「为什么这样设计」。
3. **面试落地**：说清适用场景、代价（延迟/成本/复杂度），并主动给一个对比方案或失败兜底。

**讲解**
- 面试官要听机制，不只是名词。把上面第 2 点讲到能画草图的程度。
- 常见追问：边界条件、和相邻概念的区别、线上如何观测对错。
- 若你只能背要点句子，说明还没学透——用「输入→计算→输出」再讲一遍。
"""


def _template_doc(
    task: PlanDayTask,
    bank_excerpts: list[str],
    source_links: list[dict[str, str]],
    *,
    days_remaining: int | None,
    profile: InterviewProfile,
) -> TodayLearningDoc:
    section = task.section_title or task.title
    goal_line = (
        f"为 {profile.target_role or '目标岗位'} 面试准备：今日学透「{section}」"
        f"（剩余 {days_remaining} 天）——读完本讲义即可掌握概念、答案与讲解"
        if days_remaining is not None
        else f"今日学习：{section}（含讲解与完整问答）"
    )
    bullets = list(task.reading_bullets or [])
    if not bullets:
        bullets = [f"掌握 {task.topic} 的核心概念与面试表达"]

    knowledge_parts: list[str] = []
    primary = primary_reference_for_section(section, topic=task.topic, stage_id=task.stage_id)
    crosscheck = format_crosscheck_markdown(primary, section)
    for i, b in enumerate(bullets, 1):
        knowledge_parts.append(
            f"### {i}. {b.strip(' ·-')[:60]}\n"
            f"- **要点**：{b}\n"
            f"- **口述提示**：先定义 → 再讲机制（输入/计算/输出）→ 最后说面试里怎么用或取舍。\n"
            f"{crosscheck}"
        )
    knowledge = "\n\n".join(knowledge_parts)

    # Template Qs must match today's unit — never dump unrelated topic-bank stems as Q1..Qn.
    # Bank stems stay in bank_excerpts for LLM regen; template only drills reading_bullets.
    qa_blocks = [_qa_block_from_bullet(i, b, task.topic, section) for i, b in enumerate(bullets[:3], 1)]

    links = "\n".join(f"- [{l['title']}]({l['url']})" for l in source_links[:6])
    md = f"""## 今日目标
{goal_line}

## 知识讲解
今日主题 **{task.topic}** · 章节 **{section}**

阶段目标：{task.goal}

{knowledge}

### 怎么学
1. 先通读上面知识点，用自己的话复述一遍（各 30 秒）。
2. 再看下方「面试题与详解」，对着答案练口述。
3. 最后做「今日自测」；卡住就回到对应要点。

> 说明：当前为模板讲义（LLM 未配置或调用失败时的兜底）。修好模型配置后点「重新生成」可拿到 AI 详解。

## 面试题与详解
{chr(10).join(qa_blocks)}

## 今日自测
1. 不看答案，口述今日 3 个核心知识点（各 30 秒）。
2. 任选一题，完整讲 2 分钟：定义 → 机制 → 取舍。
3. 在应用内开练「{task.topic}」，把今天答案结构用到实战题。

## 参考链接
{links}
"""
    return TodayLearningDoc(
        doc_title=task.doc_title or task.title,
        section_title=section or "今日阅读",
        topic=task.topic,
        reading_bullets=list(bullets),
        comic_url=task.comic_url,
        bank_excerpts=bank_excerpts,
        markdown_body=md,
        today_goal=goal_line,
        practice_task=f"学完讲义后，练一题「{task.topic}」并口述答案",
        source_links=source_links,  # type: ignore[arg-type]
        generated_by="template",
        format_version=DOC_FORMAT_VERSION,
    )


async def _call_daily_doc_llm(user_prompt: str) -> str | None:
    role = resolve_model_role("daily_doc")
    if role.provider_hint in {"rules", "template"}:
        return None
    base_url = (
        (getattr(settings, "INTERVIEW_DAILY_DOC_BASE_URL", "") or "").rstrip("/")
        or (settings.INTERVIEW_HINT_BASE_URL or "").rstrip("/")
        or (settings.INTERVIEW_RESUME_CRAFT_BASE_URL or "").rstrip("/")
    )
    if not base_url:
        return None
    api_key = (
        getattr(settings, "INTERVIEW_DAILY_DOC_API_KEY", "")
        or settings.INTERVIEW_HINT_API_KEY
        or settings.INTERVIEW_RESUME_CRAFT_API_KEY
        or ""
    )
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": role.model_id,
        "temperature": role.temperature,
        "messages": [
            {"role": "system", "content": DAILY_DOC_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=120.0, trust_env=False) as client:
            resp = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
            if resp.status_code >= 400:
                body = (resp.text or "")[:500]
                logger.warning(
                    "daily_doc_llm_http_error",
                    extra={
                        "status": resp.status_code,
                        "model": role.model_id,
                        "base_url": base_url,
                        "body": body,
                    },
                )
                resp.raise_for_status()
            data = resp.json()
        message = data["choices"][0]["message"]
        content = message.get("content") or message.get("reasoning_content") or ""
        if isinstance(content, str) and content.strip():
            return content.strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "daily_doc_llm_failed",
            extra={"error": f"{type(exc).__name__}: {exc}", "model": role.model_id, "base_url": base_url},
        )
    return None


def _extract_today_goal(markdown: str) -> str | None:
    for line in markdown.splitlines():
        if line.startswith("## 今日目标"):
            continue
        if line.startswith("## "):
            break
        text = line.strip()
        if text:
            return text
    return None


def _extract_practice_task(markdown: str) -> str | None:
    capture = False
    lines: list[str] = []
    for line in markdown.splitlines():
        if line.strip().startswith("## 今日自测") or line.strip().startswith("## 今日练习"):
            capture = True
            continue
        if capture and line.startswith("## "):
            break
        if capture and line.strip():
            lines.append(line.strip())
    return " ".join(lines[:2]) if lines else None


def is_usable_learning_doc(doc: TodayLearningDoc | None) -> bool:
    if doc is None or not doc.markdown_body:
        return False
    if (doc.format_version or "") != DOC_FORMAT_VERSION:
        return False
    body = doc.markdown_body
    return ("## 面试题与详解" in body or "**答案**" in body) and "## 知识讲解" in body


def _push_teaser(doc: TodayLearningDoc) -> str:
    head = doc.today_goal or f"{doc.doc_title} · {doc.section_title}"
    return (
        f"{head}\n"
        f"含知识讲解 + 面试题完整答案与解析。点击打开今日学习文档直接学。"
    )


async def generate_daily_learning_doc(
    db: AsyncSession,
    *,
    profile: InterviewProfile,
    task: PlanDayTask,
    day_offset: int = 0,
) -> TodayLearningDoc:
    source_links = format_source_links(task.stage_id, task.topic)
    reference_stems = await gather_reference_stems(
        db, profile=profile, task=task, day_offset=day_offset
    )
    days_remaining = None
    if profile.target_deadline:
        days_remaining = max(0, (profile.target_deadline - date.today()).days)

    if not task.reading_bullets or not task.doc_title:
        doc_title, section_title, bullets = reading_unit_for_day(
            task.stage_id,
            task_type=task.task_type,
            day_index_in_stage=day_offset,
            topic=task.topic,
        )
        task = task.model_copy(
            update={
                "doc_title": doc_title,
                "section_title": section_title,
                "reading_bullets": list(bullets),
            }
        )

    user_prompt = _build_user_prompt(
        profile=profile,
        task=task,
        days_remaining=days_remaining,
        reference_stems=reference_stems,
    )
    markdown = await _call_daily_doc_llm(user_prompt)
    if not markdown:
        return _template_doc(
            task,
            reference_stems[:5],
            source_links,
            days_remaining=days_remaining,
            profile=profile,
        )

    return TodayLearningDoc(
        doc_title=task.doc_title or task.title,
        section_title=task.section_title or "今日阅读",
        topic=task.topic,
        reading_bullets=list(task.reading_bullets or []),
        comic_url=task.comic_url,
        bank_excerpts=reference_stems[:5],
        markdown_body=markdown,
        today_goal=_extract_today_goal(markdown),
        practice_task=_extract_practice_task(markdown),
        source_links=source_links,  # type: ignore[arg-type]
        generated_by="llm",
        format_version=DOC_FORMAT_VERSION,
    )


def doc_to_cache(doc: TodayLearningDoc) -> dict[str, Any]:
    return doc.model_dump()


def doc_from_cache(data: dict[str, Any]) -> TodayLearningDoc:
    return TodayLearningDoc.model_validate(data)


def push_message_for_doc(doc: TodayLearningDoc) -> str:
    if doc.markdown_body:
        return _push_teaser(doc)
    return format_learning_doc_message(doc.doc_title, doc.section_title, tuple(doc.reading_bullets))
