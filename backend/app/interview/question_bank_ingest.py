"""Parse Feishu / markdown interview docs into normalized question items."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


SECTION_TOPIC_MAP: list[tuple[re.Pattern[str], str]] = [
    # ReAct paradigm — case-sensitive "ReAct" so frontend "React" is not stolen.
    (re.compile(r"ReAct|re-act"), "Agent"),
    (re.compile(r"react\s*(模式|推理|循环|agent)", re.I), "Agent"),
    (re.compile(r"agent|智能体|tool\s*call|function\s*call|\bmcp\b", re.I), "Agent"),
    (
        re.compile(
            r"\brag\b|检索增强|向量(检索|库|数据库|记忆)|知识库|chunk(ing)?|embedding|嵌入向量|召回|重排|rerank",
            re.I,
        ),
        "RAG",
    ),
    (re.compile(r"记忆|\bmemory\b|上下文(管理|窗口|压缩)?", re.I), "Memory"),
    (re.compile(r"workflow|工作流", re.I), "Workflow"),
    (re.compile(r"langgraph|langchain", re.I), "LangGraph"),
    # Python runtime / concurrency — before broad LLM so "Python 虚拟环境/Typing" land here.
    (
        re.compile(
            r"\bpython\b|\bgil\b|asyncio|协程|装饰器|深拷贝|浅拷贝|multiprocessing|"
            r"threading|subprocess|\btyping\b|类型安全|虚拟环境|解释器",
            re.I,
        ),
        "Python",
    ),
    (re.compile(r"\bllm\b|大模型|token|prompt\s*工程|提示词", re.I), "LLM"),
    (re.compile(r"redis|缓存", re.I), "Redis"),
    (re.compile(r"postgres|数据库|\bsql\b", re.I), "PostgreSQL"),
    (re.compile(r"fastapi|后端基础", re.I), "FastAPI"),
    # Frontend React only when clearly UI/framework (not "前端安全"/Prompt Injection).
    (
        re.compile(
            r"react\.?js|react\s*hooks?|\bjsx\b|\btsx\b|组件(设计|复用|状态)|vue|angular|前端(组件|框架|工程)",
            re.I,
        ),
        "React",
    ),
    (re.compile(r"docker|k8s|kubernetes", re.I), "Docker"),
    (re.compile(r"网络|\bhttp\b|websocket|\bsse\b", re.I), "SSE"),
    (re.compile(r"性能优化|性能", re.I), "性能优化"),
    (re.compile(r"系统设计", re.I), "系统设计"),
]

P5_PATTERNS = re.compile(
    r"什么是|是什么|了解|区别|定义|本质|有哪些|包括哪些|介绍一下",
    re.I,
)
P7_PATTERNS = re.compile(
    r"生产|线上|落地|故障|优化|评测|瓶颈|风险|工程|部署|监控|容量|事故|回归",
    re.I,
)
P6_PATTERNS = re.compile(
    r"为什么|如何|怎么|怎样|取舍|对比|实现|选择|设计|保证|防止|区别",
    re.I,
)

HEADING_RE = re.compile(r"^#{1,4}\s+(.+)$", re.MULTILINE)
QUESTION_LINE_RE = re.compile(
    r"^#{2,4}\s+(.+?[？?].*?)$|^###\s+(.+)$",
    re.MULTILINE,
)
XML_TAG_RE = re.compile(r"<[^>]+>")
CALLOUT_SKIP = re.compile(r"^(简介|内容已经分类|来自面经)", re.I)
# Feishu "高频题大集合" style: "## 1-请说明..." / "## 22.说下..."
NUMBERED_STEM_RE = re.compile(r"^\d+\s*[-.、．]\s*(.+)$")
CN_NUMBERED_STEM_RE = re.compile(r"^[一二三四五六七八九十百千]+[、.．]\s*(.+)$")
# Interview stems without trailing ？ (面经汇总常见标题)
STEM_START_RE = re.compile(
    r"^(请|说下|说说|简述|说明|解释|比较|介绍|描述|谈谈|分析|列举|举例|如何|怎么|什么是|为什么)",
)
STEM_END_RE = re.compile(r"(的区别|与.+区别|区别|是什么|有哪些|的理解|的原理)$")
STEM_INLINE_RE = re.compile(r"介绍一下|谈谈你|请详细|请说明|请解释|请简述|请结合|请分析|请谈谈|的理解")
SECTION_LABEL_RE = re.compile(
    r"^(核心区别|对比总结表?|说明|幂等性和安全性对比|GET vs POST.*|RFC 规范层面的区别|"
    r"一次完整请求的封装过程|第[一二三四五六七八九十\d]+步[：:].*)$"
)


@dataclass(frozen=True)
class ParsedQuestion:
    raw_question: str
    normalized_question: str
    topic: str
    level: str
    source_section: str | None
    tags: list[str]
    content_hash: str


def _strip_markup(text: str) -> str:
    text = XML_TAG_RE.sub("", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _strip_number_prefix(text: str) -> str:
    text = text.strip()
    m = NUMBERED_STEM_RE.match(text)
    if m:
        return m.group(1).strip()
    m = CN_NUMBERED_STEM_RE.match(text)
    if m:
        return m.group(1).strip()
    return text


def _infer_topic(section: str, question: str) -> str:
    blob = f"{section} {question}"
    for pattern, topic in SECTION_TOPIC_MAP:
        if pattern.search(blob):
            return topic
    return "General"


def _infer_level(question: str) -> str:
    if P5_PATTERNS.search(question) and not P7_PATTERNS.search(question):
        return "P5"
    if P7_PATTERNS.search(question):
        return "P7"
    if P6_PATTERNS.search(question):
        return "P6"
    return "P6"


def _normalize_question(text: str) -> str:
    text = _strip_number_prefix(_strip_markup(text))
    if len(text) > 200:
        text = text[:197] + "…"
    return text


def _content_hash(normalized: str, section: str | None) -> str:
    payload = f"{section or ''}|{normalized}".strip().lower()
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _looks_like_stem_phrase(text: str) -> bool:
    """True for interview-like headings that omit trailing ？."""
    text = text.strip()
    if len(text) < 6 or len(text) > 220:
        return False
    if SECTION_LABEL_RE.match(text) or CALLOUT_SKIP.search(text):
        return False
    if STEM_START_RE.search(text):
        return True
    if STEM_END_RE.search(text):
        return True
    if STEM_INLINE_RE.search(text):
        return True
    return False


def _looks_like_question(line: str) -> bool:
    line = _strip_markup(line)
    if len(line) < 6 or len(line) > 220:
        return False
    if CALLOUT_SKIP.search(line):
        return False
    if line.startswith("---"):
        return False
    if "面试加分点" in line or "大厂面试追问" in line:
        return False
    if SECTION_LABEL_RE.match(line):
        return False
    if "？" in line or "?" in line or line.endswith("吗") or line.endswith("呢"):
        return True
    # Arabic numbered titles (1-xxx / 22.xxx) are usually stems in Feishu collections.
    if NUMBERED_STEM_RE.match(line):
        body = _strip_number_prefix(line)
        return 6 <= len(body) <= 220 and not CALLOUT_SKIP.search(body)
    # Chinese numbered outline (一、xxx): only when body looks like a stem.
    cn = CN_NUMBERED_STEM_RE.match(line)
    if cn and _looks_like_stem_phrase(cn.group(1).strip()):
        return True
    if _looks_like_stem_phrase(line):
        return True
    return False


def _append_question(
    *,
    results: list[ParsedQuestion],
    seen_hashes: set[str],
    raw: str,
    current_section: str,
) -> None:
    normalized = _normalize_question(raw)
    if len(normalized) < 6:
        return
    topic = _infer_topic(current_section, normalized)
    level = _infer_level(normalized)
    h = _content_hash(normalized, current_section)
    if h in seen_hashes:
        return
    seen_hashes.add(h)
    results.append(
        ParsedQuestion(
            raw_question=raw,
            normalized_question=normalized,
            topic=topic,
            level=level,
            source_section=current_section or None,
            tags=[topic],
            content_hash=h,
        )
    )


def extract_questions_from_markdown(text: str) -> list[ParsedQuestion]:
    """Extract question stems from lark-cli markdown/xml-ish output."""
    lines = text.splitlines()
    current_section = ""
    seen_hashes: set[str] = set()
    results: list[ParsedQuestion] = []

    for raw_line in lines:
        heading = HEADING_RE.match(raw_line.strip())
        if heading:
            title = _strip_markup(heading.group(1))
            if title and not _looks_like_question(title):
                current_section = title
            elif _looks_like_question(title):
                _append_question(
                    results=results,
                    seen_hashes=seen_hashes,
                    raw=title,
                    current_section=current_section,
                )
            continue

        stripped = raw_line.strip()
        if stripped.startswith("### ") or stripped.startswith("## "):
            candidate = _strip_markup(stripped.lstrip("#").strip())
            if _looks_like_question(candidate):
                _append_question(
                    results=results,
                    seen_hashes=seen_hashes,
                    raw=candidate,
                    current_section=current_section,
                )

    return results


def document_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
