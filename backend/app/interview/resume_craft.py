"""Evidence-bound resume craft: eligibility, whitelist draft, template, anti-fabrication."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

MIN_CONFIRMED_CLAIMS = 3
MIN_COMMITTED_7D = 1
WINDOW_DAYS = 7
PROJECT_LIKE = frozenset({"project", "role"})
EXCERPT_MAX = 280

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
        evidence.append(
            {
                "attempt_id": str(getattr(a, "id")),
                "topic": str(getattr(a, "topic", "")),
                "focus_node": str(getattr(a, "focus_node", "")),
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
        ],
    }


def render_template_markdown(draft: dict[str, Any]) -> str:
    p = draft.get("profile") or {}
    role = p.get("target_role") or "目标岗位待定"
    level = p.get("target_level") or ""
    title = f"# （姓名） · {role}" + (f" · {level}" if level else "")
    skills: list[str] = []
    for k in p.get("keywords") or []:
        if k and k not in skills:
            skills.append(str(k))
    for c in draft.get("claims") or []:
        for k in c.get("keywords") or []:
            if k and k not in skills:
                skills.append(str(k))
        if c.get("category") == "skill" and c.get("label") and c["label"] not in skills:
            skills.append(str(c["label"]))

    lines = [
        title,
        "",
        "## 专业摘要",
        f"面向 {role} 的工程师，技术关键词覆盖：{'、'.join(skills[:12]) or '（待补充）'}。"
        "以下项目描述仅基于已确认事实与近期训练闭环中的可讲述证据。",
        "",
        "## 技能",
        "、".join(skills) if skills else "（待补充）",
        "",
        "## 项目经历",
    ]
    projects = [c for c in (draft.get("claims") or []) if c.get("category") in PROJECT_LIKE]
    if not projects:
        lines.append("- （请补充已确认的项目事实）")
    evidence_by_claim: dict[str, list[dict]] = {}
    for e in draft.get("evidence_from_training") or []:
        for cid in e.get("source_claim_ids") or []:
            evidence_by_claim.setdefault(str(cid), []).append(e)

    for c in projects:
        lines.append(f"### {c['label']}")
        related = evidence_by_claim.get(str(c["id"]), [])
        if related:
            for e in related[:3]:
                excerpt = (e.get("user_answer_excerpts") or ["（训练中已覆盖取舍/证据节点）"])[0]
                lines.append(f"- [{e.get('topic')}] {excerpt}")
        else:
            kws = "、".join(c.get("keywords") or []) or "相关技术"
            lines.append(f"- 参与 {c['label']}，使用 {kws}（定量结果待补充数据）。")
        lines.append("")

    lines.extend(
        [
            "---",
            "本稿基于已确认简历事实与近 7 日训练闭环生成；未经验证的数据未写入。",
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
