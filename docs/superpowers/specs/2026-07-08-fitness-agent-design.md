# Fitness Agent 设计规格

**日期**：2026-07-08  
**状态**：已定稿  
**模块代号**：`fitness`

---

## 1. 背景与目标

Qi 的 AI Studio 已有基于原生 ReAct 实现的「旅行规划 Agent」。本规格定义一个**独立的健康/减脂 Agent**，使用 **LangChain** 实现，与旅行 Agent 形成技术栈对照（原生 vs LangChain）。

### 1.1 第一版核心能力（Feature A）

1. **记账**：用户用自然语言记录餐食 → Agent 解析菜品与分量 → 按热量链路计算 → 写入今日日记 → 对照每日目标展示已摄入/剩余。
2. **推荐**：用户不知道吃什么时 → 按剩余配额/预算热量/简单偏好给出 2–3 个候选方案 → 每项带分项热量与来源 → 用户确认后可选入账。

### 1.2 后续能力（不在第一版）

- **Feature B**：身体档案 + BMR/TDEE 自动计算每日配额与减脂周计划。
- 图片识餐、条码扫描、运动消耗、体重曲线等。

### 1.3 成功标准

- 侧边栏独立入口，与主聊天、旅行 Agent 平级。
- LangChain tool-calling Agent 能自主选工具完成记账、查今日、改目标、推荐餐食。
- 每条食物热量带 `source` 标签（`local` / `usda` / `estimate`），估算项 UI 强制可见。
- 同一用户跨刷新可恢复「今日」数据。
- 共用现有 BYOK 模型配置与 JWT 登录体系。
- 能完成「晚饭不知道吃什么，剩余约 600 kcal」类推荐，并给出可对比的热量数字。

---

## 2. 产品范围

### 2.1 用户流程

**记账**
1. 设置（或沿用）每日热量目标，例如 1800 kcal。
2. 输入：「午饭吃了米饭一碗、番茄炒蛋、半瓶可乐」。
3. Agent 返回分项热量 + 来源标签 + 今日汇总。
4. 可维护日记：「今天还剩多少？」「删掉刚才可乐」。

**推荐**
1. 触发：「晚饭不知道吃什么」「帮我推荐 500 大卡内的午餐」。
2. 约束：自动带入今日剩余；用户也可指定预算热量与简单偏好（少油/素食/便宜/方便）。
3. 输出：2–3 套候选，每套含菜名、分量、分项 kcal、来源、合计。
4. 用户说「记第 2 套」后才调用 `log_meal`；**推荐默认不自动入账**。

### 2.2 输入方式

- **第一版**：文字对话为主。
- **第二迭代**：图片识餐（解析菜名/分量草稿 → 用户确认 → 走同一热量链路）。

### 2.3 配额模型

- 用户**手动设置**每日热量目标（如 1800 kcal）。
- 不做 BMR/TDEE 公式（留给 Feature B）。
- 今日已摄入、剩余由按日日记汇总。

### 2.4 持久化

- 按 `user_id + date` 落库，跨会话、跨刷新有效。
- 聊天历史存 `session_type=fitness` 会话；日记以专用表为准，不只靠聊天记录。

### 2.5 明确不做（第一版）

- 图片识别餐盘。
- BMR/TDEE、身体档案、完整减脂周计划。
- 医疗诊断、慢病处方、强制宏量营养素配比。
- 条码扫描、餐馆菜单库、Apple Health 同步。
- 一周食谱、外卖点单。
- 与旅行 Agent 的对比模式、完整 ReAct 四步可视化。

### 2.6 合规口径

- 定位为生活方式记录与估算工具，**非医疗建议**。
- UI 与 Agent 回复需含固定免责声明。
- 不处理极端节食诱导；可简短拒答并引导关注健康。

---

## 3. 技术方案

### 3.1 方案选型

**采用：LangChain Tools + Agent（方案 1）**

- 使用 LangChain tool-calling agent 编排。
- 工具拆分为：解析/查热量、写日记、读今日摘要、改目标、推荐餐食。
- 与现有 BYOK、SSE、JWT 对齐；作品集能展示「LangChain Agent + Tools」。

**不采用**
- LangGraph 状态机（第一版过重，Feature B 再考虑）。
- 薄 LCEL 固定流水线（Agent 味不足，与旅行 ReAct 对比弱）。

### 3.2 架构

```
Sidebar
  ├─ 主聊天工作台
  ├─ 旅行规划 Agent   (原生 ReAct)
  └─ Fitness Agent    (LangChain)   ← 新增

Frontend: features/fitness/
Backend:  app/fitness/ + api/v1/fitness.py
```

**分层**

| 层 | 职责 | 边界 |
|----|------|------|
| UI 工作台 | 对话、今日面板、目标设置、推荐候选卡片 | 不直接算热量 |
| API | `/api/v1/fitness/*`，JWT；SSE 流式 | 避开现有 `/api/v1/health` 探活路由 |
| LangChain Agent | 选工具完成记账/查今日/改目标/推荐 | 不硬编码查库顺序以外的业务 |
| Tools | 本地库、USDA、日记 CRUD、目标读写、推荐校验 | 纯函数/服务，可单测 |
| 数据 | 用户目标、按日餐次日记、fitness 会话 | 与 travel 数据隔离 |
| 共享 | 认证、用户模型配置、加密 Key | 不复制 BYOK |

**与旅行模块对齐**

| 对齐 | 不对齐 |
|------|--------|
| 侧边栏入口、JWT、BYOK、SSE、session_type | 对比模式、ReAct 四步时间线 |
| 会话列表复用主站能力 | 工具台独立页（第一版不做） |

---

## 4. 热量解析链路

单条食物统一走以下降级链：

1. **规范化**：菜名、分量、单位（碗/克/份）。
2. **本地中文小库**命中 → `source=local`。
3. 未命中 → **USDA FoodData Central**（需 `USDA_FDC_API_KEY`，可开关）→ `source=usda`。
4. 仍未命中 / Key 不可用 / 超时 → **LLM 估算** → `source=estimate`，UI 强制标「估算」。
5. 汇总一餐：分项列表 + 餐次合计 + 置信说明。

**数据源说明**

| 来源 | 费用 | 准确度 | 中餐友好度 |
|------|------|--------|------------|
| 本地小库 | 无 | 可控 | 好（自建） |
| USDA FDC | 免费（约 1000 次/小时） | 官方数据，原料/西餐稳 | 差 |
| LLM 估算 | BYOK 成本 | 偏差较大 | 兜底 |

第一版本地库覆盖约 **50–100** 条常见主食与中式菜名，后续可扩。

---

## 5. LangChain Tools

| Tool | 作用 |
|------|------|
| `resolve_food_calories` | 单条/批量走 local → USDA → estimate 链路 |
| `log_meal` | 写入今日日记（餐次、分项、合计、source） |
| `get_today_summary` | 目标、已摄入、剩余、餐次列表 |
| `set_daily_calorie_goal` | 设置/更新每日目标 kcal |
| `delete_diary_entry` | 删除或撤销某条记录 |
| `recommend_meals` | 按剩余配额/预算/偏好生成 2–3 候选；内部调用 resolve；不自动入账 |

Agent 负责理解意图并组合工具；查库顺序由 `resolve_food_calories` 内部保证。

---

## 6. 数据模型

### 6.1 FitnessGoal

| 字段 | 说明 |
|------|------|
| `user_id` | 用户 ID |
| `daily_calorie_goal` | 每日热量目标（kcal） |
| `updated_at` | 更新时间 |

### 6.2 FitnessDiaryEntry

| 字段 | 说明 |
|------|------|
| `id` | 主键 |
| `user_id` | 用户 ID |
| `date` | 日期（用户时区） |
| `meal_type` | 早/午/晚/加餐 |
| `items` | `[{ name, qty, unit, kcal, source }]` |
| `total_kcal` | 餐次合计 |
| `note` | 可选备注 |
| `session_id` | 可选关联会话 |

### 6.3 会话

复用主站 `sessions` 表，`session_type=fitness`。

---

## 7. API 设计

均需 JWT 鉴权。

| 方法 | 路径 | 用途 |
|------|------|------|
| `POST` | `/api/v1/fitness/agent/run` | SSE：对话 + tool 事件 |
| `GET` | `/api/v1/fitness/goals` | 读取每日目标 |
| `PUT` | `/api/v1/fitness/goals` | 设置/更新每日目标 |
| `GET` | `/api/v1/fitness/diary/today` | 今日汇总（面板直读） |
| `DELETE` | `/api/v1/fitness/diary/{entry_id}` | 非对话删除兜底 |

### 7.1 SSE 事件

| 事件 | 说明 |
|------|------|
| `token` / `message` | 自然语言增量 |
| `tool_start` / `tool_end` | 工具名与简要结果 |
| `meal_logged` | 入账成功结构化 payload |
| `recommendations` | 推荐候选卡片 payload |
| `error` | 错误信息 |
| `done` | 流结束 |

---

## 8. 前端 UX

### 8.1 布局

```
┌─────────────┬──────────────────────────┬─────────────────┐
│ 会话列表     │ 对话区                    │ 今日面板         │
│ (fitness)   │ 记账 / 推荐 / 问答         │ 目标 / 已摄入    │
│             │ 推荐候选卡片（可确认入账）   │ 剩余 / 餐次列表  │
└─────────────┴──────────────────────────┴─────────────────┘
```

### 8.2 关键交互

1. 自然语言记账 → 流式回复 + 分项表（来源标签）→ 入账后右侧面板刷新。
2. 推荐 → 2–3 张候选卡 → 「记这一套」才入账。
3. 删除记录 → Agent 调 `delete_diary_entry` → 面板同步。
4. `estimate` 来源用醒目标记；`local`/`usda` 相对低调。

### 8.3 轻量工具轨迹

第一版不做旅行级 ReAct 四步可视化；可显示「调用了哪些 tool」的轻量条。

### 8.4 i18n

新文案走现有 i18n 体系；第一版至少 `en` + `zh-CN`。

---

## 9. 错误处理与降级

| 场景 | 处理 |
|------|------|
| 未登录 / JWT 失效 | 401，走现有登录流 |
| 未配置 BYOK | 引导模型连接对话框 |
| 本地库未命中 | 自动试 USDA |
| USDA 无 Key / 超时 / 限流 | 跳过并记日志，降级 LLM 估算 |
| LLM 估算 | `source=estimate` + 「仅供参考」 |
| 分量含糊 | 追问或默认分量并明示假设 |
| 推荐未确认 | 不入账 |
| 日记写入失败 | SSE `error`，不假装成功 |
| 同日多会话 | 日记以 `user_id + date` 为准 |

---

## 10. 环境变量

| 变量 | 用途 | 必填 |
|------|------|------|
| `USDA_FDC_API_KEY` | USDA FoodData Central 查询 | 否（无则跳过 USDA） |

本地食物库可内置 JSON 或小型 DB 表，无需额外 Key。

---

## 11. 实现里程碑

1. 数据模型 + goals/diary API + 今日面板。
2. `resolve_food_calories`（local → USDA → estimate）+ 单测。
3. LangChain Agent + `log_meal` / `get_today_summary` + SSE。
4. `recommend_meals` + 候选卡片 + 确认入账。
5. 侧边栏入口、i18n、免责声明、端到端自测。

---

## 12. 后续迭代（明确不进第一版）

- 图片识餐（用户原路线 C 的图）。
- Feature B：身体档案与 BMR/TDEE 自动配额。
- 可选中文营养 API（天聚等）作为 USDA 与本地库之间的补充层。
- 宏量营养素统计、周报导出。
- LangGraph 编排（若 Feature B 需要更复杂状态机）。

---

## 13. 决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| Agent 框架 | LangChain Tools + Agent | 作品集对照、可演示 tool-calling |
| 模块命名 | `fitness` | 避开 `/health` 探活路由 |
| 热量来源 | local → USDA → estimate | 可控 + 免费外部源 + 兜底 |
| 配额 | 手动每日目标 | 第一版轻量，有产品感 |
| 持久化 | 按用户按日落库 | 今日剩余可恢复 |
| 输入 | 文字优先 | 图片第二迭代 |
| 推荐 | 纳入第一版核心 | 与记账共用热量链路 |
| 入口 | 侧边栏独立模块 | 与旅行 Agent 并列 |
