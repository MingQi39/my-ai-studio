# 面试导航：训练闭环 / 可恢复 / 复习卡 / Trace 设计规格

**日期**：2026-07-21  
**状态**：已定稿（用户确认直接实施）  
**模块**：Interview Navigator  
**路径选择**：方案 B（实体表为主 + 可选事件日志）  
**灵感来源**：InkOS 输入治理 / 审稿闭环 / hooks 债务模型（仅原则，不复制 AGPL 代码）

---

## 1. 背景与目标

当前面试导航已具备：目标先行（岗位/难度/薪资）、可选简历 claim、三栏训练台、关键词式评估、复习卡落库。缺口是：

1. 没有权威的「一题一次」`TrainingAttempt`，刷新即丢进度；
2. 完成态未强制「断点后重答」，与 PRD 北极星不一致；
3. 评估失败会与成功路径混在同一 `busy/error` 体验，且可能误写复习卡；
4. 复习卡只有创建、无生命周期与到期；
5. 评估结果非结构化 Trace，无法审计规则版本 / 降级原因。

### 1.1 本规格范围（用户选项 3）

- 训练闭环状态机（`TrainingAttempt` + Answer v1/v2）
- 会话可恢复（刷新后继续未完成 attempt）
- 复习卡生命周期（轻量调度，非完整 FSRS）
- 结构化 `EvaluationTrace`（本轮以确定性规则为主；LLM 评估接口预留）

### 1.2 明确不在本规格

- 直接集成 / 复制 InkOS 源码（AGPL-3.0）
- 主界面改成 Chat
- 完整事件溯源投影引擎
- FSRS/SM-2 完整间隔重复
- 真实 LLM 多维评分落地（仅 schema 与 `llm: null` 占位）
- 简历原文持久化、思维链落盘

### 1.3 成功标准

- 用户提交首答 → 看到断点 → 提交重答（或全覆盖直达）→ `committed`，可计入北极星；
- 刷新页面后，若有 `open|answering|evaluated|reanswered|degraded` 未终态 attempt，自动恢复题目与答案草稿；
- 评估异常 → `degraded`：答案保留，不创建/不推进复习卡，不更新能力画像；
- 复习卡具备 `status` / `next_due_at`，列表可区分到期与新卡；
- 每次成功评估写入可序列化 Trace（规则版本 + 命中信号）。

---

## 2. 领域模型

```text
InterviewProfile（已有）
 ├─ InterviewClaim[]（已有）
 ├─ TrainingAttempt[]          # 新增
 ├─ InterviewSessionEvent[]    # 新增
 └─ InterviewReviewCard[]      # 扩展字段
```

### 2.1 `TrainingAttempt`

权威实体：一题一次训练闭环。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID | 主键 |
| `profile_id` | FK | 归属 profile |
| `topic` | str | 主题 |
| `question` | text | 题干快照 |
| `level` | P5/P6/P7 | 深度 |
| `focus_node` | str | 当前焦点节点 |
| `route_nodes` | JSON list | 出题时冻结的 Answer Route |
| `atlas` | JSON list | 知识地图片段 |
| `category` | skill/project/role | 题目类别 |
| `goal_snapshot` | JSON | `{target_role, target_level, salary_band}` |
| `source_claim_ids` | JSON list | 经历题依据；无简历可 `[]` |
| `status` | enum | 见 §3 |
| `answers` | JSON | `[{version: 1\|2, text, created_at}]` |
| `evaluation` | JSON \| null | 最近一次 **成功** 评估 Trace；失败不覆盖 |
| `hint_level` | int 0–4 | 已展示提示层 |
| `review_card_id` | UUID \| null | committed 时关联 |
| `degraded_reason` | str \| null | 仅 degraded |
| `created_at` / `updated_at` | datetime | 时间戳 |

**答案版本**：内嵌在 `answers` JSON，不单独建表（MVP）。v1 = 首答，v2 = 重答；本轮最多保留到 v2。

### 2.2 `InterviewSessionEvent`

辅助审计与恢复线索；**不以**事件重放为唯一真相（真相在 Attempt 行）。

| 字段 | 说明 |
| --- | --- |
| `id`, `profile_id`, `attempt_id` | 关联 |
| `seq` | profile 内单调递增 |
| `type` | 见下 |
| `payload` | 小 JSON：版本号、节点名、status；**禁止**简历原文 |
| `created_at` | 时间 |

事件类型：

- `attempt_started`
- `answer_submitted`（含 `version`）
- `evaluation_completed` / `evaluation_failed`
- `hint_shown`（含 `level`, `node`）
- `attempt_committed` / `attempt_abandoned`

并发：同一 profile 用 DB 事务 + `SELECT … FOR UPDATE` 取下一 `seq`，或 `UNIQUE(profile_id, seq)`。

### 2.3 `InterviewReviewCard` 扩展

保留：`topic`, `question`, `answer`, `missing_nodes`, `created_at`。

新增：

| 字段 | 说明 |
| --- | --- |
| `status` | `new \| learning \| reviewing \| deferred \| mastered \| invalidated` |
| `attempt_id` | 来源 attempt（可空兼容旧数据） |
| `last_reviewed_at` | 上次回访 |
| `next_due_at` | 下次到期；创建时默认 `now + 1 day` |
| `successful_recall_count` | 成功召回次数，默认 0 |
| `source_claim_ids` | JSON list，可空 |

本轮调度规则（轻量）：

- 闭环 `committed` 且仍有 `missing_nodes` → 创建卡，`status=new`，`next_due_at=now+1d`
- 全覆盖 committed → **可不创建**复习卡（或创建 `mastered` 归档卡，默认不创建）
- `degraded` / `abandoned` → **不创建、不推进**卡
- 回访 API（可选 MVP）：标记 `learning` 并刷新 `next_due_at`；完整 FSRS 后续再做

### 2.4 `EvaluationTrace`（嵌在 `attempt.evaluation`）

```json
{
  "covered_nodes": ["Position", "Mechanism"],
  "missing_nodes": ["Trade-off", "Evidence"],
  "breakpoint": "Trade-off",
  "hint": { "node": "Trade-off", "recall": "...", "keywords": "...", "example": "..." },
  "next_step": "补一个权衡点后再答",
  "complete": false,
  "deterministic": {
    "rule_version": "interview-eval-v1",
    "signals_hit": { "Position": ["场景"], "Mechanism": ["怎么"] }
  },
  "llm": null,
  "status": "ok",
  "evaluated_at": "ISO-8601"
}
```

降级示例：`status: "degraded"`, `reason: "evaluator_exception"`；该对象写入事件 `evaluation_failed`，**不**写入 `attempt.evaluation`（保留上一份 ok trace，若无则 null）。

---

## 3. 状态机

```text
open
  → answering      # 收到 v1 提交（或用户开始作答的显式 start，可选）
  → evaluated      # 评估 ok
  → reanswered     # 收到 v2
  → committed      # 闭环落盘（复习卡按规则）

评估抛错 / 解析失败 → degraded
用户换题或放弃     → abandoned
```

### 3.1 合法转移

| From | To | 触发 |
| --- | --- | --- |
| — | `open` | `POST /training/attempts`（出题并建 attempt） |
| `open` | `answering` | 提交 answer v1 |
| `answering` | `evaluated` | 评估成功 |
| `answering` | `degraded` | 评估失败 |
| `evaluated` | `reanswered` | 提交 answer v2 |
| `evaluated` | `committed` | `complete=true` 且用户确认结束（或自动） |
| `evaluated` | `abandoned` | 用户跳过重答 / 换题 |
| `reanswered` | `committed` | 二次评估完成（成功）后提交闭环 |
| `reanswered` | `degraded` | 二次评估失败 |
| `degraded` | `abandoned` | 用户放弃 |
| `degraded` | `answering` | 用户用同一题重试评估（可选；MVP 允许重新提交当前版本文本） |

终态：`committed` | `abandoned`。`degraded` 视为可恢复非终态（可重试或放弃）。

### 3.2 完成态（北极星）

计入「闭环成功」当且仅当 `status=committed`，且满足其一：

1. 存在 answer v2；或
2. 首评 `complete=true`（五节点按 level 要求全覆盖）

「只看反馈不重答」必须走 `abandoned`，**不计入**闭环。

---

## 4. API 设计

前缀保持 `/api/v1/interview`。旧无状态接口可保留作兼容，新 UI 走 attempt API。

### 4.1 新建并出题

`POST /training/attempts`

- Query/body：可选 `topic`；`level` 可省略（用 profile）
- 行为：若存在非终态 attempt → **409** 或返回现有（推荐：返回现有 + `resumed: true`，避免双开）
- 否则：调用现有出题逻辑，插入 `open` attempt，写 `attempt_started`
- 响应：`TrainingAttemptResponse`（含题目字段 + status + answers）

### 4.2 恢复

`GET /training/attempts/active`

- 返回当前用户最新非终态 attempt，或 `204/null`
- 前端进入 `train` 时先调此接口

`GET /training/attempts/{id}`  
`GET /training/attempts?limit=`（历史，可选 MVP）

### 4.3 提交答案

`POST /training/attempts/{id}/answers`

```json
{ "text": "...", "version": 1 }
```

规则：

- v1：仅 `open`（或重试中的 degraded）
- v2：仅 `evaluated`
- 写入 `answers`，状态 → `answering`（v1）或 `reanswered`（v2），事件 `answer_submitted`
- 随后服务端同步跑评估（同一请求返回评估结果，减少前端往返）

响应：`{ attempt, evaluation | null, degraded: bool }`

### 4.4 提示

`POST /training/attempts/{id}/hints` `{ "level": 2 }`

- 校验 attempt 非终态；更新 `hint_level`；事件 `hint_shown`
- 复用现有 `hint_for`

### 4.5 提交闭环 / 放弃

`POST /training/attempts/{id}/commit`

- 校验 §3.2；创建复习卡（若需要）；`committed`；事件 `attempt_committed`

`POST /training/attempts/{id}/abandon` `{ "reason": "skip_retry" | "switch_topic" }`

- `abandoned`；不写卡；事件 `attempt_abandoned`

### 4.6 复习卡

- `GET /review-cards`：增加 `status`, `next_due_at`, …；支持 `?due=1` 过滤到期
- `PATCH /review-cards/{id}`：更新 status / 标记已复习（轻量）
- 创建改由 `commit` 服务端完成；前端「保存复习卡」按钮改为「完成并保存」→ `commit`（避免双写）

### 4.7 兼容

现有 `GET /training/next`、`POST /training/evaluate`、`POST /training/hint`、`POST /review-cards`：

- **短期保留**，标记 deprecated
- 新页面不再调用 evaluate/hint/create-card 独立路径

---

## 5. 服务层行为

### 5.1 出题

复用 `InterviewService.next_training_prompt` 逻辑，但结果写入 Attempt，而不是只返回 DTO。`goal_snapshot` 从 profile 冻结。经历题：`source_claim_ids` = 本次选用的 confirmed claim ids。

### 5.2 评估

1. try：现有 `evaluate_answer` → 组装 Trace（`rule_version=interview-eval-v1`，附 `signals_hit`）
2. except：写 `evaluation_failed` 事件，attempt → `degraded`，**不**改 `evaluation` 字段，不写卡
3. 成功：写 `evaluation`，`evaluated` 或（若已是 reanswered 路径）准备 commit

v2 提交后再次评估：比较 covered 是否提升（可选展示 delta）；无论是否提升，允许用户 `commit`（MVP 不强制净提升门槛；InkOS 的 +3 分规则留给 LLM 阶段）。

### 5.3 事务

`answer` + `evaluate` + `event` 同事务；`commit` + `review_card` + `event` 同事务。失败整单回滚。

---

## 6. 前端行为

### 6.1 进入训练

1. `GET /training/attempts/active`
2. 有 → 恢复题目、答案框（最新 version 文本）、feedback（若有 evaluation）、hint_level
3. 无 → 用户点「下一题」→ `POST /training/attempts`

### 6.2 作答 UI 状态

| Attempt status | UI |
| --- | --- |
| `open` / `answering` | 可编辑；主按钮「提交回答」→ answers v1 |
| `evaluated` | 展示 Trace 断点；输入框清空或保留由产品定（推荐清空并 placeholder「针对断点重答」）；主按钮「提交重答」；次按钮「跳过（不计入闭环）」→ abandon |
| `reanswered` | 展示覆盖 delta；主按钮「完成并保存复习卡」→ commit |
| `committed` | 只读摘要 +「下一题」 |
| `degraded` | 错误分层：「评估暂时不可用，答案已保存」；可重试提交 / 放弃 |
| `abandoned` | 提示未计入闭环 + 「下一题」 |

### 6.3 Busy / Error 拆分

- `busy`: `submitting | evaluating | hinting | committing | loading`（枚举，非单一 boolean）
- `error`: `{ scope, message }`；degraded 用 warning 样式，不与网络错误混用

### 6.4 复习卡抽屉（MVP）

右侧或底部抽屉列出卡：到期优先；点击可「从该卡出题」（建新 attempt，topic/missing 继承）。本轮可做列表+到期标记；完整抽屉编辑可第二迭代。

---

## 7. 数据迁移

新 Alembic revision，例如 `add_interview_training_attempts`：

1. 表 `interview_training_attempts`（全字段）
2. 表 `interview_session_events`（含 `uq_interview_events_profile_seq`）
3. `interview_review_cards` 加列：`status`（default `new`）、`attempt_id`（nullable FK）、`last_reviewed_at`、`next_due_at`（nullable）、`successful_recall_count`（default 0）、`source_claim_ids`（JSON default `[]`）
4. 旧卡：`status=new`，`next_due_at=created_at+1d`（数据回填在 upgrade 中）

---

## 8. 测试计划

### 后端单测 / 服务测

- 状态机非法转移拒绝
- v1→evaluated→v2→commit 成功并建卡
- `complete=true` 可无 v2 直接 commit
- 跳过重答 → abandoned，无卡
- evaluate 抛错 → degraded，无卡，evaluation 字段不变
- `GET active` 恢复非终态；终态不返回
- 双开出题：返回已有 active，不建第二条

### 前端冒烟

- 刷新后恢复 evaluated 状态与断点文案
- degraded 显示警告而非空白
- commit 后复习卡列表出现新卡且带 due

### 不做本轮

- LLM 评估一致性集
- 完整事件重放重建 Attempt

---

## 9. 实施顺序（建议）

1. Migration + ORM + schemas
2. Service：attempt CRUD、状态转移、事件写入
3. API 路由挂载
4. 评估 Trace 组装 + degraded 路径
5. commit 创建复习卡（生命周期字段）
6. 前端：active 恢复 + busy 拆分 + 强制重答 UX
7. 复习卡列表 due 过滤；deprecate 旧 evaluate 调用
8. 单测补齐

---

## 10. 风险与假设

- **假设**：单用户同时仅一个 active attempt 足够；多标签页以后者 409/复用策略为准。
- **假设**：答案原文可存 DB（已有 review card answer）；仍不存简历原件与 CoT。
- **风险**：旧前端若仍调 `POST /review-cards` 会与 commit 双写——上线时改前端并文档标注。
- **风险**：关键词评估质量仍有限；Trace 先保证可替换为 LLM，不在本轮承诺评分准确度。

---

## 11. 规格自检

- [x] 无 TBD/占位未决（LLM 明确为 null 占位）
- [x] 与 PRD 北极星「答→断点→重答」一致
- [x] 与方案 B（实体为主）一致；事件非唯一真相
- [x] 未引入 AGPL 代码依赖
- [x] 范围含选项 3 四块；FSRS/纯事件源排除
- [x] 迁移与兼容策略已写

---

## 12. 审阅清单（请你确认）

1. 全覆盖是否允许无 v2 直接 `committed`？（规格默认：**允许**）
2. 刷新恢复时答案框：恢复上次文本，还是 evaluated 后强制空重答？（规格默认：**evaluated 后清空鼓励重答；open/degraded 恢复原文**）
3. 本轮是否要做复习卡「回访 PATCH」，还是只做创建+列表 due？（规格默认：**列表 due + 可选 PATCH 最小实现**）

确认本文件后，再进入 `writing-plans` 拆实施计划。
