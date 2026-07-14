# Spider Pipeline + Todo 混合执行设计规格

**日期**：2026-07-14  
**状态**：已定稿（待实现）  
**模块代号**：`spider` / `pipeline-todos-hybrid`  
**关联**：[`2026-07-14-spider-deepagent-todos-design.md`](./2026-07-14-spider-deepagent-todos-design.md)

---

## 1. 背景与目标

DeepAgent Todo UI 已落地（`todos_updated` → `SpiderTodoCard`），但 `/agent/run` 切回真 DeepAgent 后出现「只回复教程、不调 `task`」：没有逐步执行，Todo 也不推进。

历史 Pipeline 可强制四阶段执行，但旧规格曾禁止为 Pipeline 伪造 todo。产品现状需要：**有目标 URL 时必须逐步真执行，并实时更新 Todo 状态**。

### 1.1 成功标准

- 带 URL 的标准爬取：走 Pipeline；开场即出现 4 步 Todo；每完成一阶段推进状态；全部成功四步均为 `completed`。
- 某阶段失败：当前步变为 `failed`，未执行步骤保持 `pending`；现有 failure / error 卡片仍出现。
- 无 URL / 纯追问：走 DeepAgent；Todo 仍仅来自真实 `write_todos`（可不出现卡片）。
- 刷新后能恢复最后一次 todos 快照（含 `failed`）。

### 1.2 非目标

- 不对「追问」做 NLP 意图分类（首版仅按是否有 URL 分流）。
- 不实现 DeepAgent hang 专项恢复。
- 不引入全局 sticky Todo 面板。
- 不修改 DeepAgents / `TodoListMiddleware` 源码。
- 不移除 Pipeline 或 DeepAgent 任一实现（两者并存）。

### 1.3 对旧规格的修正

[`spider-deepagent-todos`](./2026-07-14-spider-deepagent-todos-design.md) 中：

- 「API 一律挂 DeepAgent」「不为 pipeline 伪造 todo」——**本规格在标准爬取路径上推翻**。
- DeepAgent 路径的 todo 语义与 UI 契约**继续有效**；本规格主要补 Pipeline 侧与路由。

---

## 2. 产品决策（已确认）

| 项 | 选择 |
|---|---|
| 引擎策略 | 混合：有 URL → Pipeline；无 URL / 追问 → DeepAgent |
| Todo 来源（Pipeline） | 固定 4 步模板，程序推进并发 `todos_updated` |
| Todo 来源（DeepAgent） | 原生 `write_todos`（不变） |
| 失败状态 | 新增 `failed` |
| 追问判定（首版） | 仅「消息与 `target_url` 均无法解析出 http(s) URL」→ DeepAgent |

---

## 3. 架构与数据流

### 3.1 运行时路由

在 `backend/app/api/v1/spider.py` 的 `event_stream` 内：

```text
resolve_url(request.target_url, request.message)
  → 有 URL  → spider_pipeline_stream(...)
  → 无 URL  → spider_agent_stream(...)
```

URL 解析复用 Pipeline 现有 `_resolve_target_url` 逻辑（可抽到共享 helper）：

1. `target_url` 非空则用之；
2. 否则扫描 `message` 中以 `http://` / `https://` 开头的 token；
3. 皆无则判定「无 URL」→ DeepAgent（不再让 Pipeline 直接 `missing_target_url` 提前结束——DeepAgent 可回答「请提供网址」类追问）。

> 说明：有 URL 时即使文案像追问（如「再清洗一次」），首版仍走完整 Pipeline。后续若要精细分流，另开规格。

### 3.2 Todo 数据模型

扩展状态（前后端一致）：

```ts
type SpiderTodoStatus = 'pending' | 'in_progress' | 'completed' | 'failed';

type SpiderTodoItem = {
  content: string;
  status: SpiderTodoStatus;
};
```

- `normalize_todos` / `isSpiderTodoStatus` / `todo_events._ALLOWED_STATUS` 均接受 `failed`。
- DeepAgent 若不产出 `failed`，行为不变。

### 3.3 Pipeline 固定模板

与四阶段一一对应，文案固定（中文；英文 i18n 可由后端常量或前端不翻译 content——首版后端发中文 content，与现 DeepAgent/Pipeline 中文阶段文案一致）：

| 索引 | content | 阶段 |
|---|---|---|
| 0 | 分析目标网站结构 | `web_analyzer` |
| 1 | 生成爬虫代码 | `code_generator` |
| 2 | 在沙箱执行并调试 | `debug_agent` |
| 3 | 清洗并校验数据 | `data_processor` |

### 3.4 Todo 推进规则

开场（Sandbox 初始化成功、开始 Stage 1 之前）：

```json
{
  "type": "todos_updated",
  "source": "agent",
  "todos": [
    { "content": "分析目标网站结构", "status": "in_progress" },
    { "content": "生成爬虫代码", "status": "pending" },
    { "content": "在沙箱执行并调试", "status": "pending" },
    { "content": "清洗并校验数据", "status": "pending" }
  ]
}
```

之后：

| 时机 | 动作 |
|---|---|
| 阶段 start | 该索引 → `in_progress`（通常已在上一步 complete 时设好） |
| 阶段 complete | 该索引 → `completed`；若有下一步 → `in_progress` |
| 阶段 error（含提前失败） | 当前索引 → `failed`；其后索引保持 `pending`；此前 `completed` 不变 |
| 四阶段全部成功 | 四步均为 `completed`，再发 `final_response` |

每次推进都发**完整快照** `todos_updated`（与 DeepAgent 契约一致）。  
若在沙箱初始化失败等「尚未进入 Stage 1」场景：可不发 todos，或发四步全 `pending` 后立刻把第 0 步标 `failed`——**推荐**：仅在确认进入流水线后发首帧；沙箱失败仍用现有 `error` 事件，无 Todo 卡片（与「未真正开始爬取」一致）。

缺失目标 URL 已由路由交给 DeepAgent，Pipeline 不再处理「缺 URL」。

### 3.5 数据流示意

```text
有 URL
  → pipeline
  → todos_updated(in_progress 第1步)
  → stage1…4（每步 tool/subagent 事件 + todos_updated）
  → final_response / error(+ failed todo)

无 URL
  → deepagent
  → （可选）write_todos → todos_updated
  → task / 文本回复（可能仍空聊——接受，非本规格主修范围）
```

---

## 4. UI 规格

在既有 `SpiderTodoCard` 上增量：

| status | 展示 |
|---|---|
| `completed` | 绿勾 + 灰字删除线（不变） |
| `pending` | 空心灰圈（不变） |
| `in_progress` | spinner（不变） |
| `failed` | 红色警示/叉图标；**不加**删除线；字色可偏 error token |

- Header 计数：`completed / total`（`failed` **不计入** completed）。
- i18n：`spider.chat.todos.failed`（如「失败」），用于 `aria-label`。
- 持久化恢复：`mapStoredMessageToChat` 已读 `meta.todos`；需确保 normalize 接受 `failed`。

---

## 5. 错误处理与边界

| 场景 | 行为 |
|---|---|
| 抓取 / 代码生成 / 执行 / 清洗失败 | 当前步 `failed` + 现有 `_error_event` / failure |
| 流中断 / 取消 | persist 保留最后 todos（现有 checkpoint 逻辑） |
| DeepAgent 空聊无 write_todos | 无卡片（既有行为）；非本规格强制修复 |
| 历史消息 status 无 `failed` | 正常；新枚举向后兼容 |
| 非法 status 项 | normalize 丢弃该项 |

---

## 6. 主要改动面

### Backend

- `api/v1/spider.py`：按 URL 在 `spider_pipeline_stream` / `spider_agent_stream` 间路由。
- `spider/services/spider_pipeline_service.py`：发并推进 `todos_updated`；失败标 `failed`。
- `spider/services/todo_events.py`：允许 `failed`；可选增加 Pipeline 模板 helper。
- 抽共享 `resolve_spider_target_url`（可选，避免双份解析）。

### Frontend

- `features/spider/types/todo.ts`：`failed`。
- `SpiderTodoCard.tsx`：failed 图标与样式。
- i18n：`zh-CN` / `en` 的 `spider.chat.todos.failed`。

### 测试

- `tests/spider/`：Pipeline 首帧 / complete / failed 快照单测；`normalize_todos` 接受 `failed`。
- 路由单测：有/无 URL 选择正确 stream（可 mock）。

---

## 7. 测试计划

- [ ] 仅填目标 URL +「爬电影标题」→ Pipeline；Todo 逐步 `in_progress` → `completed`。
- [ ] 故意坏 URL / 抓取失败 → 第 1 步 `failed`，其余 `pending`，有失败卡片。
- [ ] 执行阶段失败 → 前两步 `completed`，第 3 步 `failed`，第 4 步 `pending`。
- [ ] 无 URL 纯文字追问 → DeepAgent；可不出现固定四步 Todo。
- [ ] 刷新会话 → 恢复含 `failed`/`completed` 的快照。
- [ ] 现有 DeepAgent `write_todos` 路径回归：仍能更新卡片。

---

## 8. 已知风险

| 风险 | 缓解 |
|---|---|
| 有 URL 的「轻量追问」也被整流水线重跑 | 首版接受；可后续加 mode / NLP |
| DeepAgent 路径仍可能空聊 | 本规格不强制；产品以 Pipeline 覆盖主路径 |
| Pipeline hang（少见） | 沿用取消 / error；非 DeepAgent task hang |

---

## 9. 实现顺序建议

1. 扩展 `failed`（backend normalize + frontend 类型/UI）。  
2. Pipeline 注入 todo 模板与阶段推进。  
3. API 按 URL 路由。  
4. 单测 + 手动冒烟（有 URL / 无 URL / 中途失败）。  

---

## 10. Spec 自检

- [x] 无 TBD / 占位符未决项（路由、failed、模板已确认）
- [x] 与 deepagent-todos 冲突处已显式「推翻说明」
- [x] 范围清晰：不含 hang 恢复、不含追问 NLP
- [x] SSE 事件类型不新增（复用 `todos_updated`）
