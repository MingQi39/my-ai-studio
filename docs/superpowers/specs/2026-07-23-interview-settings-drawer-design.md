# 面试训练：设置抽屉 + 首次引导分离（方案 1）设计规格

**日期**：2026-07-23  
**状态**：已定稿并实施中  
**模块**：Interview Navigator · Setup / Train  
**路径选择**：方案 1（前端状态机拆分；设置用右侧 Sheet；后端 API 基本不动）  
**关联**：消除「改目标 → 整页 setup → 误 abandon 当前题」摩擦；日常配置留在练题页

---

## 1. 背景与目标

当前练题顶栏「改目标」会先 `abandon` 未闭环 attempt，再切到整页 setup（「先定目标，再出题」）。推送、截止日期等也主要挂在 setup。用户即使**不改**目标、只想调提醒或再点生成，也被迫来回切换，且会丢掉进行中的题。

### 1.1 本规格范围

- Setup 整页**仅用于首次**（profile 目标不齐：缺 role / level / salary 等现有 boot 判定）
- 练题页「改目标」改为「设置」，打开**右侧 Sheet 抽屉**，人留在 `phase=train`
- 目标字段（岗位 / 难度 / 薪资）本地草稿；**关抽屉丢草稿**；落库仅在用户确认「立刻换题」
- 提醒（开关 / 频率 / 时间）在抽屉内**改完即保存**（沿用现有 `persistPushSettings`）
- 截止日期：改完后单独确认「是否按新截止日期重排学习计划」；**不**触发换题确认
- 出题 CTA：有进行中 attempt →「换一题」（确认放弃）；无 →「生成面试题」
- 「补充简历」保持顶栏独立入口，不进设置

### 1.2 明确不在本规格

- 后端 pending goal / 草稿表
- 独立路由 `/interview/settings`
- 改 Attempt FSM、评估、复习卡、学习讲义内容生成
- 多 profile / 多目标并行
- 把 setup 整页删掉（首次仍需要）

### 1.3 成功标准

1. 已有完整目标的用户，日常练题**几乎不再进入**整页 setup。
2. 打开设置再关闭（未确认换题）**不会** abandon 当前题。
3. 改提醒 / 频率 / 时间即保存，无需回 setup。
4. 改岗位/难度/薪资时出现确认；选「稍后」= 撤销修改；选「立刻换题」才落库并出新题。
5. 改截止日期只问是否重排计划，不问换题。
6. 已 committed 的进度 / 复习卡 / 学习计划已完成日行为与现网一致（本规格不削弱）。

---

## 2. 决策记录（Grill 锁定）

| # | 决策 |
| --- | --- |
| 路径 | C：setup = 首次引导；之后配置在练题「设置」 |
| 目标变更 | B：确认「立刻换题 / 稍后」 |
| 「稍后」语义 | B：撤销本次目标修改，**不落库** |
| 提醒 / 截止日期 | C：提醒自动保存；截止日期单独确认是否重排计划 |
| UI | A：右侧抽屉（Sheet `side="right"`） |
| 首次 | A：保留现有整页 setup；完成后进 train；之后只走设置 |
| 出题 CTA | B：有进行中 →「换一题」；无 →「生成面试题」 |
| 截止日期 vs 换题 | C：截止日期不算换题触发；只提示重排计划 |
| 旧按钮 | A：「改目标」文案改为「设置」 |
| 抽屉初值 | A：始终已保存 profile；关抽屉丢未确认草稿 |
| 简历 | A：补充简历独立入口 |
| 成功标准 | D：以上都要 |

---

## 3. 信息架构与页面流

### 3.1 Phase 规则（不变 + 收敛）

| Phase | 何时进入 | 说明 |
| --- | --- | --- |
| `loading` | boot | 现有 |
| `setup` | boot 发现目标不齐；**禁止**从 train 因「设置」进入 | 首次引导 |
| `import` / `confirm` | 补充简历 / 确认 claims | 现有；顶栏「补充简历」仍可 `setPhase('import')` |
| `train` | 目标齐全后的主界面 | 设置抽屉叠在 train 之上，**不改变 phase** |

### 3.2 主路径

```text
boot
 ├─ 目标齐全 → enterTrain（可 resume active）
 └─ 目标不齐 → setup
      └─「生成面试题并开始」→ updateProfile + enterTrain

train
 ├─「设置」→ 打开 Sheet（草稿 = 已保存值）
 │    ├─ 提醒控件 onChange → persistPushSettings（即时）
 │    ├─ 截止日期 onChange → 本地草稿；失焦/点「应用截止日期」→ 截止日期确认框
 │    └─「应用目标」→ 若目标字段相对已保存有变：
 │         ├─ 有非终端 attempt → 换题确认框
 │         │    ├─ 立刻换题 → updateProfile(目标) + abandon + createAttempt + 关抽屉
 │         │    └─ 稍后 → 草稿重置为已保存；关确认框；抽屉可继续开着或关（见 §4.2）
 │         └─ 无进行中 attempt → 直接 updateProfile(目标)；可选提示「已保存，可点生成面试题」
 ├─「换一题」→ 确认放弃当前 → abandon + createAttempt（目标不变）
 ├─「生成面试题」→ 仅当无进行中 attempt → createAttempt / enterTrain 路径
 └─「补充简历」→ phase=import（不 abandon）
```

### 3.3 设置抽屉内容块（自上而下）

1. **目标**：岗位 chips + 自定义输入、难度、薪资（复用 setup 现有控件与文案结构）
2. **截止日期**：date input + 简短说明（剩余天数 → 学习路径）
3. **学习提醒**：开关、频率、时间、「立即推送」（可保留顶栏「立即推送」或只留一处；**本规格默认：顶栏与抽屉均可触发同一 `onPushNow`，避免找不到**）
4. 页脚：「应用目标」主按钮；无「保存全部」（提醒已即时保存）

**不放入抽屉：** 补充简历、生成简历、今日学习文档入口（顶栏已有）。

---

## 4. 交互细则

### 4.1 目标字段定义（触发换题确认）

比较对象（与现有 `goalStillMatches` / 后端 `active_attempt_matches_goal` 对齐）：

- `target_role`（含自定义输入归一后的字符串）
- `target_level` / 前端 difficulty 映射后的 level
- `salary_band`

**不含：** `target_deadline`、push_*。

「有变」：相对**服务端已保存 profile**（打开抽屉时快照或当前 React 中已同步的 profile），草稿三者任一不同。

### 4.2 换题确认框

- **标题**：目标已更改  
- **正文**：将按新目标出新题，当前未完成的练习会被放弃（已提交的进度不受影响）。  
- **主按钮**：立刻换题  
- **次按钮**：稍后  

**稍后：**

1. 不调用 `updateInterviewProfile` 写目标字段  
2. 抽屉内目标草稿重置为已保存值  
3. 关闭确认框；**默认保持抽屉打开**（用户可继续改提醒），当前 attempt 不动  

**立刻换题：**

1. `updateInterviewProfile` 写入新 role/level/salary（及当时草稿里的 deadline，若已通过截止日期流程落库则用已保存值；若截止日期仍是未确认草稿，**本规格：应用目标时不捎带未确认的 deadline**，避免绕过截止日期确认）  
2. 若有非 `committed`/`abandoned` attempt → `abandonInterviewAttempt(..., 'switch_topic')`（或新增 reason `goal_changed`，可选；一期可用现有 `switch_topic`）  
3. 清空本地 answer/feedback；`createInterviewAttempt` / `loadTraining` / `enterTrain` 等价路径出新题  
4. 关闭确认框与抽屉  

### 4.3 截止日期确认框

- **触发：** 用户更改 date 且与已保存不同后，点「应用截止日期」或等价明确动作（避免每个按键弹窗；**禁止**仅 onBlur 自动弹若易误触——推荐显式按钮）  
- **标题**：更新日期并重排学习计划？  
- **正文**：将按新截止日期重排未完成学习日；已完成的学习日会保留。  
- **主按钮**：保存并重排  
- **次按钮**：取消（草稿重置为已保存 deadline）  

**保存并重排：** 调用现有 `updateInterviewProfile({ target_deadline })`（后端已有 deadline 变化 → `generate_learning_plan` / rebalance）。不 abandon attempt。

### 4.4 提醒即时保存

与现有 setup 行为一致：`push_enabled` / `push_frequency` / `push_time` 变更即 `persistPushSettings`。失败 Toast，控件可回滚到上次成功值。

### 4.5 出题 CTA

| 条件 | 按钮文案 | 行为 |
| --- | --- | --- |
| 存在非终端 attempt（`open\|answering\|evaluated\|reanswered\|degraded`） | 换一题 | 确认：「放弃当前题并换一题？」→ 是则现有 `changeQuestion()` |
| 无上述 attempt（含 null、committed、abandoned） | 生成面试题 | `enterTrain` / `createInterviewAttempt`，**不**进 setup |

首次 setup 页保留「生成面试题并开始」文案即可。

### 4.6 关抽屉

- `onOpenChange(false)`：丢弃目标与未应用截止日期草稿；重置为已保存；若换题确认开着一并关  
- **不** abandon、**不**写目标  

### 4.7 从 train 禁止再「改目标进 setup」

删除/替换现有「改目标」handler 中的 `abandon` + `setPhase('setup')`。唯一进 setup 的路径：boot 目标不齐。

---

## 5. 架构与数据流

### 5.1 原则

- **无新后端实体**；继续用 `GET/PATCH` profile、attempt create/abandon、learning plan 副作用  
- 纯函数抽出「是否目标变更 / 是否该弹确认」，便于单测  
- UI：`InterviewSettingsSheet` 组件；`InterviewPage` 编排确认框与 API

### 5.2 建议纯函数（前端）

```ts
// frontend/src/components/interview/interviewGoalDraft.ts

export type GoalCore = {
  targetRole: string;
  targetLevel: string; // 或 difficulty；与页面统一一种
  salaryBand: string;
};

export function normalizeGoalCore(g: GoalCore): GoalCore;
export function goalCoreEquals(a: GoalCore, b: GoalCore): boolean;
export function goalCoreChanged(saved: GoalCore, draft: GoalCore): boolean;
```

截止日期：简单 `savedDeadline !== draftDeadline`（ISO date 字符串或 null）。

### 5.3 组件边界

| 单元 | 职责 | 不负责 |
| --- | --- | --- |
| `InterviewSettingsSheet` | 渲染三块表单；把草稿 onChange / 即时 push /「应用目标」「应用截止日期」事件抛出 | 直接 abandon / 出题 |
| `InterviewPage` | open 状态、saved vs draft、两个 AlertDialog、调用 API、出题 CTA 文案切换 | 复制一整份 setup JSX 长期分叉——应从 setup 抽共享控件或 props 化 |
| `interviewGoalDraft.ts` | 比较与归一 | UI |

### 5.4 与 resume / progress 的关系

- Committed attempts、review cards、progress 现算逻辑不变  
- Abandoned 题仍不计入进度（与现网一致）  
- 「立刻换题」与今日「换一题」对进度的影响相同：丢掉未闭环，保留已闭环  

---

## 6. i18n

- 新增/替换键：`interview.settings`、确认框标题/正文/按钮、「生成面试题」、「应用目标」、「应用截止日期」等  
- 至少更新 `zh-CN.json` + `en.json`；其余语言可先英文占位或与现有 interview 键同批补齐（跟仓库惯例：九语都改）  
- 删除或弃用「改目标」文案键若存在  

---

## 7. 测试计划

### 7.1 单元（必做）

- `goalCoreChanged`：同值 / 改 role / 改 level / 改 salary / 空白归一  
- （可选）CTA 文案选择纯函数：`hasActiveAttempt(status) → 'switch' | 'generate'`

### 7.2 手工 / 冒烟（必做）

1. 新用户（无 profile 目标）→ 仍见整页 setup → 开始后进 train  
2. train 开设置再关 → 当前题仍在，答案草稿仍在  
3. 只改提醒 → 刷新后仍生效；当前题未 abandon  
4. 改目标点应用 → 确认 → 稍后 → profile 未变、题仍在、草稿恢复  
5. 改目标 → 立刻换题 → 新题、旧 attempt abandoned、profile 已更新  
6. 无进行中题时改目标应用 → 直接保存，可点「生成面试题」  
7. 改截止日期 → 保存并重排 → 计划更新、当前题仍在  
8. 「换一题」确认后换题；「生成面试题」仅在无 active 时出现  

### 7.3 后端

- 无新 API 时可不加后端测试；若为 `abandon` 增加 `goal_changed` reason，补一行枚举/校验测试  

---

## 8. 风险与缓解

| 风险 | 缓解 |
| --- | --- |
| InterviewPage 过大更难改 | 抽出 Sheet + goal draft 纯函数；设置表单尽量共享 |
| 用户以为改目标已自动保存 | 「应用目标」主按钮 + 关抽屉丢草稿的轻提示（抽屉顶一句） |
| 截止日期与目标同时改 | 规格：应用目标不捎带未确认 deadline；先应用 deadline 或先应用目标，顺序由用户显式操作 |
| Electron 推送与 Web | 沿用 `platform.push` / `persistPushSettings`；抽屉内无推送能力时隐藏块（与 setup 一致） |

---

## 9. 实现顺序建议

1. 纯函数 + 单测  
2. `InterviewSettingsSheet` + 接入「设置」打开（暂不删旧逻辑）  
3. 换题确认 / 稍后撤销；去掉 abandon+setup  
4. 截止日期确认；提醒即时保存迁入抽屉  
5. CTA「换一题 / 生成面试题」切换  
6. i18n + 冒烟  
7. 清理 setup 中与 train 重复的「仅日常配置」引导文案（可选收紧）  

---

## 10. 开放问题（实现时可默认）

- abandon reason 用 `switch_topic` 即可，不必新枚举。  
- 抽屉宽度：现有 Sheet `sm:max-w-sm` 可能偏窄装目标 chips → 实现时用 `sm:max-w-md` 或 `max-w-lg` 覆盖 className。  
- 顶栏「立即推送」保留，避免只藏在抽屉里。  
