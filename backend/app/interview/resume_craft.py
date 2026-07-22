"""Evidence-bound resume craft: eligibility, whitelist draft, template, anti-fabrication."""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MIN_CONFIRMED_CLAIMS = 3
MIN_COMMITTED_7D = 1
WINDOW_DAYS = 7
PROJECT_LIKE = frozenset({"project", "role"})
EXCERPT_MAX = 280

_STYLE_EXAMPLES_PATH = Path(__file__).resolve().parent / "fixtures" / "resume_craft_style_examples.md"

_OUTPUT_SKELETON = """\
输出必须使用以下 Markdown 骨架（无证据的小节整段省略，不要写空标题）：

# （姓名） · {目标岗位} · {级别}

## 专业摘要
（3–4 句，仅 ResumeDraft 事实）

## 技能关键词
A · B · C

## 项目经历

### {项目名}
**角色** · {时间或「待补充」}
**技术栈：** …
**项目背景：** …
**工作内容：**
1. **{分块标题}**
   - …
**项目成果：**
- …

---
*本稿基于已确认简历事实与近 7 日训练闭环生成；未经验证的数据未写入。*
"""

_HARD_RULES = (
    "你是中文技术简历润色器。只根据用户提供的 ResumeDraft JSON 输出一份 Markdown 简历。\n"
    "禁止新增数字、公司、职责、项目或成果。缺数据时写「（待补充数据）」或省略该小节。\n"
    "写法参考中的项目名、技术细节与措辞不得原样写入用户简历；只能学习分区与句式。\n"
    "不要输出 JSON，不要解释，只输出 Markdown。"
)

_WORK_BUCKET_LABELS: dict[str, str] = {
    "principle": "原理与机制",
    "trade-off": "取舍与方案",
    "tradeoff": "取舍与方案",
    "evidence": "证据与验证",
    "position": "场景与定位",
}

_METRIC_PATTERNS = [
    re.compile(r"\d+(\.\d+)?\s*%"),
    re.compile(r"\d+(\.\d+)?\s*倍"),
    re.compile(r"(提升|降低|优化|增长|下降)\s*了?\s*\d+"),
    re.compile(r"QPS\s*[升提升到至了]*\s*\d+", re.I),
    re.compile(r"\d+\s*ms\b", re.I),
    re.compile(r"\d+\s*万"),
]


def check_eligibility(*, confirmed_claims: list[Any], committed_attempts_7d: int) -> dict[str, Any]:
    n = len(confirmed_claims)
    project_like = sum(1 for c in confirmed_claims if getattr(c, "category", None) in PROJECT_LIKE)
    reasons: list[str] = []
    if n < MIN_CONFIRMED_CLAIMS:
        reasons.append(f"需要至少 {MIN_CONFIRMED_CLAIMS} 条已确认的简历事实（当前 {n}）")
    if committed_attempts_7d < MIN_COMMITTED_7D:
        reasons.append("近 7 天需要至少 1 次已提交的训练闭环")
    return {
        "eligible": len(reasons) == 0,
        "reasons": reasons,
        "stats": {
            "confirmed_claims": n,
            "confirmed_project_like_claims": project_like,
            "committed_attempts_7d": int(committed_attempts_7d),
        },
    }


def normalize_work_bucket(focus_node: str | None) -> str:
    raw = (focus_node or "").strip().lower().replace("_", "-")
    if raw in _WORK_BUCKET_LABELS:
        return raw
    if "trade" in raw:
        return "trade-off"
    if "principle" in raw or "机制" in raw:
        return "principle"
    if "evidence" in raw or "证据" in raw:
        return "evidence"
    if "position" in raw or "场景" in raw:
        return "position"
    return "other"


def work_bucket_label(bucket: str) -> str:
    return _WORK_BUCKET_LABELS.get(bucket, "职责与实现")


def load_style_examples() -> str:
    try:
        text = _STYLE_EXAMPLES_PATH.read_text(encoding="utf-8").strip()
        return text
    except OSError as exc:
        logger.warning("resume_craft_style_examples_load_failed", extra={"error": str(exc)})
        return ""


@lru_cache(maxsize=1)
def build_polish_system_prompt() -> str:
    parts = [_HARD_RULES, "", _OUTPUT_SKELETON]
    examples = load_style_examples()
    if examples:
        parts.extend(["", "## 写法参考（虚构，禁止照抄）", "", examples])
    return "\n".join(parts).strip() + "\n"


def _answer_excerpt(attempt: Any) -> list[str]:
    answers = list(getattr(attempt, "answers", None) or [])
    if not answers:
        return []
    last = answers[-1]
    text = str(last.get("text") if isinstance(last, dict) else getattr(last, "text", "") or "")
    text = text.strip()
    if not text:
        return []
    return [text[:EXCERPT_MAX]]


def build_resume_draft(
    *,
    profile: Any,
    confirmed_claims: list[Any],
    committed_attempts: list[Any],
) -> dict[str, Any]:
    claims = [
        {
            "id": str(getattr(c, "id")),
            "category": str(getattr(c, "category")),
            "label": str(getattr(c, "label")),
            "keywords": list(getattr(c, "keywords", None) or []),
        }
        for c in confirmed_claims
    ]
    evidence = []
    for a in committed_attempts:
        if getattr(a, "status", None) != "committed":
            continue
        ev = getattr(a, "evaluation", None) or {}
        focus = str(getattr(a, "focus_node", ""))
        evidence.append(
            {
                "attempt_id": str(getattr(a, "id")),
                "topic": str(getattr(a, "topic", "")),
                "focus_node": focus,
                "work_bucket": normalize_work_bucket(focus),
                "covered_nodes": list(ev.get("covered_nodes") or []),
                "source_claim_ids": list(getattr(a, "source_claim_ids", None) or []),
                "user_answer_excerpts": _answer_excerpt(a),
                "evaluation_flags": {
                    "has_tradeoff": any("trade" in str(x).lower() for x in (ev.get("covered_nodes") or [])),
                    "has_evidence": any("evidence" in str(x).lower() for x in (ev.get("covered_nodes") or [])),
                },
            }
        )
    return {
        "profile": {
            "target_role": getattr(profile, "target_role", None),
            "target_level": getattr(profile, "target_level", None),
            "salary_band": getattr(profile, "salary_band", None),
            "keywords": list(getattr(profile, "keywords", None) or []),
        },
        "claims": claims,
        "evidence_from_training": evidence,
        "constraints": [
            "Do not invent metrics, headcount, revenue, latency numbers, or employers.",
            "Only rephrase facts present in claims and evidence_from_training.",
            "If a bullet lacks quantitative evidence, write qualitative impact only or mark （待补充数据）.",
            "Do not copy entities or wording from style few-shot examples.",
        ],
    }


def _collect_skills(draft: dict[str, Any]) -> list[str]:
    skills: list[str] = []
    p = draft.get("profile") or {}
    for k in p.get("keywords") or []:
        if k and k not in skills:
            skills.append(str(k))
    for c in draft.get("claims") or []:
        for k in c.get("keywords") or []:
            if k and k not in skills:
                skills.append(str(k))
        if c.get("category") == "skill" and c.get("label") and c["label"] not in skills:
            skills.append(str(c["label"]))
    return skills


def _evidence_by_claim(draft: dict[str, Any]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for e in draft.get("evidence_from_training") or []:
        for cid in e.get("source_claim_ids") or []:
            out.setdefault(str(cid), []).append(e)
    return out


def _project_tech_stack(claim: dict[str, Any], related: list[dict]) -> list[str]:
    stack: list[str] = []
    for k in claim.get("keywords") or []:
        if k and k not in stack:
            stack.append(str(k))
    for e in related:
        topic = e.get("topic")
        if topic and topic not in stack:
            stack.append(str(topic))
    return stack


def _render_project_block(claim: dict[str, Any], related: list[dict]) -> list[str]:
    lines = [
        f"### {claim['label']}",
        "**角色待补充** · **时间待补充**",
    ]
    stack = _project_tech_stack(claim, related)
    if stack:
        lines.append(f"**技术栈：** {'、'.join(stack)}")

    if related:
        excerpt0 = (related[0].get("user_answer_excerpts") or [""])[0]
        if excerpt0:
            lines.append(f"**项目背景：** 围绕「{claim['label']}」相关问题展开；训练中已覆盖可讲述证据。")
        else:
            lines.append(f"**项目背景：** 参与「{claim['label']}」相关建设与讲解沉淀。")
    # no evidence → omit 项目背景

    lines.append("**工作内容：**")
    if related:
        buckets: dict[str, list[dict]] = {}
        for e in related:
            bucket = str(e.get("work_bucket") or normalize_work_bucket(e.get("focus_node")))
            buckets.setdefault(bucket, []).append(e)
        for i, (bucket, items) in enumerate(buckets.items(), start=1):
            lines.append(f"{i}. **{work_bucket_label(bucket)}**")
            for e in items[:3]:
                excerpt = (e.get("user_answer_excerpts") or ["（训练中已覆盖相关节点）"])[0]
                topic = e.get("topic") or "主题"
                lines.append(f"   - [{topic}] {excerpt}")
    else:
        kws = "、".join(claim.get("keywords") or []) or "相关技术"
        lines.append("1. **职责与实现**")
        lines.append(f"   - 参与 {claim['label']}，使用 {kws}。")

    lines.append("**项目成果：**")
    if related:
        lines.append("- 将训练中已覆盖的机制 / 取舍 / 证据整理为可讲述项目贡献。（待补充数据）")
    else:
        lines.append("- （待补充数据）")
    lines.append("")
    return lines


def render_template_markdown(draft: dict[str, Any]) -> str:
    p = draft.get("profile") or {}
    role = p.get("target_role") or "目标岗位待定"
    level = p.get("target_level") or ""
    title = f"# （姓名） · {role}" + (f" · {level}" if level else "")
    skills = _collect_skills(draft)
    skill_line = " · ".join(skills) if skills else "（待补充）"

    lines = [
        title,
        "",
        "## 专业摘要",
        f"面向 {role} 的工程师，技术关键词覆盖：{'、'.join(skills[:12]) or '（待补充）'}。"
        "以下项目描述仅基于已确认事实与近期训练闭环中的可讲述证据。",
        "",
        "## 技能关键词",
        skill_line,
        "",
        "## 项目经历",
        "",
    ]

    projects = [c for c in (draft.get("claims") or []) if c.get("category") in PROJECT_LIKE]
    by_claim = _evidence_by_claim(draft)
    if not projects:
        lines.append("（请补充已确认的项目事实）")
        lines.append("")
    else:
        for c in projects:
            related = by_claim.get(str(c["id"]), [])
            lines.extend(_render_project_block(c, related))

    lines.extend(
        [
            "---",
            "*本稿基于已确认简历事实与近 7 日训练闭环生成；未经验证的数据未写入。*",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _collect_metrics(text: str) -> set[str]:
    hits: set[str] = set()
    for pat in _METRIC_PATTERNS:
        for m in pat.finditer(text or ""):
            hits.add(m.group(0).strip())
    return hits


def extract_novel_metrics(*, markdown: str, draft: dict[str, Any]) -> list[str]:
    allowed_blob = str(draft)
    for e in draft.get("evidence_from_training") or []:
        for ex in e.get("user_answer_excerpts") or []:
            allowed_blob += "\n" + ex
    allowed = _collect_metrics(allowed_blob)
    novel = []
    for m in sorted(_collect_metrics(markdown)):
        if m not in allowed:
            novel.append(m)
    return novel


def polish_or_template(*, draft: dict[str, Any], polished: str | None) -> tuple[str, list[str]]:
    template = render_template_markdown(draft)
    if not polished or not polished.strip():
        return template, ["degraded:template_only"]
    novel = extract_novel_metrics(markdown=polished, draft=draft)
    if novel:
        return template, ["degraded:metric_reject", f"rejected_metrics:{','.join(novel[:5])}"]
    return polished.strip() + ("\n" if not polished.endswith("\n") else ""), []
