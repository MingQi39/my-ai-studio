"""Route reflection: review user answer against Answer Route — never emit model answers."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from app.interview.training import NODE_HINTS, ROUTE_NODES, hint_for, route_node_label

logger = logging.getLogger(__name__)

REFLECTION_SYSTEM_PROMPT = """你是面试表达训练的断点审查员，不是答题助手。

只输出一个 JSON 对象，字段严格如下：
{
  "covered": ["已覆盖的 Answer Route 节点名"],
  "missing": ["仍缺失的节点名"],
  "hallucinated_metrics": ["可疑的无依据量化指标原文片段"],
  "min_hint": "一句最小提示，只点断点，禁止给出完整标准答案或范文"
}

硬性禁止：
- 禁止输出 full_answer / model_answer / 标准答案 / 范文
- 禁止替用户重写整段口述
- min_hint 最多一两句，只提示缺哪类信息
"""

_METRIC_PATTERNS = [
    re.compile(r"\d+(\.\d+)?\s*%"),
    re.compile(r"\d+(\.\d+)?\s*倍"),
    re.compile(r"(提升|降低|优化|增长|下降)\s*了?\s*\d+"),
    re.compile(r"QPS\s*[升提升到至了]*\s*\d+", re.I),
    re.compile(r"准确率.{0,6}100\s*%"),
]


@dataclass
class RouteReflection:
    covered: list[str]
    missing: list[str]
    hallucinated_metrics: list[str]
    min_hint: str | None = None
    source: str = "rule"
    raw_model_output: str | None = None
    parse_error: str | None = None


class ReflectionLLM(Protocol):
    async def acomplete(self, messages: Sequence[dict[str, str]], **kwargs: Any) -> str:
        ...


def parse_reflection_json(raw: str) -> RouteReflection:
    text = (raw or "").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            raise ValueError("无法解析 JSON")
        data = json.loads(m.group(0))

    covered = [str(x) for x in (data.get("covered") or []) if str(x) in ROUTE_NODES]
    missing = [str(x) for x in (data.get("missing") or []) if str(x) in ROUTE_NODES]
    # Drop unknown / answer-leak fields intentionally
    metrics = [str(x).strip() for x in (data.get("hallucinated_metrics") or []) if str(x).strip()]
    min_hint = str(data.get("min_hint") or "").strip() or None
    if min_hint and _looks_like_full_answer(min_hint):
        min_hint = "请只补当前断点节点，不要展开成完整答案。"
    return RouteReflection(
        covered=covered,
        missing=missing,
        hallucinated_metrics=metrics[:8],
        min_hint=min_hint,
        source="llm",
        raw_model_output=raw,
    )


def _looks_like_full_answer(text: str) -> bool:
    if len(text) > 120:
        return True
    banned = ("标准答案", "完整答案", "范文", "参考回答", "可以这样答")
    return any(b in text for b in banned)


def rule_reflect(*, answer: str, focus_node: str | None = None) -> RouteReflection:
    hits: list[str] = []
    for pat in _METRIC_PATTERNS:
        for m in pat.finditer(answer or ""):
            frag = m.group(0).strip()
            if frag and frag not in hits:
                hits.append(frag)
    min_hint = None
    if hits:
        node = focus_node or "Evidence"
        min_hint = f"你提到了量化数字（如 {hits[0]}），请补一句可核实的证据来源，不要只报结果。"
        if node:
            base = hint_for(node, 2)
            min_hint = f"{base['content']}；同时核对量化是否有依据。"
    return RouteReflection(
        covered=[],
        missing=[],
        hallucinated_metrics=hits[:8],
        min_hint=min_hint,
        source="rule",
    )


async def llm_reflect(
    *,
    llm: ReflectionLLM,
    question: str,
    answer: str,
    route_nodes: list[str],
    focus_node: str | None = None,
) -> RouteReflection:
    user_content = f"""## 题目
{question}

## 用户口述
{answer}

## Answer Route 节点
{", ".join(route_nodes)}

## 当前焦点
{focus_node or "（无）"}

只输出审查 JSON。不要写完整答案。"""
    messages = [
        {"role": "system", "content": REFLECTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    try:
        raw = await llm.acomplete(messages, temperature=0.1)
        return parse_reflection_json(raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("route_reflect_llm_failed", extra={"error": str(exc)})
        return RouteReflection(
            covered=[],
            missing=[],
            hallucinated_metrics=[],
            min_hint=None,
            source="llm_error",
            parse_error=str(exc),
        )


def merge_rule_and_reflection(rule: dict[str, Any], reflection: RouteReflection) -> dict[str, Any]:
    """Merge deterministic keyword eval with optional reflection; never invent full answers."""
    covered = list(rule.get("covered_nodes") or [])
    missing = list(rule.get("missing_nodes") or [])

    if reflection.covered:
        for node in reflection.covered:
            if node not in covered and node in ROUTE_NODES:
                covered.append(node)
            if node in missing:
                missing = [m for m in missing if m != node]
    if reflection.missing:
        # Prefer reflection missing order when it provides a non-empty list
        refined = [n for n in reflection.missing if n in ROUTE_NODES and n not in covered]
        for n in missing:
            if n not in covered and n not in refined:
                refined.append(n)
        missing = refined

    # Keep route order for missing
    missing = [n for n in ROUTE_NODES if n in missing]
    covered = [n for n in ROUTE_NODES if n in covered]

    breakpoint = missing[0] if missing else None
    focus = rule.get("breakpoint")
    if isinstance(focus, str) and focus in missing:
        breakpoint = focus
    if reflection.missing and reflection.missing[0] in missing:
        breakpoint = reflection.missing[0]

    hint = rule.get("hint")
    if breakpoint and reflection.min_hint:
        meta = NODE_HINTS.get(breakpoint, {})
        hint = {
            "node": breakpoint,
            "recall": reflection.min_hint,
            "keywords": meta.get("keywords", ""),
            "example": meta.get("example", ""),
        }
    elif breakpoint and not hint:
        meta = NODE_HINTS.get(breakpoint, {})
        hint = {
            "node": breakpoint,
            "recall": meta.get("recall", f"补上「{route_node_label(breakpoint)}」"),
            "keywords": meta.get("keywords", ""),
            "example": meta.get("example", ""),
        }

    out = dict(rule)
    out["covered_nodes"] = covered
    out["missing_nodes"] = missing
    out["breakpoint"] = breakpoint
    out["hint"] = hint
    out["complete"] = len(missing) == 0
    out["next_step"] = (
        f"用一句话补上「{route_node_label(breakpoint)}」，然后重答。"
        if breakpoint
        else str(rule.get("next_step") or "路径已基本走通。")
    )
    out["llm"] = {
        "source": "route_reflection",
        "reflection_source": reflection.source,
        "hallucinated_metrics": list(reflection.hallucinated_metrics),
        "min_hint": reflection.min_hint,
        "parse_error": reflection.parse_error,
    }
    return out
