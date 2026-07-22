# Interview Resume Craft Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the Interview page, add one-click evidence-bound Chinese Markdown resume generation (eligibility gate → ResumeDraft → optional LLM polish → copyable Markdown).

**Architecture:** Pure functions in `resume_craft.py` build eligibility + whitelist draft + template Markdown. `POST /interview/resume/craft` re-checks eligibility, optionally polishes via injectable LLM (`purpose=resume_craft`), rejects invented metrics and falls back to template. Frontend loads eligibility, disables the button with reasons, shows a Dialog with Markdown + Copy.

**Tech Stack:** FastAPI, Pydantic schemas, existing `InterviewService` / SQLAlchemy models, React + Radix Dialog, pytest (unit tests; no new frontend test framework).

**Spec:** `docs/superpowers/specs/2026-07-22-interview-resume-craft-design.md`

## Global Constraints

- Never invent metrics, employers, headcount, or project outcomes not present in confirmed claims / committed attempt excerpts.
- Unlock only when `confirmed_claims >= 3` **and** `committed_attempts_7d >= 1`.
- Output P0: in-page Markdown + copy only (no PDF).
- LLM unavailable or metric hallucination → return template Markdown with `warnings` including `degraded:template_only` or `degraded:metric_reject`.
- Project-like claims = `category in {"project", "role"}` (existing `ClaimCategory`).

---

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/interview/resume_craft.py` | Eligibility, draft build, template Markdown, metric scan, polish orchestration |
| `backend/app/interview/schemas.py` | `ResumeEligibilityResponse`, `ResumeCraftResponse` |
| `backend/app/interview/model_roles.py` | Add `resume_craft` purpose |
| `backend/app/config.py` + `backend/.env.example` | `INTERVIEW_RESUME_CRAFT_*` settings |
| `backend/app/interview/services.py` | Load claims/attempts; call craft; return API payloads |
| `backend/app/api/v1/interview.py` | `GET /resume/eligibility`, `POST /resume/craft` |
| `backend/tests/test_interview_resume_craft.py` | Unit tests for craft module |
| `frontend/src/services/api.ts` | Client helpers + types |
| `frontend/src/pages/InterviewPage.tsx` | Button, eligibility load, Dialog, copy |

**Explicit non-touch:** PDF export, resume history table, independent resume workspace, English resume.

---

### Task 1: Eligibility + draft + template Markdown (pure, TDD)

**Files:**
- Create: `backend/app/interview/resume_craft.py`
- Create: `backend/tests/test_interview_resume_craft.py`

**Interfaces:**
- Produces:
  - `MIN_CONFIRMED_CLAIMS = 3`, `MIN_COMMITTED_7D = 1`, `WINDOW_DAYS = 7`
  - `check_eligibility(*, confirmed_claims: list, committed_attempts_7d: int) -> dict`
  - `build_resume_draft(*, profile, confirmed_claims, committed_attempts) -> dict`
  - `render_template_markdown(draft: dict) -> str`
  - `extract_novel_metrics(*, markdown: str, draft: dict) -> list[str]`
  - `polish_or_template(*, draft: dict, polished: str | None) -> tuple[str, list[str]]`

- [ ] **Step 1: Write failing tests**

```python
"""Unit tests for interview resume craft (eligibility / draft / anti-fabrication)."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.interview.resume_craft import (
    check_eligibility,
    build_resume_draft,
    render_template_markdown,
    extract_novel_metrics,
    polish_or_template,
)


def test_eligibility_requires_claims_and_recent_commit():
    claims = [
        SimpleNamespace(status="confirmed", category="skill", label="React", keywords=["React"], id="1"),
        SimpleNamespace(status="confirmed", category="skill", label="SSE", keywords=["SSE"], id="2"),
        SimpleNamespace(status="confirmed", category="project", label="Qi AI Studio", keywords=[], id="3"),
    ]
    bad = check_eligibility(confirmed_claims=claims[:1], committed_attempts_7d=0)
    assert bad["eligible"] is False
    assert bad["stats"]["confirmed_claims"] == 1
    assert any("确认" in r for r in bad["reasons"])

    ok = check_eligibility(confirmed_claims=claims, committed_attempts_7d=1)
    assert ok["eligible"] is True
    assert ok["reasons"] == []


def test_draft_excludes_candidate_claims_and_includes_evidence():
    profile = SimpleNamespace(
        target_role="AI 应用工程师",
        target_level="P6",
        salary_band="30-50k",
        keywords=["FastAPI"],
    )
    claims = [
        SimpleNamespace(id="c1", status="confirmed", category="project", label="面试导航", keywords=["SSE"]),
        SimpleNamespace(id="c2", status="candidate", category="skill", label="K8s", keywords=["K8s"]),
    ]
    now = datetime(2026, 7, 22, tzinfo=timezone.utc)
    attempt = SimpleNamespace(
        id="a1",
        status="committed",
        topic="SSE",
        focus_node="Trade-off",
        source_claim_ids=["c1"],
        updated_at=now - timedelta(days=1),
        answers=[{"version": 1, "text": "选 SSE 因为单向推送与 HTTP 栈一致"}],
        evaluation={"covered_nodes": ["Principle", "Trade-off", "Evidence"]},
    )
    draft = build_resume_draft(
        profile=profile,
        confirmed_claims=[c for c in claims if c.status == "confirmed"],
        committed_attempts=[attempt],
    )
    assert [c["id"] for c in draft["claims"]] == ["c1"]
    assert draft["evidence_from_training"][0]["topic"] == "SSE"
    assert "SSE" in draft["evidence_from_training"][0]["user_answer_excerpts"][0]


def test_template_markdown_contains_footer_and_no_fake_metrics():
    draft = {
        "profile": {"target_role": "后端", "target_level": "P6", "salary_band": None, "keywords": ["Go"]},
        "claims": [{"id": "1", "category": "project", "label": "网关", "keywords": ["Go"]}],
        "evidence_from_training": [],
        "constraints": [],
    }
    md = render_template_markdown(draft)
    assert "网关" in md
    assert "待验证" in md or "未经验证" in md
    assert "300%" not in md


def test_novel_metrics_rejected_falls_back_to_template():
    draft = {
        "profile": {"target_role": "后端", "target_level": "P6", "salary_band": None, "keywords": []},
        "claims": [{"id": "1", "category": "project", "label": "网关", "keywords": []}],
        "evidence_from_training": [],
        "constraints": [],
    }
    polished = "# 简历\n- 性能提升 300%\n"
    md, warnings = polish_or_template(draft=draft, polished=polished)
    assert "300%" not in md
    assert any("metric" in w for w in warnings)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_interview_resume_craft.py -v`

Expected: FAIL with `ModuleNotFoundError` or import error for `resume_craft`.

- [ ] **Step 3: Implement `resume_craft.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_interview_resume_craft.py -v`

Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/interview/resume_craft.py backend/tests/test_interview_resume_craft.py
git commit -m "feat(interview): add resume craft eligibility and template draft"
```

---

### Task 2: Schemas, model role, config, service + HTTP routes

**Files:**
- Modify: `backend/app/interview/schemas.py`
- Modify: `backend/app/interview/model_roles.py`
- Modify: `backend/app/config.py`
- Modify: `backend/.env.example`
- Modify: `backend/app/interview/services.py`
- Modify: `backend/app/api/v1/interview.py`

**Interfaces:**
- Consumes: `check_eligibility`, `build_resume_draft`, `polish_or_template`, `render_template_markdown` from Task 1
- Produces:
  - `GET /interview/resume/eligibility` → `ResumeEligibilityResponse`
  - `POST /interview/resume/craft` → `ResumeCraftResponse` or HTTP 403 with `detail.reasons`

- [ ] **Step 1: Add schemas**

Append to `backend/app/interview/schemas.py`:

```python
class ResumeEligibilityStats(BaseModel):
    confirmed_claims: int
    confirmed_project_like_claims: int
    committed_attempts_7d: int


class ResumeEligibilityResponse(BaseModel):
    eligible: bool
    reasons: list[str] = Field(default_factory=list)
    stats: ResumeEligibilityStats


class ResumeCraftSources(BaseModel):
    claim_ids: list[str] = Field(default_factory=list)
    attempt_ids: list[str] = Field(default_factory=list)


class ResumeCraftResponse(BaseModel):
    markdown: str
    sources: ResumeCraftSources
    warnings: list[str] = Field(default_factory=list)
```

- [ ] **Step 2: Extend model_roles + config**

In `model_roles.py`, extend:

```python
InterviewModelPurpose = Literal["evaluate", "hint", "reflect", "embed", "resume_craft"]
```

Add branch before evaluate default:

```python
if purpose == "resume_craft":
    return ModelRoleConfig(
        purpose=purpose,
        provider_hint=getattr(settings, "INTERVIEW_RESUME_CRAFT_PROVIDER", "template"),
        model_id=getattr(settings, "INTERVIEW_RESUME_CRAFT_MODEL", "template"),
        temperature=0.3,
    )
```

In `config.py` after reflect settings:

```python
INTERVIEW_RESUME_CRAFT_PROVIDER: str = "template"  # template | openai_compatible
INTERVIEW_RESUME_CRAFT_MODEL: str = "template"
INTERVIEW_RESUME_CRAFT_BASE_URL: str = ""  # optional OpenAI-compatible base
INTERVIEW_RESUME_CRAFT_API_KEY: str = ""
```

Document the same keys in `backend/.env.example`.

- [ ] **Step 3: Service helpers**

In `InterviewService`, add methods (follow existing async session patterns used by `get_training_progress`):

```python
async def resume_eligibility(self, user_id: UUID) -> dict:
    profile = await self.get_or_create_profile(user_id)
    claims = await self.list_claims(user_id)  # filter confirmed in Python
    confirmed = [c for c in claims if c.status == "confirmed"]
    attempts = await self._list_committed_attempts(profile.id, window_days=7)
    return check_eligibility(
        confirmed_claims=confirmed,
        committed_attempts_7d=len(attempts),
    )

async def craft_resume(self, user_id: UUID) -> dict:
    profile = await self.get_or_create_profile(user_id)
    claims = [c for c in await self.list_claims(user_id) if c.status == "confirmed"]
    attempts = await self._list_committed_attempts(profile.id, window_days=7)
    gate = check_eligibility(confirmed_claims=claims, committed_attempts_7d=len(attempts))
    if not gate["eligible"]:
        raise HTTPException(status_code=403, detail={"reasons": gate["reasons"], "stats": gate["stats"]})
    draft = build_resume_draft(profile=profile, confirmed_claims=claims, committed_attempts=attempts)
    polished = await self._maybe_polish_resume(draft)
    markdown, warnings = polish_or_template(draft=draft, polished=polished)
    if not profile.target_role:
        warnings.append("未设置目标岗位，标题区已用占位")
    return {
        "markdown": markdown,
        "sources": {
            "claim_ids": [str(c.id) for c in claims],
            "attempt_ids": [str(a.id) for a in attempts],
        },
        "warnings": warnings,
    }
```

Implement `_list_committed_attempts` with `status=="committed"` and `updated_at >= now - 7d` (timezone-aware), reusing progress window semantics.

`_maybe_polish_resume`: if `resolve_model_role("resume_craft").provider_hint == "template"`, return `None`. Otherwise call a small OpenAI-compatible chat completion via `httpx` (system prompt: only rewrite draft JSON to Markdown; no new facts). On any error, return `None`.

System prompt (store as constant in `resume_craft.py`):

```text
你是中文技术简历润色器。只根据用户提供的 ResumeDraft JSON 输出一份 Markdown 简历。
禁止新增数字、公司、职责、项目或成果。缺数据时写「（待补充数据）」。
不要输出 JSON，不要解释，只输出 Markdown。
```

- [ ] **Step 4: Wire routes**

In `interview.py`:

```python
@router.get("/resume/eligibility", response_model=ResumeEligibilityResponse)
async def resume_eligibility(
    user_id: UUID = Depends(get_current_user_auth),
    db: AsyncSession = Depends(get_db),
):
    data = await InterviewService(db).resume_eligibility(user_id)
    return ResumeEligibilityResponse(**data)

@router.post("/resume/craft", response_model=ResumeCraftResponse)
async def craft_resume(
    user_id: UUID = Depends(get_current_user_auth),
    db: AsyncSession = Depends(get_db),
):
    data = await InterviewService(db).craft_resume(user_id)
    return ResumeCraftResponse(**data)
```

Import the new schema types.

- [ ] **Step 5: Add unit test for metric path already covered; add one service-level pure test if `_maybe_polish` is mockable — optional.** Prefer extending `test_interview_resume_craft.py` with:

```python
def test_polish_accepts_when_metric_already_in_excerpt():
    draft = {
        "profile": {"target_role": "后端", "target_level": "P6", "salary_band": None, "keywords": []},
        "claims": [{"id": "1", "category": "project", "label": "网关", "keywords": []}],
        "evidence_from_training": [
            {"user_answer_excerpts": ["延迟从 200ms 降到 50ms"], "source_claim_ids": ["1"], "topic": "性能", "focus_node": "Evidence", "covered_nodes": ["Evidence"], "attempt_id": "a", "evaluation_flags": {}}
        ],
        "constraints": [],
    }
    polished = "- 将延迟从 200ms 降到 50ms\n"
    md, warnings = polish_or_template(draft=draft, polished=polished)
    assert "50ms" in md
    assert warnings == []
```

- [ ] **Step 6: Run tests**

Run: `cd backend && python -m pytest tests/test_interview_resume_craft.py tests/test_interview_model_roles.py -v`

Expected: PASS. If `test_interview_model_roles.py` asserts purpose set exhaustively, update it to include `resume_craft`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/interview/schemas.py backend/app/interview/model_roles.py backend/app/config.py backend/.env.example backend/app/interview/services.py backend/app/api/v1/interview.py backend/tests/test_interview_resume_craft.py backend/tests/test_interview_model_roles.py
git commit -m "feat(interview): expose resume eligibility and craft APIs"
```

---

### Task 3: Frontend — API client + Interview page button/dialog

**Files:**
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/pages/InterviewPage.tsx`

**Interfaces:**
- Consumes: `GET /interview/resume/eligibility`, `POST /interview/resume/craft`
- Produces: disabled「生成简历」button + Dialog with Markdown + Copy

- [ ] **Step 1: Add API types and functions in `api.ts`**

Near other interview helpers:

```typescript
export type ResumeEligibility = {
  eligible: boolean;
  reasons: string[];
  stats: {
    confirmed_claims: number;
    confirmed_project_like_claims: number;
    committed_attempts_7d: number;
  };
};

export type ResumeCraftResult = {
  markdown: string;
  sources: { claim_ids: string[]; attempt_ids: string[] };
  warnings: string[];
};

export async function getResumeEligibility(): Promise<ResumeEligibility> {
  return request('/interview/resume/eligibility');
}

export async function craftInterviewResume(): Promise<ResumeCraftResult> {
  return request('/interview/resume/craft', { method: 'POST', body: '{}' });
}
```

- [ ] **Step 2: Wire InterviewPage UX**

1. State: `resumeEligibility`, `resumeMarkdown`, `resumeOpen`, `resumeBusy`, `resumeWarn`.
2. When entering train phase (same place progress is loaded), also `getResumeEligibility().then(setResumeEligibility)`.
3. After successful claim confirm / attempt commit, refresh eligibility (same refresh hooks as progress).
4. In train header (next to「更新简历」), add:

```tsx
<button
  type="button"
  disabled={!resumeEligibility?.eligible || !!busy || resumeBusy}
  title={resumeEligibility && !resumeEligibility.eligible ? resumeEligibility.reasons.join('；') : '基于已确认事实与训练证据生成 Markdown 简历'}
  onClick={() => void onCraftResume()}
  className="..."
>
  生成简历
</button>
```

5. `onCraftResume`: set busy → `craftInterviewResume()` → set markdown + open dialog → refresh eligibility; on 403 show reasons in `error`.
6. Dialog (use `@/components/ui/dialog`):

```tsx
<Dialog open={resumeOpen} onOpenChange={setResumeOpen}>
  <DialogContent className="max-w-2xl">
    <DialogHeader>
      <DialogTitle>生成的简历（Markdown）</DialogTitle>
    </DialogHeader>
    {resumeWarn?.length ? <p className="text-xs text-amber-700">{resumeWarn.join(' · ')}</p> : null}
    <pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap rounded-lg border p-3 text-sm">{resumeMarkdown}</pre>
    <button type="button" onClick={() => void navigator.clipboard.writeText(resumeMarkdown)}>复制</button>
  </DialogContent>
</Dialog>
```

Match existing InterviewPage button/border token classes (`border-[var(--border-color)]` etc.).

- [ ] **Step 3: Typecheck / smoke**

Run: `cd frontend && npx tsc --noEmit`

Expected: no new errors in touched files.

Manual smoke (dev servers): ineligible → button disabled with title reasons; after 3 confirmed claims + 1 commit → generate → copy works; with `INTERVIEW_RESUME_CRAFT_PROVIDER=template` still returns Markdown.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/services/api.ts frontend/src/pages/InterviewPage.tsx
git commit -m "feat(interview): add generate-resume button with Markdown copy"
```

---

## Spec coverage self-check

| Spec item | Task |
|-----------|------|
| Eligibility ≥3 claims + 7d commit | Task 1–2 |
| GET eligibility | Task 2 |
| POST craft + 403 | Task 2 |
| ResumeDraft whitelist | Task 1 |
| Template Markdown skeleton + footer | Task 1 |
| LLM polish optional + template fallback | Task 2 |
| Novel metric reject | Task 1–2 |
| Page Markdown + copy, disabled button | Task 3 |
| Config `INTERVIEW_RESUME_CRAFT_*` | Task 2 |
| No PDF / no history DB | Explicit non-touch |

## Placeholder scan

None intentional. Implementers must not leave `TODO` for polish — default provider `template` is the complete P0 path; `openai_compatible` is optional enhancement inside `_maybe_polish_resume`.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-22-interview-resume-craft.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — this session with executing-plans and checkpoints  

Which approach?
