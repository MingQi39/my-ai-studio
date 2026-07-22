"""Extract interview Q stems from bcefghj/ai-agent-interview-guide style markdown."""

from __future__ import annotations

import re
from pathlib import Path

from app.interview.question_bank_ingest import (
    ParsedQuestion,
    _content_hash,
    _infer_level,
    _infer_topic,
)

# Explicit file → default topic (override General when text is vague).
FILE_DEFAULT_TOPIC: dict[str, str] = {
    "01-基础概念.md": "Agent",
    "02-核心框架.md": "Agent",
    "03-RAG技术.md": "RAG",
    "04-工具调用.md": "Agent",
    "05-记忆系统.md": "Memory",
    "06-多智能体.md": "Agent",
    "07-大模型基础.md": "LLM",
    "08-工程化实践.md": "可观测性",
    "09-Prompt工程.md": "LLM",
    "README.md": "Agent",
}

_Q_LINE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\*\*(?:面试\s*)?Q\d*[a-zA-Z]?[：:]\s*(.+?)\*\*\s*$"),
    re.compile(r"^\*\*Q[：:]\s*(.+?)\*\*\s*$"),
    re.compile(r"^###\s*Q\d+[：:]\s*(.+)\s*$"),
    re.compile(r"^-\s*\*\*追问[：:]\s*(.+?)\*\*"),
)

_WEAK_FOLLOWUP = re.compile(
    r"^(和|与|那|那它|这种|那种).{0,12}(区别|不同|呢)[？?]?$"
    r"|^(为什么|怎么说|举例)[？?]?$"
    r"|^有什么(优缺点|区别)[？?]?$",
)


def _normalize_stem(raw: str) -> str:
    q = re.sub(r"\s+", " ", (raw or "").strip())
    q = re.sub(r"^[\d一二三四五六七八九十]+[、.．]\s*", "", q)
    q = q.strip("　 \t")
    if not q.endswith(("？", "?", "吗", "呢")):
        q = f"{q}？"
    return q.replace("?", "？")


def _is_keep_stem(q: str) -> bool:
    if len(q) < 10 or len(q) > 200:
        return False
    if _WEAK_FOLLOWUP.match(q):
        return False
    if q.count("```") or q.startswith("http"):
        return False
    return True


def extract_questions_from_guide_markdown(
    text: str,
    *,
    source_section: str | None = None,
    default_topic: str | None = None,
) -> list[ParsedQuestion]:
    """Parse bold Q / ### Q / 追问 lines into ParsedQuestion items."""
    seen: set[str] = set()
    out: list[ParsedQuestion] = []
    section = source_section or ""

    for line in text.splitlines():
        stripped = line.strip()
        matched: str | None = None
        for pat in _Q_LINE_PATTERNS:
            m = pat.match(stripped)
            if m:
                matched = m.group(1)
                break
        if not matched:
            continue
        stem = _normalize_stem(matched)
        if not _is_keep_stem(stem):
            continue
        key = stem.lower()
        if key in seen:
            continue
        seen.add(key)
        topic = _infer_topic(section, stem)
        if default_topic and topic == "General":
            topic = default_topic
        out.append(
            ParsedQuestion(
                raw_question=matched.strip(),
                normalized_question=stem,
                topic=topic,
                level=_infer_level(stem),
                source_section=section or None,
                tags=[topic],
                content_hash=_content_hash(stem, section or None),
            )
        )
    return out


def extract_from_guide_repo(repo_dir: Path) -> list[ParsedQuestion]:
    """
    Walk docs/01-面试八股文/*.md and docs/06-面试问答集/README.md.
    Deduplicate across files.
    """
    repo_dir = Path(repo_dir)
    bagua = repo_dir / "docs" / "01-面试八股文"
    qa = repo_dir / "docs" / "06-面试问答集" / "README.md"

    seen: set[str] = set()
    results: list[ParsedQuestion] = []

    files: list[tuple[Path, str | None, str]] = []
    if bagua.is_dir():
        for path in sorted(bagua.glob("0*.md")):
            files.append((path, FILE_DEFAULT_TOPIC.get(path.name), path.name))
    if qa.is_file():
        files.append((qa, "Agent", "06-面试问答集"))

    for path, default_topic, section in files:
        items = extract_questions_from_guide_markdown(
            path.read_text(encoding="utf-8"),
            source_section=section,
            default_topic=default_topic,
        )
        for it in items:
            key = it.normalized_question.lower()
            if key in seen:
                continue
            seen.add(key)
            results.append(it)
    return results
