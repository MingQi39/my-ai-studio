# Spider 执行中 Checkpoint 与刷新恢复设计规格

**日期**：2026-07-14  
**状态**：已定稿待实现  
**模块代号**：`spider` / `run-checkpoint-restore`

---

## 1. 背景与目标

爬虫 Agent 流式执行时，前端会在助手气泡内展示工具、子 agent（`task`）、todos、部分正文与失败卡。当前 `_persist_spider_stream` **仅在整轮流结束后** `add_message` 落库助手消息；页面刷新掐断 SSE 后，进行中快照尚未入库，刷新后只剩「页面刷新中断」提示，第一次执行过程中已展示的内容全部消失。

### 1.1 成功标准

- **实时**：执行过程中，已发生的工具 / 子 agent / todos / 正文继续挂在当前助手消息内（保持现有实时行为正确）。
- **刷新后**：重开同一会话，第一次执行过程中已经展示过的内容全部再展示：工具块（含输入输出）、子 agent 对应的 `task` 块、Todo 卡片、已缓冲正文、已有 failure 卡。
- 仍在 `running` 的工具：刷新后标为中断（`error` +「页面已刷新，实时执行状态已中断」），不再转圈。
- 顶部保留现有浅蓝 `restoreInterrupted` 提示条；**不恢复** ephemeral `statusLabel` 转圈文案。
- 正常跑完时仍只有 **一条** 助手消息，`is_complete=True`。

### 1.2 非目标

- 不重连后端、不续跑同一条 SSE。
- 不以 `sessionStorage` 作为主真相源（仅保留现有 `SPIDER_GENERATING_SESSION_KEY` 作中断提示辅助）。
- 不改为 `ToolExecution` 表；轨迹继续放在 `spider_meta.tool_trace`。
- 不顺带改 Fitness / Travel 的落库。

---

## 2. 产品决策

| 项 | 选择 |
|---|---|
| 真相源 | 后端增量 upsert 助手消息 |
| 未完成消息标记 | `Message.is_complete=False` |
| 中断判定 | `SPIDER_GENERATING_SESSION_KEY` 命中 **或** `is_complete === false` |
| 进行中无正文 | `content` 存 `""`，不写「执行中…」占位 |
| `tool_trace` | 含已完成 **与** 仍 pending/running 的项，按开始顺序 |
| 刷新后 statusLabel | 不恢复 |

---

## 3. 架构与数据流

```text
SSE 事件
  → 内存快照（content / tool_trace 含 pending / todos / failure）
  → 首个显著事件：创建助手消息 is_complete=False，记下 message_id
  → 显著变更：upsert 同一条消息的 content + spider_meta
  → 正常结束：is_complete=True 最终快照
  → 客户端断开 finally：再 flush 一次，保持 is_complete=False
  → 前端 loadSpiderSession → 渲染气泡全部已落库内容
  → 若中断：markInterruptedToolRuns + restoreInterrupted 条
```

与主站 `chat_service`「先建未完成助手消息再 update」同模式；Spider 元数据仍走 `spider_meta`。

---

## 4. 落库契约

### 4.1 `upsert_spider_assistant_message`

新增于 `chat_persistence.py`（经 `SessionService` 更新消息）：

```text
upsert_spider_assistant_message(
  session_id,
  message_id | None,
  content,
  *,
  tool_trace, failure, todos,
  is_complete: bool,
) -> message_id
```

- `message_id is None` → `add_message`，`is_complete` 按参。
- 已有 id → update 该行的 `content` / `tool_calls`（`build_spider_tool_calls`）/ `is_complete`。
- **禁止** 同一次 run 再插入第二条助手消息。

若 `SessionService` 尚无 update 能力，本规格允许最小增量：`update_message(message_id, …)`。

### 4.2 `_persist_spider_stream` 行为

内存态：

- `assistant_message_id: UUID | None`
- `content_buffer`
- `pending: dict[call_id, entry]`（start 时写入）
- `tool_trace_ordered`：由 `pending` 按首次出现顺序导出的完整列表（含未完成）
- `latest_todos` / `failure`

显著事件（立即 checkpoint）：

- `tool_call_start` / `tool_call_result`
- `todos_updated`
- `error`

内容 chunk：防抖 checkpoint（建议 ≥2s **或** 内容增量 ≥200 字符再写）。

结束路径：

| 路径 | `is_complete` | 说明 |
|---|---|---|
| 流正常结束且有可持久化内容 | `True` | 最终 content / trace / todos / failure |
| `CancelledError` / `GeneratorExit` / `finally` 且已有快照 | `False` | 再 flush，避免刷新丢进度 |
| 全程无内容、无 trace、无 failure、无 todos | 不写库 | 与现逻辑一致 |

空 content 且 `is_complete=True` 时，沿用现有占位「（无回复内容）」；未完成且无 content 时保持 `""`。

### 4.3 `tool_trace` 项形状

与现有条目兼容，未完成项示例：

```json
{
  "id": "<call_id>",
  "tool_name": "task",
  "raw_tool_name": "task",
  "tool_args": { "subagent_type": "code_generator", "description": "..." },
  "status": "pending"
}
```

已完成后补 `result`，`status` 为 `success` / `error`（与现事件一致）。前端 `mapToolTraceStatus`：`pending` / `running` → `running`。

---

## 5. 前端恢复与实时

### 5.1 实时

`useSpiderChat` 现有对 `tool_call_*` / `subagent_*` / `todos_updated` / chunk 的气泡更新保持不变；本规格靠后端对齐真相，不改主交互。

### 5.2 恢复

`mapStoredMessageToChat`：

- 继续映射 `tool_trace` → `toolRuns`、`todos`、`failure`、content。
- 透传 `isComplete: msg.is_complete !== false`（API 已有 `is_complete`）。

`useSpiderSessionRestore`：

- 中断条件：`sessionStorage` 生成标记命中 **或** 恢复出的助手消息存在 `isComplete === false`。
- 命中则：`markInterruptedToolRuns`、关 `isThinking`、`setRestoreInterruptedHint(true)`。
- 工作区短周期 `refreshWorkspace` 保留。

不恢复 `statusLabel`。

### 5.3 UI

无新组件。刷新后应再次出现首次执行气泡内已有的 `ChatToolRunBlock` / `SpiderTodoCard` / 正文 / `SpiderFailureCard`。

---

## 6. 错误与边界

| 场景 | 行为 |
|---|---|
| 刷新时断连 | finally flush 未完成快照；前端按中断展示 |
| Checkpoint 写库失败 | 不中断 SSE；尽量在 finally 再试一次 |
| 正常完成后又刷新 | `is_complete=True` 且无 generating 标记 → 完整终态，无中断条 |
| 仅 start 尚无显著事件就断开 | 无可持久化内容 → 不写助手消息（与现一致） |
| 下一轮新消息 | 未完成助手消息已在历史上；`messages_to_history` 照常带 content（可能为空串） |

---

## 7. 主要改动面

### Backend

- `session_service.py`：如需，新增 `update_message`。
- `spider/services/chat_persistence.py`：`upsert_spider_assistant_message`。
- `api/v1/spider.py`：`_persist_spider_stream` 增量 checkpoint + finally flush；`tool_trace` 含 pending。

### Frontend

- `services/api/sessions.ts`：`isComplete` 映射。
- `hooks/studioChat/types.ts`：消息可选 `isComplete`。
- `useSpiderSessionRestore.ts`：中断判定扩到 `isComplete === false`。

---

## 8. 测试计划

- 执行中出现至少 2 个工具后刷新：气泡恢复工具（含仍 running→中断）、todos（若有）、正文（若有），见中断条。
- 正常跑完再刷新：完整终态，无中断条，仅一条助手消息。
- 仅 `todos_updated` 尚无工具就刷新：Todos 可恢复。
- 流错误已发 `error` 后刷新：failure + 已有 trace 可恢复。
- Checkpoint 写失败时前端流仍可用；断开后若 finally 成功仍可恢复。

---

## 9. 实现顺序建议

1. `SessionService.update_message` + `upsert_spider_assistant_message`。  
2. 改造 `_persist_spider_stream`（含 pending trace + finally）。  
3. 前端 `isComplete` + 恢复中断判定。  
4. 手动冒烟：中途刷新 / 正常完成刷新。
