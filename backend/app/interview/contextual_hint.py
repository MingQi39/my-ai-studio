"""Contextual progressive hints: driven by question (+ answer), no canned scaffolds."""

from __future__ import annotations

import re
from typing import Any

from app.interview.training import route_node_label

HINT_SYSTEM_PROMPT = """你是技术面试主动回忆教练，只给「最小提示」，不是答题助手。

硬性规则：
- 必须紧扣用户给出的「题目」原文；提示内容必须能看出读过该题
- 禁止拼接任何通用脚手架或套话，包括但不限于：
  「适用场景」「问题边界」「谁受益」「组织骨架」「先补：解决什么问题」
  「先点清…再补一句机制或取舍」「可用线索」等固定句式
- 用中文写 1～2 句；禁止完整答案、范文、标准答案
- 禁止替用户重写整段口述
- 若用户尚未作答：只根据题目给回忆方向
- 按 level 控制深度（仍禁止套话）：
  L1：用一句话点出本题真正在考什么
  L2：把本题改写成一个更短的回忆问句
  L3：只从本题原文抽出 2～4 个关键词（禁止通用清单）
  L4：给一句「怎么组织回答」的提醒，必须能对着本题用，禁止写满答案
只输出提示正文，不要编号标题，不要解释你的角色。
"""

_BANNED_BOILERPLATE = (
    "适用场景",
    "问题边界",
    "谁受益",
    "核心约束",
    "为什么这样抽象",
    "主路径 · 关键步骤",
    "它解决的是哪一类问题、在什么边界内成立",
    "组织骨架",
    "可用线索",
    "先补：",
    "当前先补",
    "解决什么问题",
    "底层原理",
    "怎么实现",
    "方案取舍",
    "项目证据",
)


def looks_like_full_answer(text: str) -> bool:
    if len(text or "") > 120:
        return True
    banned = ("标准答案", "完整答案", "范文", "参考回答", "可以这样答")
    return any(b in (text or "") for b in banned)


def looks_like_boilerplate(text: str) -> bool:
    t = text or ""
    return any(b in t for b in _BANNED_BOILERPLATE)


def has_submitted_evaluation(*, answers: list[Any] | None, evaluation: dict[str, Any] | None) -> bool:
    if not evaluation:
        return False
    if not answers:
        return False
    return True


def latest_answer_text(answers: list[Any] | None) -> str:
    if not answers:
        return ""
    items = sorted(
        answers,
        key=lambda a: int(a.get("version", 0) if isinstance(a, dict) else getattr(a, "version", 0) or 0),
    )
    last = items[-1]
    if isinstance(last, dict):
        return str(last.get("text") or "").strip()
    return str(getattr(last, "text", "") or "").strip()


def short_question(question: str, *, max_len: int = 72) -> str:
    q = " ".join((question or "").strip().split())
    if not q:
        return ""
    if len(q) <= max_len:
        return q
    return q[: max_len - 1].rstrip("，。,.；;：:") + "…"


def keywords_from_question(question: str, *, limit: int = 4) -> list[str]:
    q = (question or "").strip()
    if not q:
        return []
    tokens: list[str] = []
    for m in re.finditer(r"[A-Za-z][A-Za-z0-9+./_-]{1,24}", q):
        tok = m.group(0)
        if tok.lower() in {"the", "and", "for", "with", "from"}:
            continue
        if tok not in tokens:
            tokens.append(tok)
        if len(tokens) >= limit:
            return tokens[:limit]
    for part in re.split(r"[，。？?！!、；;：:\s「」『』《》（）()]+", q):
        part = part.strip()
        if len(part) < 2 or part in tokens:
            continue
        if 2 <= len(part) <= 12:
            tokens.append(part)
        elif len(part) > 12:
            tokens.append(part[:8])
        if len(tokens) >= limit:
            break
    return tokens[:limit]


def topic_template_hint(
    *,
    topic: str,
    node: str,
    level: int,
    question: str = "",
) -> dict[str, str]:
    """Last-resort fallback: only restate / extract from the question. No route-node scaffolds."""
    _ = node  # kept for call-site compatibility; never stitch Answer-Route labels into copy
    topic_s = (topic or "").strip()
    q_full = " ".join((question or "").strip().split())
    q = short_question(question) or topic_s or "本题"
    keys = keywords_from_question(question)
    lvl = min(max(int(level), 1), 4)

    if lvl <= 1:
        content = f"本题在问：{q}" if q_full else f"先想清「{topic_s or '本题'}」这道题在考什么。"
    elif lvl == 2:
        content = f"用更短的一句自问：{q}？" if q_full else f"把「{topic_s or '本题'}」改写成一个你能开口的短问题。"
    elif lvl == 3:
        if keys:
            content = "本题关键词：" + " · ".join(keys)
        elif q_full:
            content = f"从这句里自己划出关键词：「{q}」"
        else:
            content = f"围绕「{topic_s or '本题'}」写出你会用到的 2～3 个词。"
    else:
        content = (
            f"对着「{q}」说两三句：先结论，再一点原理或流程，最后一句你的项目经历。"
            if q_full
            else f"围绕「{topic_s or '本题'}」说两三句，先结论后细节。"
        )
    return {"level": str(lvl), "content": content}


def build_hint_messages(
    *,
    topic: str,
    question: str,
    answer: str,
    breakpoint: str | None,
    covered_nodes: list[str],
    missing_nodes: list[str],
    level: int,
    focus_node: str | None = None,
) -> list[dict[str, str]]:
    node = breakpoint or (missing_nodes[0] if missing_nodes else None) or focus_node or "Position"
    # Node names only for model context — must not become canned user-facing scaffolds.
    label = route_node_label(node)
    answer_block = answer.strip() if answer and answer.strip() else "（用户尚未作答——请只根据题目给回忆提示）"
    if breakpoint or covered_nodes or missing_nodes:
        eval_block = f"""## 评测上下文（仅供定位断点，禁止把下列中文标签抄进提示正文）
- 已覆盖: {", ".join(covered_nodes) or "（无）"}
- 缺失: {", ".join(missing_nodes) or "（无）"}
- 断点内部名: {breakpoint or "（无）"} / {label}"""
    else:
        eval_block = f"""## 评测上下文（用户尚未提交；禁止把焦点标签抄进提示正文）
- 焦点内部名: {node} / {label}"""
    user = f"""## 话题
{topic}

## 题目（提示必须紧扣此题，禁止通用套话）
{question}

## 用户答卷
{answer_block}

{eval_block}
- 提示层级 L{level}

只输出提示正文。"""
    return [
        {"role": "system", "content": HINT_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def resolve_contextual_hint(
    *,
    topic: str,
    node: str,
    level: int,
    llm_text: str | None,
    question: str = "",
) -> tuple[dict[str, str], str]:
    text = (llm_text or "").strip()
    if text and not looks_like_full_answer(text) and not looks_like_boilerplate(text):
        return {"level": str(min(max(level, 1), 4)), "content": text}, "llm"
    return (
        topic_template_hint(topic=topic, node=node, level=level, question=question),
        "template",
    )
