# Learning Doc Deep Links Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or implement inline. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn template/LLM handout「对照」lines into clickable Markdown links that deep-link when possible and fall back to whole docs.

**Architecture:** Curated section→source map in `learning_sources.py`; template and LLM prompt consume `primary_reference_for_section(...)`.

**Tech Stack:** FastAPI / Python, existing Markdown handout renderer.

## Global Constraints

- Prefer GitHub `blob/...md#slug` when curated; else Feishu handbook page; else first GitHub file; else plain fallback text.
- No Feishu in-page anchors; no runtime scraping.
- Frontend Markdown already renders links — no UI change required beyond existing `react-markdown`.

---

### Task 1: Section reference resolver + tests

**Files:**
- Modify: `backend/app/interview/learning_sources.py`
- Modify: `backend/tests/test_daily_doc_generator.py` (or new `test_learning_sources.py`)

**Produces:**
- `PrimaryRef` dataclass with `label: str`, `url: str`
- `primary_reference_for_section(section_title: str | None, *, topic: str, stage_id: str | None) -> PrimaryRef | None`
- `format_对照_markdown(ref: PrimaryRef | None, section: str) -> str`

- [ ] **Step 1:** Failing tests for Transformer section → http link; unknown section → Feishu/GitHub fallback by topic; `format_对照_markdown` contains `[` `](` 
- [ ] **Step 2:** Implement map + resolver covering all `STAGE_READING_UNITS` section titles (GitHub file + optional `#` slug where known; else handbook)
- [ ] **Step 3:** Tests pass

### Task 2: Wire into template + LLM prompt

**Files:**
- Modify: `backend/app/interview/daily_doc_generator.py`
- Modify: `backend/tests/test_daily_doc_generator.py`

**Produces:** Template「对照」uses markdown link; prompt includes 章节主链.

- [ ] **Step 1:** Failing test: template body contains `](http` in 对照 line for LLM/Transformer task
- [ ] **Step 2:** `_template_doc` + `_build_user_prompt` / system notes use resolver
- [ ] **Step 3:** Tests pass

### Task 3: Commit (when user asks)

---

## Spec coverage

- Clickable 对照 → Task 1–2  
- Anchor when possible / whole doc else → Task 1 map  
- LLM prompt → Task 2  
- No frontend change → intentional  
