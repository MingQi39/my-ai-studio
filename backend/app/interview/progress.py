"""Compute interview training progress (coverage / route depth / retention)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


TRADEOFF_NODE = "Trade-off"
EVIDENCE_NODE = "Evidence"
ROUTE_DEPTH_WINDOW_DAYS = 7
TREND_WEEKS = 6
CONSOLIDATED_RECALL_MIN = 2

# salary_band keywords (substring match, lowercased)
HIGH_SALARY_MARKERS = ("40-60", "60k", "60+", "50-80", "80k")
MID_SALARY_MARKERS = ("25-40", "30-50", "20-35", "35-50")


@dataclass(frozen=True)
class ExpectationItem:
    id: str
    label: str
    detail: str
    met: bool


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def covered_nodes_from_evaluation(evaluation: dict[str, Any] | None) -> set[str]:
    if not evaluation:
        return set()
    raw = evaluation.get("covered_nodes") or []
    return {str(x) for x in raw}


def is_high_salary_band(salary_band: str | None) -> bool:
    text = (salary_band or "").lower().replace(" ", "")
    return any(m in text for m in HIGH_SALARY_MARKERS)


def is_mid_salary_band(salary_band: str | None) -> bool:
    text = (salary_band or "").lower().replace(" ", "")
    if not text or is_high_salary_band(salary_band):
        return False
    return any(m in text for m in MID_SALARY_MARKERS)


def band_tier(salary_band: str | None, target_level: str | None) -> str:
    """Return low | mid | high for expectation checklist."""
    level = (target_level or "").strip()
    if is_high_salary_band(salary_band) or level in {"高级", "P7"}:
        return "high"
    if level in {"初级", "P5"} and not is_mid_salary_band(salary_band):
        return "low"
    if is_mid_salary_band(salary_band) or level in {"中级", "P6"}:
        return "mid"
    if level in {"初级", "P5"}:
        return "low"
    return "mid"


def compute_coverage(
    *,
    role_topics: list[str],
    committed_topics: set[str],
) -> dict[str, Any]:
    bank = list(role_topics)
    covered = [t for t in bank if t in committed_topics]
    missing = [t for t in bank if t not in committed_topics]
    total = len(bank) or 1
    return {
        "covered_count": len(covered),
        "total_count": len(bank),
        "covered_topics": covered,
        "missing_topics": missing,
        "ratio": round(len(covered) / total, 4) if bank else 0.0,
    }


def compute_route_depth(
    *,
    committed_attempts: list[Any],
    now: datetime | None = None,
    window_days: int = ROUTE_DEPTH_WINDOW_DAYS,
) -> dict[str, Any]:
    now = now or _utcnow()
    cutoff = now - timedelta(days=window_days)
    recent = []
    for a in committed_attempts:
        updated = _as_aware(getattr(a, "updated_at", None))
        if updated is None or updated >= cutoff:
            recent.append(a)

    total = len(recent)
    tradeoff_hits = 0
    evidence_hits = 0
    node_sum = 0
    for a in recent:
        covered = covered_nodes_from_evaluation(getattr(a, "evaluation", None))
        node_sum += len(covered)
        if TRADEOFF_NODE in covered:
            tradeoff_hits += 1
        if EVIDENCE_NODE in covered:
            evidence_hits += 1

    return {
        "window_days": window_days,
        "committed_count": total,
        "tradeoff_hits": tradeoff_hits,
        "evidence_hits": evidence_hits,
        "tradeoff_rate": round(tradeoff_hits / total, 4) if total else 0.0,
        "evidence_rate": round(evidence_hits / total, 4) if total else 0.0,
        "avg_covered_nodes": round(node_sum / total, 2) if total else 0.0,
    }


def compute_retention(
    *,
    cards: list[Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or _utcnow()
    due = 0
    consolidated = 0
    stuck = 0
    for card in cards:
        missing = list(getattr(card, "missing_nodes", None) or [])
        recall = int(getattr(card, "successful_recall_count", 0) or 0)
        next_due = _as_aware(getattr(card, "next_due_at", None))
        status = getattr(card, "status", None) or "new"
        if missing:
            stuck += 1
        if recall >= CONSOLIDATED_RECALL_MIN or status == "mastered":
            consolidated += 1
        if next_due is not None and next_due <= now and status in {"new", "learning", "reviewing"}:
            due += 1
        elif next_due is None and status in {"new", "learning"} and recall == 0:
            due += 1

    total = len(cards) or 1
    healthy_ratio = round(consolidated / total, 4) if cards else 0.0
    return {
        "total_cards": len(cards),
        "due_count": due,
        "consolidated_count": consolidated,
        "stuck_count": stuck,
        "healthy_ratio": healthy_ratio,
    }


def build_expectations(
    *,
    tier: str,
    coverage: dict[str, Any],
    depth: dict[str, Any],
    retention: dict[str, Any],
) -> list[ExpectationItem]:
    items: list[ExpectationItem] = []
    covered_ratio = float(coverage.get("ratio") or 0)
    tradeoff_rate = float(depth.get("tradeoff_rate") or 0)
    evidence_rate = float(depth.get("evidence_rate") or 0)
    committed = int(depth.get("committed_count") or 0)
    consolidated = int(retention.get("consolidated_count") or 0)
    stuck = int(retention.get("stuck_count") or 0)

    if tier == "low":
        items.append(
            ExpectationItem(
                id="coverage_core",
                label="覆盖核心主题",
                detail="岗位题库至少练通 1～2 个主题闭环",
                met=coverage["covered_count"] >= min(2, max(1, coverage["total_count"] // 3))
                or coverage["covered_count"] >= 1,
            )
        )
        items.append(
            ExpectationItem(
                id="route_basic",
                label="说清问题与实现",
                detail="近 7 天有闭环，且平均覆盖 ≥2 个表达节点",
                met=committed >= 1 and float(depth.get("avg_covered_nodes") or 0) >= 2,
            )
        )
    elif tier == "mid":
        items.append(
            ExpectationItem(
                id="coverage_majority",
                label="覆盖岗位大半主题",
                detail="岗位题库覆盖率 ≥ 50%",
                met=covered_ratio >= 0.5,
            )
        )
        items.append(
            ExpectationItem(
                id="tradeoff_stable",
                label="稳定出现方案取舍",
                detail="近 7 天闭环中 ≥40% 走到「方案取舍」",
                met=committed >= 2 and tradeoff_rate >= 0.4,
            )
        )
        items.append(
            ExpectationItem(
                id="retention_basic",
                label="开始巩固复习卡",
                detail="至少 1 张卡成功回忆 ≥2 次",
                met=consolidated >= 1,
            )
        )
    else:  # high
        items.append(
            ExpectationItem(
                id="coverage_broad",
                label="主题接近全覆盖",
                detail="岗位题库覆盖率 ≥ 80%",
                met=covered_ratio >= 0.8,
            )
        )
        items.append(
            ExpectationItem(
                id="tradeoff_strong",
                label="取舍成为习惯",
                detail="近 7 天闭环中 ≥60% 走到「方案取舍」",
                met=committed >= 3 and tradeoff_rate >= 0.6,
            )
        )
        items.append(
            ExpectationItem(
                id="evidence_stable",
                label="稳定给出项目证据",
                detail="近 7 天闭环中 ≥40% 走到「项目证据」",
                met=committed >= 3 and evidence_rate >= 0.4,
            )
        )
        items.append(
            ExpectationItem(
                id="retention_strong",
                label="复习卡少卡壳",
                detail="已巩固 ≥3 且仍卡壳 ≤1",
                met=consolidated >= 3 and stuck <= 1,
            )
        )
    return items


def suggest_next_step(
    *,
    coverage: dict[str, Any],
    depth: dict[str, Any],
    retention: dict[str, Any],
    expectations: list[ExpectationItem],
) -> str:
    unmet = next((e for e in expectations if not e.met), None)
    if int(retention.get("due_count") or 0) > 0 and (
        unmet is None or unmet.id.startswith("retention")
    ):
        return f"有 {retention['due_count']} 张复习卡到期，先复习巩固再开新题。"
    if unmet:
        if unmet.id.startswith("coverage"):
            missing = coverage.get("missing_topics") or []
            hint = f"「{missing[0]}」" if missing else "未覆盖主题"
            return f"当前短板：主题覆盖。建议先完成 {hint} 的 1 道闭环。"
        if "tradeoff" in unmet.id:
            return "当前短板：方案取舍。建议完成本题时主动对比一个替代方案并 commit。"
        if "evidence" in unmet.id:
            return "当前短板：项目证据。建议用简历里确认过的事实收尾，再完成闭环。"
        if unmet.id.startswith("retention"):
            return "当前短板：复习留存。把已有复习卡练到能口头复述。"
        return f"下一步：{unmet.label} — {unmet.detail}"
    if coverage.get("missing_topics"):
        return f"目标期望已基本对齐。可继续补「{coverage['missing_topics'][0]}」拓宽覆盖。"
    return "进展健康。保持每周至少 2 次闭环 + 按时复习即可。"


def compute_composite_score(
    *,
    coverage: dict[str, Any],
    depth: dict[str, Any],
    retention: dict[str, Any],
    tier: str,
) -> dict[str, Any]:
    c = float(coverage.get("ratio") or 0)
    # depth: blend tradeoff/evidence/avg nodes (avg/5)
    d = (
        0.45 * float(depth.get("tradeoff_rate") or 0)
        + 0.35 * float(depth.get("evidence_rate") or 0)
        + 0.20 * min(float(depth.get("avg_covered_nodes") or 0) / 5.0, 1.0)
    )
    r = float(retention.get("healthy_ratio") or 0)
    raw = 100.0 * (0.35 * c + 0.45 * d + 0.20 * r)

    cap_reason: str | None = None
    capped = raw
    if tier == "mid" and float(depth.get("tradeoff_rate") or 0) < 0.4:
        capped = min(capped, 72.0)
        cap_reason = "中级目标要求取舍更稳定，深度不足时总分封顶 72"
    if tier == "high":
        if float(depth.get("evidence_rate") or 0) < 0.4:
            capped = min(capped, 68.0)
            cap_reason = "高薪带要求证据更稳定，证据不足时总分封顶 68"
        elif float(retention.get("healthy_ratio") or 0) < 0.3:
            capped = min(capped, 75.0)
            cap_reason = "高薪带要求复习留存，巩固不足时总分封顶 75"

    return {
        "score": int(round(min(max(capped, 0.0), 100.0))),
        "uncapped_score": int(round(min(max(raw, 0.0), 100.0))),
        "formula": "0.35×覆盖 + 0.45×深度 + 0.20×留存（深度含取舍/证据/节点覆盖）",
        "cap_reason": cap_reason,
        "components": {
            "coverage": round(c, 4),
            "depth": round(d, 4),
            "retention": round(r, 4),
        },
    }


def compute_weekly_trend(
    *,
    committed_attempts: list[Any],
    weeks: int = TREND_WEEKS,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    now = now or _utcnow()
    # Align to UTC week start (Monday)
    today = now.date()
    start_of_this_week = today - timedelta(days=today.weekday())
    buckets: list[dict[str, Any]] = []
    for i in range(weeks - 1, -1, -1):
        week_start = start_of_this_week - timedelta(days=7 * i)
        week_end = week_start + timedelta(days=7)
        week_attempts = []
        for a in committed_attempts:
            updated = _as_aware(getattr(a, "updated_at", None))
            if updated is None:
                continue
            d = updated.date()
            if week_start <= d < week_end:
                week_attempts.append(a)
        total = len(week_attempts)
        tradeoff = sum(
            1
            for a in week_attempts
            if TRADEOFF_NODE in covered_nodes_from_evaluation(getattr(a, "evaluation", None))
        )
        evidence = sum(
            1
            for a in week_attempts
            if EVIDENCE_NODE in covered_nodes_from_evaluation(getattr(a, "evaluation", None))
        )
        buckets.append(
            {
                "week_start": week_start.isoformat(),
                "committed_count": total,
                "tradeoff_rate": round(tradeoff / total, 4) if total else 0.0,
                "evidence_rate": round(evidence / total, 4) if total else 0.0,
            }
        )
    return buckets


def build_progress_payload(
    *,
    target_role: str | None,
    target_level: str | None,
    salary_band: str | None,
    role_topics: list[str],
    committed_attempts: list[Any],
    cards: list[Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    from app.interview.learning_path import recommend_learning_path

    now = now or _utcnow()
    committed_topics = {str(getattr(a, "topic", "")) for a in committed_attempts if getattr(a, "topic", None)}
    coverage = compute_coverage(role_topics=role_topics, committed_topics=committed_topics)
    depth = compute_route_depth(committed_attempts=committed_attempts, now=now)
    retention = compute_retention(cards=cards, now=now)
    tier = band_tier(salary_band, target_level)
    expectations = build_expectations(
        tier=tier, coverage=coverage, depth=depth, retention=retention
    )
    next_step = suggest_next_step(
        coverage=coverage, depth=depth, retention=retention, expectations=expectations
    )
    score = compute_composite_score(
        coverage=coverage, depth=depth, retention=retention, tier=tier
    )
    trend = compute_weekly_trend(committed_attempts=committed_attempts, now=now)
    learning_path = recommend_learning_path(
        committed_topics=committed_topics,
        role_topics=role_topics,
    )
    # Prefer learning-path next when coverage shortfall matches the recommended topic
    nm = learning_path.get("next_module") or {}
    if nm.get("topic") and nm.get("stage_id"):
        next_step = f"{nm.get('reason') or next_step}（也可点「下一模块」直接开练）"
    return {
        "goal": {
            "target_role": target_role,
            "target_level": target_level,
            "salary_band": salary_band,
            "tier": tier,
        },
        "coverage": coverage,
        "route_depth": depth,
        "retention": retention,
        "expectations": [
            {
                "id": e.id,
                "label": e.label,
                "detail": e.detail,
                "met": e.met,
            }
            for e in expectations
        ],
        "next_step": next_step,
        "learning_path": learning_path,
        "composite": score,
        "weekly_trend": trend,
        "counted_rule": "仅统计 committed 闭环与复习卡；换题/跳过不计入",
    }
