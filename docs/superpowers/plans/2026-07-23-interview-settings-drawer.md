# Interview Settings Drawer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make interview setup a first-time-only screen; move everyday goal/push/deadline config into a train-page right Sheet so users stop abandoning in-progress attempts just to tweak settings.

**Architecture:** Frontend-only state split. Pure helpers compare saved vs draft goal cores. `InterviewSettingsSheet` owns form UI; `InterviewPage` owns open/draft/saved sync, two `AlertDialog`s (goal switch vs deadline rebalance), push instant save, and CTA label switching. Backend profile/attempt APIs unchanged.

**Tech Stack:** React 18, existing Radix `Sheet` + `AlertDialog`, `node:test` + `--experimental-strip-types` for pure TS helpers, existing `updateInterviewProfile` / `abandonInterviewAttempt` / `createInterviewAttempt`.

**Spec:** `docs/superpowers/specs/2026-07-23-interview-settings-drawer-design.md`

## Global Constraints

- Setup `phase='setup'` only when boot finds incomplete profile (`!target_role || !target_level || !salary_band`). Never navigate train → setup for 「设置」.
- 「稍后」on goal confirm = discard draft, do **not** `updateInterviewProfile` for role/level/salary, do **not** abandon.
- Push fields auto-save on change; deadline never triggers question-switch dialog.
- Applying goal must **not** persist an unconfirmed deadline draft.
- 「补充简历」stays a separate header action.
- Prefer Chinese UI copy matching spec §4; update all 9 locale files.
- Do not invent backend pending-goal tables.

---

## File map

| File | Responsibility |
|------|----------------|
| `frontend/src/components/interview/interviewGoalDraft.ts` | Normalize/compare goal core; active-attempt CTA kind |
| `frontend/src/components/interview/interviewGoalDraft.test.ts` | `node:test` coverage for helpers |
| `frontend/src/components/interview/InterviewSettingsSheet.tsx` | Right Sheet: goal + deadline + push blocks; emit events |
| `frontend/src/pages/InterviewPage.tsx` | Wire sheet, dialogs, remove abandon→setup, CTA switch |
| `frontend/src/i18n/locales/{zh-CN,zh-TW,en,ja,ko,de,fr,es,ru}.json` | Settings / dialog / CTA strings |

**Explicit non-touch:** attempt FSM, progress.py, plan_service rebalance rules (call existing PATCH only), LearningDocWorkspace, voice controls.

---

### Task 1: Goal draft helpers (TDD)

**Files:**
- Create: `frontend/src/components/interview/interviewGoalDraft.ts`
- Create: `frontend/src/components/interview/interviewGoalDraft.test.ts`

**Interfaces:**
- Produces:
  - `export type GoalCore = { targetRole: string; difficulty: string; salaryBand: string }`
  - `export function normalizeGoalCore(g: GoalCore): GoalCore`
  - `export function goalCoreChanged(saved: GoalCore, draft: GoalCore): boolean`
  - `export type AttemptCtaKind = 'switch' | 'generate'`
  - `export function attemptCtaKind(status: string | null | undefined): AttemptCtaKind`
  - Active statuses for `'switch'`: `open`, `answering`, `evaluated`, `reanswered`, `degraded`

- [ ] **Step 1: Write the failing test**

```ts
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  attemptCtaKind,
  goalCoreChanged,
  normalizeGoalCore,
} from './interviewGoalDraft.ts';

describe('interviewGoalDraft', () => {
  it('normalize trims role and treats empty salary as empty', () => {
    const n = normalizeGoalCore({
      targetRole: '  前端  ',
      difficulty: '中级',
      salaryBand: ' 40-60k ',
    });
    assert.equal(n.targetRole, '前端');
    assert.equal(n.salaryBand, '40-60k');
  });

  it('goalCoreChanged is false when equal after normalize', () => {
    const saved = { targetRole: '前端', difficulty: '中级', salaryBand: '40-60k' };
    const draft = { targetRole: ' 前端 ', difficulty: '中级', salaryBand: '40-60k' };
    assert.equal(goalCoreChanged(saved, draft), false);
  });

  it('goalCoreChanged is true when role differs', () => {
    assert.equal(
      goalCoreChanged(
        { targetRole: '前端', difficulty: '中级', salaryBand: '40-60k' },
        { targetRole: '后端', difficulty: '中级', salaryBand: '40-60k' },
      ),
      true,
    );
  });

  it('attemptCtaKind switches only for non-terminal active statuses', () => {
    assert.equal(attemptCtaKind('answering'), 'switch');
    assert.equal(attemptCtaKind('evaluated'), 'switch');
    assert.equal(attemptCtaKind('committed'), 'generate');
    assert.equal(attemptCtaKind('abandoned'), 'generate');
    assert.equal(attemptCtaKind(null), 'generate');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && node --experimental-strip-types --test src/components/interview/interviewGoalDraft.test.ts`

Expected: FAIL (module not found)

- [ ] **Step 3: Write minimal implementation**

```ts
export type GoalCore = {
  targetRole: string;
  difficulty: string;
  salaryBand: string;
};

export function normalizeGoalCore(g: GoalCore): GoalCore {
  return {
    targetRole: g.targetRole.trim(),
    difficulty: g.difficulty.trim(),
    salaryBand: g.salaryBand.trim(),
  };
}

export function goalCoreChanged(saved: GoalCore, draft: GoalCore): boolean {
  const a = normalizeGoalCore(saved);
  const b = normalizeGoalCore(draft);
  return (
    a.targetRole !== b.targetRole ||
    a.difficulty !== b.difficulty ||
    a.salaryBand !== b.salaryBand
  );
}

const ACTIVE = new Set([
  'open',
  'answering',
  'evaluated',
  'reanswered',
  'degraded',
]);

export type AttemptCtaKind = 'switch' | 'generate';

export function attemptCtaKind(status: string | null | undefined): AttemptCtaKind {
  if (status && ACTIVE.has(status)) return 'switch';
  return 'generate';
}
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd frontend && node --experimental-strip-types --test src/components/interview/interviewGoalDraft.test.ts`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/interview/interviewGoalDraft.ts frontend/src/components/interview/interviewGoalDraft.test.ts
git commit -m "$(cat <<'EOF'
test: add interview goal draft helpers for settings drawer

EOF
)"
```

---

### Task 2: `InterviewSettingsSheet` presentational component

**Files:**
- Create: `frontend/src/components/interview/InterviewSettingsSheet.tsx`
- Modify: (none yet — wiring in Task 3)

**Interfaces:**
- Consumes: `GoalCore` types conceptually; page passes primitive props
- Produces: React component

```tsx
export type InterviewSettingsSheetProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  // draft goal
  targetRole: string;
  customRole: string;
  difficulty: string; // Difficulty
  salaryBand: string;
  onTargetRole: (role: string) => void;
  onCustomRole: (v: string) => void;
  onDifficulty: (d: string) => void;
  onSalaryBand: (b: string) => void;
  onApplyGoal: () => void;
  applyGoalDisabled?: boolean;
  // deadline draft
  targetDeadline: string; // '' or YYYY-MM-DD
  onTargetDeadline: (v: string) => void;
  onApplyDeadline: () => void;
  applyDeadlineDisabled?: boolean;
  // push (controlled + instant callbacks)
  supportsPush: boolean;
  pushEnabled: boolean;
  pushFrequency: string;
  pushTime: string;
  onPushEnabled: (v: boolean) => void;
  onPushFrequency: (v: string) => void;
  onPushTime: (v: string) => void;
  onPushNow: () => void;
  pushNowBusy?: boolean;
};
```

- [ ] **Step 1: Implement Sheet using existing UI kit**

Use `Sheet`, `SheetContent` (`side="right"`, className widen to `sm:max-w-md`), `SheetHeader`, `SheetTitle`, `SheetDescription` from `frontend/src/components/ui/sheet.tsx`.

Mirror setup controls from `InterviewPage.tsx` setup block (~ROLE_OPTIONS chips, difficulty ChoiceButtons, salary bands, deadline input, push checkbox/select/time). Prefer copying JSX structure rather than abstracting ChoiceButton out of InterviewPage in this task (can keep local small button helpers inside the sheet file to avoid a large refactor).

Header description (zh hardcoded ok if i18n comes in Task 7; or accept `title`/`hint` props):

- Title: 设置
- Hint: 提醒会自动保存。修改岗位/难度/薪资后请点「应用目标」。关闭抽屉会丢弃未应用的目标与截止日期草稿。

Footer buttons:
- 「应用截止日期」 secondary
- 「应用目标」 primary

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit -p tsconfig.json 2>&1 | head -40`

Expected: no errors in the new file (fix any introduced).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/interview/InterviewSettingsSheet.tsx
git commit -m "$(cat <<'EOF'
feat(interview): add settings sheet UI for train-page config

EOF
)"
```

---

### Task 3: Wire sheet; replace「改目标」; discard draft on close

**Files:**
- Modify: `frontend/src/pages/InterviewPage.tsx`

**Interfaces:**
- Consumes: `InterviewSettingsSheet`, `goalCoreChanged` (Task 4 will use apply)
- Page state additions:
  - `settingsOpen: boolean`
  - Draft mirrors for settings: either reuse page `targetRole`/`difficulty`/`salaryBand`/`targetDeadline` carefully, **or** dedicated `draftRole`/`draftDifficulty`/`draftSalary`/`draftDeadline` reset from saved whenever sheet opens

**Recommended draft model (follow spec §4.6 / decision A):**

```ts
const [settingsOpen, setSettingsOpen] = useState(false);
const [draftRole, setDraftRole] = useState('');
const [draftCustomRole, setDraftCustomRole] = useState('');
const [draftDifficulty, setDraftDifficulty] = useState<Difficulty>('中级');
const [draftSalary, setDraftSalary] = useState('25-40k');
const [draftDeadline, setDraftDeadline] = useState('');

function openSettings() {
  // seed from current saved page state (already synced from profile)
  setDraftRole(ROLE_OPTIONS.includes(targetRole as any) ? targetRole : '');
  setDraftCustomRole(ROLE_OPTIONS.includes(targetRole as any) ? '' : targetRole);
  setDraftDifficulty(difficulty);
  setDraftSalary(salaryBand);
  setDraftDeadline(targetDeadline || '');
  setSettingsOpen(true);
}

function handleSettingsOpenChange(open: boolean) {
  setSettingsOpen(open);
  if (!open) {
    // discard drafts — do nothing to attempt / profile goal fields
  }
}
```

- [ ] **Step 1: Replace header button**

Remove the async abandon + `setPhase('setup')` handler (~lines 1684–1707). Replace with:

```tsx
<button
  type="button"
  disabled={!!busy}
  onClick={() => openSettings()}
  className="px-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:opacity-50 sm:px-0"
>
  设置
</button>
```

- [ ] **Step 2: Render sheet at end of train layout**

```tsx
<InterviewSettingsSheet
  open={settingsOpen}
  onOpenChange={handleSettingsOpenChange}
  targetRole={draftRole}
  customRole={draftCustomRole}
  difficulty={draftDifficulty}
  salaryBand={draftSalary}
  onTargetRole={setDraftRole}
  onCustomRole={setDraftCustomRole}
  onDifficulty={(d) => setDraftDifficulty(d as Difficulty)}
  onSalaryBand={setDraftSalary}
  onApplyGoal={() => { /* Task 4 */ }}
  targetDeadline={draftDeadline}
  onTargetDeadline={setDraftDeadline}
  onApplyDeadline={() => { /* Task 5 */ }}
  supportsPush={platform.push.supportsPush}
  pushEnabled={pushEnabled}
  pushFrequency={pushFrequency}
  pushTime={pushTime}
  onPushEnabled={(enabled) => void persistPushSettings({ push_enabled: enabled })}
  onPushFrequency={(frequency) =>
    void persistPushSettings({ push_frequency: frequency as PushFrequency })
  }
  onPushTime={(t) => {
    setPushTime(normalizePushTime(t));
    void persistPushSettings({ push_time: normalizePushTime(t) });
  }}
  onPushNow={() => void onPushNow()}
  pushNowBusy={pushNowBusy}
/>
```

Wire `persistPushSettings` carefully: today it reads `pushEnabled` from closure — when enabling from draft sheet, pass explicit patch (already supported).

- [ ] **Step 3: Manual check**

Boot with existing profile → train → 设置 opens sheet → close → same attempt still visible; no navigation to setup.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/InterviewPage.tsx
git commit -m "$(cat <<'EOF'
feat(interview): open settings sheet from train instead of setup page

EOF
)"
```

---

### Task 4: Apply goal + confirm dialog (立刻换题 / 稍后)

**Files:**
- Modify: `frontend/src/pages/InterviewPage.tsx`
- Uses: `AlertDialog` from `frontend/src/components/ui/alert-dialog.tsx`
- Uses: `goalCoreChanged`, `difficultyToLevel`

**Interfaces:**
- Produces page handlers:
  - `onApplyGoal()`
  - `confirmApplyGoalNow()`
  - `cancelApplyGoal()` // 稍后

```ts
const [goalConfirmOpen, setGoalConfirmOpen] = useState(false);

function resolvedDraftRole() {
  return (draftCustomRole.trim() || draftRole).trim();
}

function savedGoalCore(): GoalCore {
  return {
    targetRole: resolvedRole.trim(), // existing page helper
    difficulty,
    salaryBand,
  };
}

function draftGoalCore(): GoalCore {
  return {
    targetRole: resolvedDraftRole(),
    difficulty: draftDifficulty,
    salaryBand: draftSalary,
  };
}

async function onApplyGoal() {
  if (!resolvedDraftRole() || !draftSalary) return;
  if (!goalCoreChanged(savedGoalCore(), draftGoalCore())) {
    // no-op toast optional
    return;
  }
  if (attemptCtaKind(attempt?.status) === 'switch') {
    setGoalConfirmOpen(true);
    return;
  }
  await persistGoalAndMaybeStart({ switchQuestion: false });
}

async function persistGoalAndMaybeStart(opts: { switchQuestion: boolean }) {
  const nextLevel = difficultyToLevel(draftDifficulty);
  await updateInterviewProfile({
    target_role: resolvedDraftRole(),
    target_level: nextLevel,
    salary_band: draftSalary,
    // do NOT send draftDeadline here
  });
  setTargetRole(resolvedDraftRole());
  setDifficulty(draftDifficulty);
  setLevel(nextLevel);
  setSalaryBand(draftSalary);
  setGoalConfirmOpen(false);
  setSettingsOpen(false);
  if (opts.switchQuestion) {
    if (attempt && attemptCtaKind(attempt.status) === 'switch') {
      try {
        await abandonInterviewAttempt(attempt.id, 'switch_topic');
      } catch {
        // 409 terminal ok
      }
    }
    setAttempt(null);
    setFeedback(null);
    setAnswer('');
    setHintText(null);
    recentQuestionsRef.current = [];
    await enterTrain(nextLevel);
  }
}

function cancelApplyGoal() {
  // 稍后 = revert drafts to saved
  setDraftRole(ROLE_OPTIONS.includes(targetRole as any) ? targetRole : '');
  setDraftCustomRole(ROLE_OPTIONS.includes(targetRole as any) ? '' : targetRole);
  setDraftDifficulty(difficulty);
  setDraftSalary(salaryBand);
  setGoalConfirmOpen(false);
}
```

AlertDialog copy (zh):

- Title: 目标已更改
- Description: 将按新目标出新题，当前未完成的练习会被放弃。已提交的进度不受影响。
- Cancel: 稍后
- Action: 立刻换题 → `void persistGoalAndMaybeStart({ switchQuestion: true })`

- [ ] **Step 1: Implement handlers + dialog**
- [ ] **Step 2: Verify typecheck**
- [ ] **Step 3: Manual** — change role → 应用目标 → 稍后 → profile unchanged (reload settings shows old); attempt intact. Then 立刻换题 → new question, old abandoned.
- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/InterviewPage.tsx
git commit -m "$(cat <<'EOF'
feat(interview): confirm before applying goal changes that switch questions

EOF
)"
```

---

### Task 5: Deadline apply + rebalance confirm

**Files:**
- Modify: `frontend/src/pages/InterviewPage.tsx`

```ts
const [deadlineConfirmOpen, setDeadlineConfirmOpen] = useState(false);

function onApplyDeadline() {
  const next = draftDeadline || null;
  const saved = targetDeadline || null;
  if (next === saved) return;
  setDeadlineConfirmOpen(true);
}

async function confirmDeadline() {
  const next = draftDeadline || null;
  await updateInterviewProfile({ target_deadline: next });
  setTargetDeadline(next || '');
  setDeadlineConfirmOpen(false);
  // keep sheet open; force rebalance-aware refresh
  void refreshTodayPlan({ refresh: true });
}

function cancelDeadline() {
  setDraftDeadline(targetDeadline || '');
  setDeadlineConfirmOpen(false);
}
```

Dialog copy:

- Title: 更新日期并重排学习计划？
- Description: 将按新截止日期重排未完成学习日；已完成的学习日会保留。当前练习不受影响。
- Cancel: 取消
- Action: 保存并重排

Wire sheet `onApplyDeadline={onApplyDeadline}`.

- [ ] **Step 1: Implement**
- [ ] **Step 2: Manual** — change deadline → 保存并重排 → plan updates; attempt still same question
- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/InterviewPage.tsx
git commit -m "$(cat <<'EOF'
feat(interview): confirm deadline updates that rebalance the learning plan

EOF
)"
```

---

### Task 6: CTA —「换一题」confirm vs「生成面试题」

**Files:**
- Modify: `frontend/src/pages/InterviewPage.tsx`

**Behavior:**

```ts
const ctaKind = attemptCtaKind(attempt?.status);
const [switchConfirmOpen, setSwitchConfirmOpen] = useState(false);

async function onHeaderQuestionCta() {
  if (ctaKind === 'switch') {
    setSwitchConfirmOpen(true);
    return;
  }
  await enterTrain(level); // generate under current saved goal
}
```

Header button:

```tsx
<button
  type="button"
  disabled={!!busy}
  onClick={() => void onHeaderQuestionCta()}
  ...
>
  {ctaKind === 'switch' ? (
    <>
      <SkipForward ... />
      换一题
    </>
  ) : (
    <>生成面试题</>
  )}
</button>
```

Switch confirm:

- Title: 换一题？
- Description: 将放弃当前未完成的练习并抽取同主题新题。已提交进度不受影响。
- Cancel: 取消
- Action: 确认换题 → `void changeQuestion()` then close

- [ ] **Step 1: Implement CTA + dialog**
- [ ] **Step 2: Manual** — with active attempt only「换一题」+ confirm; after commit/abandon/null shows「生成面试题」and creates attempt without visiting setup
- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/InterviewPage.tsx
git commit -m "$(cat <<'EOF'
feat(interview): toggle generate vs switch-question CTA from attempt status

EOF
)"
```

---

### Task 7: i18n (9 locales)

**Files:**
- Modify: `frontend/src/i18n/locales/zh-CN.json` (and zh-TW, en, ja, ko, de, fr, es, ru)

Add under a sensible `interview` (or existing interview namespace if present — InterviewPage currently hardcodes many Chinese strings; **prefer introducing keys and switching new UI to `useTranslation`**, at minimum for strings added by this feature):

```json
"interviewNav": {
  "settings": "设置",
  "settingsHint": "提醒会自动保存。修改岗位/难度/薪资后请点「应用目标」。关闭抽屉会丢弃未应用的草稿。",
  "applyGoal": "应用目标",
  "applyDeadline": "应用截止日期",
  "generateQuestion": "生成面试题",
  "switchQuestion": "换一题",
  "goalChangedTitle": "目标已更改",
  "goalChangedBody": "将按新目标出新题，当前未完成的练习会被放弃。已提交的进度不受影响。",
  "applyGoalNow": "立刻换题",
  "applyGoalLater": "稍后",
  "deadlineTitle": "更新日期并重排学习计划？",
  "deadlineBody": "将按新截止日期重排未完成学习日；已完成的学习日会保留。当前练习不受影响。",
  "deadlineConfirm": "保存并重排",
  "deadlineCancel": "取消",
  "switchTitle": "换一题？",
  "switchBody": "将放弃当前未完成的练习并抽取同主题新题。已提交进度不受影响。",
  "switchConfirm": "确认换题",
  "switchCancel": "取消"
}
```

English (and others): provide natural equivalents. For non-EN/ZH, English fallback is acceptable if time-boxed, but fill all 9 files so keys exist.

Wire `InterviewSettingsSheet` + dialogs + header buttons to `t('interviewNav.*')`.

- [ ] **Step 1: Add keys to all 9 locale files**
- [ ] **Step 2: Replace hardcoded new strings with `t(...)`**
- [ ] **Step 3: Commit**

```bash
git add frontend/src/i18n/locales/*.json frontend/src/components/interview/InterviewSettingsSheet.tsx frontend/src/pages/InterviewPage.tsx
git commit -m "$(cat <<'EOF'
i18n: add interview settings drawer and confirm dialog strings

EOF
)"
```

---

### Task 8: Spec smoke checklist + final verification

**Files:** none required (optional: mark spec status to 已定稿)

- [ ] **Step 1: Run helper tests**

```bash
cd frontend && node --experimental-strip-types --test src/components/interview/interviewGoalDraft.test.ts
```

Expected: all pass

- [ ] **Step 2: Run through spec §7.2 manually** (checklist)

1. Incomplete profile → setup still works  
2. Open/close settings → attempt preserved  
3. Push toggle persists across refresh  
4. Goal apply → 稍后 → no profile change  
5. Goal apply → 立刻换题 → new attempt  
6. No active attempt → apply goal saves without dialog; 生成面试题 works  
7. Deadline confirm rebalances; attempt kept  
8. 换一题 confirm works  

- [ ] **Step 3: Update design doc status line to `已定稿` if user already approved**

- [ ] **Step 4: Commit only if doc status changed**

```bash
git add docs/superpowers/specs/2026-07-23-interview-settings-drawer-design.md
git commit -m "$(cat <<'EOF'
docs: mark interview settings drawer spec as finalized

EOF
)"
```

---

## Spec coverage (self-check)

| Spec requirement | Task |
| --- | --- |
| Setup first-time only | Task 3 (remove train→setup) + boot unchanged |
| Right Sheet settings | Task 2–3 |
| Push auto-save | Task 3 |
| Goal confirm; 稍后=revert | Task 4 |
| Deadline confirm only | Task 5 |
| CTA switch/generate | Task 6 |
| 改目标→设置 | Task 3 |
| Draft discard on close | Task 3 |
| 补充简历 independent | unchanged header |
| i18n | Task 7 |
| Pure helper tests | Task 1 |
| No backend pending goal | honored |

## Placeholder scan

No TBD / “implement later” left in tasks. Task 5 uses existing `refreshTodayPlan({ refresh: true })` on `InterviewPage`.
