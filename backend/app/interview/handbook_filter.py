"""Quality filter for handbook-style Feishu docs (not pure interview lists)."""

from __future__ import annotations

import re

from app.interview.question_bank_ingest import (
    ParsedQuestion,
    extract_questions_from_markdown,
    _content_hash,
    _infer_level,
)

_CODEISH = re.compile(r"^\[|^'|^\s*\{|complete.*code|完整的RAG生成代码|^code_tool", re.I)
_STEPISH = re.compile(
    r"^\d+\s*[-.、．]?\s*(移除|提取|规范化|去除|检索相关|生成子|调用LLM|添加引用|"
    r"对假设|计算与|返回Top|首先需要|从搜索|进行数值)"
)
_TOO_SHORT_BODY = re.compile(r"^(为什么这样更有效|为什么需要|什么是检索优化)[？?]?$")
_NUM_PREFIX = re.compile(r"^\d+(?:\.\d+)*\.?\s*")
_CN_CHAPTER = re.compile(r"^[一二三四五六七八九十百]+[、.．]\s*")
_CN_BOOK_CHAPTER = re.compile(r"^第[一二三四五六七八九十百千\d]+章\s*")
_LAYER_PREFIX = re.compile(r"^第[一二三四五六七八九十\d]+层[：:、.\s]*")
_MODE_PREFIX = re.compile(r"^模式\d+[：:、.\s]*")
_VIEW_PREFIX = re.compile(r"^视角\d+[：:、.\s]*")
_STAGE_PREFIX = re.compile(r"^阶段\s*\d+[：:、.\s]*")
_DIFFICULTY_PREFIX = re.compile(r"^难点[一二三四五六七八九十\d]+[：:、.\s]*")
_HEADING_RE = re.compile(r"^#{1,4}\s+(.+)$")
_OVERVIEW_WRAP = re.compile(r"^(?:Overview|Indexing|Retrieval|Generation)[（(](.+?)[）)]\s*$", re.I)

_OUTLINE_SKIP = re.compile(
    r"^(实际代码|代码示例|代码实现|代码对比|完整的.+示例|问题描述|解决方案|"
    r"作用与地位|当前主流选择|选择建议|记忆架构图|架构图说明|架构图$|组成部分总览|"
    r"整体架构图|数据流转过程|万字详解|入门到实战|飞书云文档|前言$|概览$|"
    r".*的代码实现$|工具是Agent|最佳实践$|实际案例$|注意事项$|核心思想$|"
    r"知识框架|简单类比|完整流程图|可视化$|手算一个|真实案例演示|"
    r"矩阵形式计算|完整数据流|写在前面|安装依赖|配置 API Key|验证安装|"
    r"环境搭建|项目结构|主程序|运行效果|完整代码|代码详解|概念地图|"
    r"工作流程$|工作流程图$|一句话解释$|输出示例|输出过程|输出的计划|"
    r"Thought:|Action:|Observation:|Task \d+:|使用示例$|效果：$|"
    r"原始历史|第一轮对话|第二步：|alpha:|向量搜索结果$|关键词搜索结果|"
    r"融合排序$|按融合分数|传统方法$|HyDE方法$|简单查询直接检索$|"
    r"复杂查询用HyDE$|运行方式$|pyproject|src/|tests/|agent_harness|"
    r".*Scripts\\\\activate|.*pip install|安装 LangChain|安装依赖|"
    r"【.+入门到实战】|从小白到|万字详解|详细版$|实战教程)",
    re.I,
)

_RAG_CONCEPT = re.compile(
    r"(RAG|Chunking|Embedding|Retrieval|Indexing|Generation|Rerank|Re-rank|"
    r"HyDE|CRAG|Self-RAG|Routing|BM25|Multi[\s-]?Query|RAG-Fusion|"
    r"Decomposition|Step Back|RRF|分块|向量|检索|索引|重排|路由|"
    r"假设性文档|问题分解|查询处理|效果评估|引用)",
    re.I,
)

_CONCEPT_PAREN = re.compile(r"[（(][A-Za-z][^）)]{1,40}[）)]")


def is_interview_worthy_stem(question: str) -> bool:
    q = (question or "").strip()
    if len(q) < 8 or len(q) > 200:
        return False
    if _CODEISH.search(q) or _STEPISH.match(q):
        return False
    if "公司去年" in q or "营收是多少" in q or "财务表现" in q:
        return False
    if "Thought:" in q or "Action:" in q or "Observation:" in q:
        return False
    if "？" in q or "?" in q or q.endswith("吗") or q.endswith("呢"):
        return True
    if re.match(r"^(什么是|为什么|如何|怎么|怎样|请|说下|简述|解释|比较|介绍|谈谈)", q):
        return True
    if "的区别" in q or q.endswith("是什么") or "有哪些" in q:
        return True
    return False


def filter_handbook_questions(
    items: list[ParsedQuestion],
    *,
    default_topic: str | None = None,
) -> list[ParsedQuestion]:
    """Keep interview-like stems; optionally force topic when still General."""
    out: list[ParsedQuestion] = []
    seen: set[str] = set()
    for it in items:
        if not is_interview_worthy_stem(it.normalized_question):
            continue
        if _TOO_SHORT_BODY.match(it.normalized_question):
            continue
        topic = it.topic
        if default_topic and topic == "General":
            topic = default_topic
        key = it.normalized_question.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(
            ParsedQuestion(
                raw_question=it.raw_question,
                normalized_question=it.normalized_question,
                topic=topic,
                level=it.level,
                source_section=it.source_section,
                tags=[topic],
                content_hash=it.content_hash,
            )
        )
    return out


def _clean_outline_title(title: str) -> str:
    t = (title or "").strip().replace("\u200b", "")
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = re.sub(r"^【[^】]+】\s*", "", t)
    wrap = _OVERVIEW_WRAP.match(t)
    if wrap:
        t = wrap.group(1).strip()
    t = _NUM_PREFIX.sub("", t).strip()
    t = _CN_BOOK_CHAPTER.sub("", t).strip()
    t = _CN_CHAPTER.sub("", t).strip()
    t = _LAYER_PREFIX.sub("", t).strip()
    t = _MODE_PREFIX.sub("", t).strip()
    t = _VIEW_PREFIX.sub("", t).strip()
    t = _STAGE_PREFIX.sub("", t).strip()
    t = _DIFFICULTY_PREFIX.sub("", t).strip()
    t = re.sub(r"^组成部分[一二三四五六七八九十\d]+[：:、.\s]*", "", t).strip()
    t = re.sub(r"^深度理解", "", t).strip()
    t = re.sub(r"^先搞清楚[：:]\s*", "", t).strip()
    t = re.sub(r"^问题[：:]\s*", "", t).strip()
    t = re.sub(r"^关键[：:点函数]*[：:]\s*", "", t).strip()
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _as_stem(body: str, *, prefix: str | None = None) -> str | None:
    text = body.strip().replace("?", "？")
    text = re.sub(r"？+$", "", text).strip()
    if prefix and not re.match(r"^(什么是|为什么|如何|怎么|怎样|请)", text):
        text = f"{prefix}{text}"
    if not text.endswith(("吗", "呢")):
        text = f"{text}？"
    text = re.sub(r"？{2,}", "？", text)
    return text if is_interview_worthy_stem(text) else None


def outline_title_to_stem(title: str) -> str | None:
    """Turn a handbook TOC heading into an interview-like stem."""
    raw = (title or "").strip().replace("\u200b", "")
    raw = re.sub(r"\*\*([^*]+)\*\*", r"\1", raw)
    if len(raw) < 4 or len(raw) > 160:
        return None
    if _OUTLINE_SKIP.search(raw):
        return None
    if re.search(r"\\\\|Scripts[/\\]|pip install|npm install|\.py$|\.toml$|activate\b", raw, re.I):
        return None
    if re.search(r"从小白到|万字详解|详细版|实战教程：", raw):
        return None

    body = _clean_outline_title(raw)
    body = body.lstrip("、.．)） ").strip()
    if not body or len(body) < 4 or len(body) > 140:
        return None
    if _OUTLINE_SKIP.search(body):
        return None
    if re.search(r"从小白到|万字详解|详细版|实战教程|Scripts[/\\]|activate\b", body, re.I):
        return None

    if "？" in body or "?" in body:
        return _as_stem(body)

    if body.endswith("是什么") or body.endswith("啥关系") or body.endswith("是啥"):
        return _as_stem(body)

    if re.match(r"^(什么是|为什么|如何|怎么|怎样|请|说下|简述|解释|比较|介绍|谈谈)", body):
        return _as_stem(body)

    if _RAG_CONCEPT.search(body):
        return _as_stem(body, prefix="请说明")

    if re.search(
        r"(注意力|Self-Attention|Multi-Head|位置编码|QKV|Encoder|Decoder|"
        r"编码器|解码器|激活函数|特征抽取)",
        body,
        re.I,
    ):
        return _as_stem(body, prefix="请说明")

    if re.search(
        r"(无限循环|任务卡死|工具选择错误|上下文窗口溢出|错误处理|鲁棒性|成本控制|幻觉|超时|失败重试)",
        body,
    ):
        return _as_stem(f"Agent 场景下如何处理「{body}」")

    if re.search(r"(区别|对比|取舍|vs|VS|选择指南)", body, re.I):
        return _as_stem(body, prefix="请说明")

    if "层" in body and ("感知" in body or "认知" in body or "执行" in body or "记忆" in body):
        return _as_stem(f"{body}在 Agent 里负责什么")

    if re.search(
        r"(Perception|Cognition|Execution|Memory Layer|ReAct|CoT|"
        r"Plan-and-Execute|Self-Ask|LangGraph|LangChain|Transformer|"
        r"Chain of Thought|AutoGen|CrewAI|Dify)",
        body,
        re.I,
    ):
        name = re.sub(r"(深度解析|详解|介绍)$", "", body).strip()
        return _as_stem(name or body, prefix="什么是")

    if re.search(
        r"(Harness|Vibe Coding|Context Engineering|Prompt Engineering|"
        r"AGENTS\.md|CI Gate|MCP|可观测|沙箱|任务规格|项目记忆|"
        r"人类接管|验证机制)",
        body,
        re.I,
    ):
        return _as_stem(body, prefix="请说明")

    if re.search(
        r"(Prompt|Few-shot|Tools|Agent|LangSmith|温度|流式|迭代|"
        r"工具绑定|聊天模板|提示词模板|思考循环|记忆的 Agent|"
        r"State|Node|Edge|Reducer|MessagesState|Subgraph|"
        r"Human-in-the-Loop|Checkpoint|Supervisor|条件分支|循环流程|"
        r"持久化|调试技巧|规划|记忆模块|工具集|工作模式)",
        body,
        re.I,
    ):
        return _as_stem(body, prefix="请说明")

    if re.search(r"(多Agent|多智能体)", body, re.I):
        return _as_stem(body, prefix="请说明")

    if re.search(r"(优化|监控|可靠性|提示词|工具调用)", body):
        return _as_stem(body, prefix="如何做")

    if re.search(r"^案例|^智能客服|^代码生成|^数据分析", body):
        cleaned = re.sub(r"^案例[一二三四五六七八九十\d]+[：:]\s*", "", body)
        return _as_stem(cleaned, prefix="如何设计一个")

    if re.search(
        r"(定义|原理|架构|框架|评测|编排|发展趋势|核心组件|核心能力|四大核心)",
        body,
        re.I,
    ):
        return _as_stem(body, prefix="请说明")

    if re.search(r"(短期记忆|长期记忆|核心循环|规划方法|高级技巧)", body):
        return _as_stem(body, prefix="请说明")

    if "把Agent看作" in body or "把 Agent 看作" in body:
        return _as_stem(f"如何理解「{body}」这种视角")

    # Mid-level concept headings with English gloss: "文档分块（Chunking）"
    if _CONCEPT_PAREN.search(body) and 6 <= len(body) <= 80:
        return _as_stem(body, prefix="请说明")

    return None


def outline_titles_to_markdown(titles: list[str], *, doc_title: str = "") -> str:
    """Build markdown headings from TOC titles for extract_questions_from_markdown."""
    lines: list[str] = []
    if doc_title:
        lines.append(f"# {doc_title}")
        lines.append("")
    seen: set[str] = set()
    for title in titles:
        stem = outline_title_to_stem(title)
        if not stem:
            continue
        key = stem.lower()
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"### {stem}")
    lines.append("")
    return "\n".join(lines)


def extract_handbook_stems_from_markdown(
    text: str,
    *,
    default_topic: str | None = None,
) -> list[ParsedQuestion]:
    """
    Handbook ingest path:
    1) convert section headings → interview stems
    2) keep worthy stems from normal markdown extract
    """
    seen: set[str] = set()
    results: list[ParsedQuestion] = []

    def _add(raw: str, section: str = "") -> None:
        stem = raw.strip()
        if not is_interview_worthy_stem(stem) or _TOO_SHORT_BODY.match(stem):
            return
        key = stem.lower()
        if key in seen:
            return
        seen.add(key)
        topic = default_topic or "General"
        results.append(
            ParsedQuestion(
                raw_question=stem,
                normalized_question=stem,
                topic=topic,
                level=_infer_level(stem),
                source_section=section or None,
                tags=[topic],
                content_hash=_content_hash(stem, section or None),
            )
        )

    for line in text.splitlines():
        m = _HEADING_RE.match(line.strip())
        if not m:
            continue
        title = m.group(1).strip()
        stem = outline_title_to_stem(title)
        if stem:
            _add(stem, section=title)

    for item in filter_handbook_questions(
        extract_questions_from_markdown(text),
        default_topic=default_topic,
    ):
        _add(item.normalized_question, section=item.source_section or "")

    return results
