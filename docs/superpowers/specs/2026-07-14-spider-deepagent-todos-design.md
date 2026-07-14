# Spider DeepAgent Todo 列表展示设计规格

**日期**：2026-07-14  
**状态**：已定稿  
**模块代号**：`spider` / `deepagent-todos`

---

## 1. 背景与目标

爬虫 Agent 基于 DeepAgents（`create_deep_agent` + LangChain `TodoListMiddleware`），具备 `write_todos` 规划能力。当前聊天 UI 只把工具调用渲成普通 `ChatToolRunBlock`，缺少类似截图的任务进度卡片。

另外，`/api/v1/spider/agent/run` **目前挂接的是确定性 pipeline**（`spider_pipeline_service`），为规避 DeepAgent `task` 子智能体挂起风险。本规格明确：**切回真 DeepAgent**，用其原生 todo 快照驱动 UI。

### 1.1 成功标准

- 复杂任务：LLM 自主调用 `write_todos` 后，助手消息内出现与参考图一致的 Todo 进度卡片，并随状态更新。
- 简单任务：未调用 `write_todos` 时，**不出现** Todo UI，也不伪造阶段列表。
- `write_todos` 默认不进普通工具块；可在「工具详情」中查看。
- 刷新 / 重开会话后，助手消息恢复当时 todos 快照与进度（如 `2/8`）。
- 新增 SSE `todos_updated`，前后端契约清晰。

### 1.2 非目标

- 不为 pipeline 伪造 todo。
- 不实现 DeepAgent hang 的专项恢复（沿用现有错误 / 取消）。
- 不做跨消息共享的全局 sticky Todo 面板。
- 不改 DeepAgent / `TodoListMiddleware` 源码；只消费其工具与状态语义。

---

## 2. 产品决策（已确认）

| 项 | 选择 |
|---|---|
| 展示位置 | 嵌在当前助手消息内（在「思考中…」上方） |
| `write_todos` 展示 | 默认仅 Todo 卡片；展开「工具详情」可见 |
| 会话恢复 | 恢复最终 todos 快照与状态 |
| 数据源 | 真 DeepAgent `write_todos`（非 pipeline 阶段） |
| 触发条件 | 仅当 LLM 判定复杂任务并调用 `write_todos` |

---

## 3. 架构与数据流

### 3.1 运行时切换

`backend/app/api/v1/spider.py` 中 `spider_agent_stream` 的导入从：

- `spider_pipeline_service.spider_pipeline_stream`

改为：

- `spider_agent_service.spider_agent_stream`

Pipeline 代码保留，便于必要时回退；本规格不删除。

### 3.2 Todo 数据模型

与 LangChain `Todo` 对齐：

```ts
type SpiderTodoStatus = 'pending' | 'in_progress' | 'completed';

type SpiderTodoItem = {
  content: string;
  status: SpiderTodoStatus;
};
```

DeepAgent 每次 `write_todos` **整表替换**，不做增量 merge。

### 3.3 SSE

在现有 `tool_call_start` / `tool_call_result` 之外，后端在识别到 `write_todos` 的 **tool_call_start**（从 `tool_args.todos` 规范化）时立即另发，不等待 tool result：

```json
{
  "type": "todos_updated",
  "source": "agent",
  "todos": [
    { "content": "分析目标网站结构", "status": "in_progress" },
    { "content": "生成爬虫代码", "status": "pending" }
  ]
}
```

规则：

- payload 为**规范化后的完整快照**（过滤非法项后）。
- 无合法项则不发该事件。
- 简单任务从不调用 `write_todos` → 从不发 `todos_updated` → 前端无卡片。

### 3.4 前端流式消费

`useSpiderChat`：

1. 收到 `todos_updated` → `updateMessage(assistantId, { todos })`。
2. 普通工具进 `toolRuns`；`raw_tool_name === 'write_todos'` 的 run 标记为 `hiddenFromDefaultList`（或等价），仅供「工具详情」。
3. `StudioAssistantMessage` / `StudioChatMessageList`：有 `todos?.length` 时渲染 `SpiderTodoCard`。

### 3.5 持久化

`_persist_spider_stream` 维护 `latest_todos`：每收到 `todos_updated` 覆盖。

`build_spider_tool_calls` / `save_spider_assistant_message` 增加可选 `todos`，写入：

```json
{
  "type": "spider_meta",
  "tool_trace": [...],
  "todos": [...],
  "failure": optional
}
```

恢复：`mapStoredMessageToChat` 读取 `meta.todos` → `StudioChatMessage.todos`。

流中断 / error：若已有 `latest_todos`，仍一并落库，不清空。

### 3.6 数据流示意

```text
LLM(复杂任务) → write_todos(整表)
  → tool_call_start/result
  → todos_updated
  → message.todos → SpiderTodoCard
  → (done) spider_meta.todos

LLM(简单任务) → 无 write_todos → 无卡片（与现网一致）
```

---

## 4. UI 规格

### 4.1 `SpiderTodoCard`

嵌入助手消息气泡内：

- **Header**：清单图标 + `{completed}/{total} 已完成` + ×（折叠为单行摘要，可再展开）。
- **List**：
  - `completed`：绿色勾选圆 + 灰字删除线
  - `pending`：空心灰圈 + 正常字色
  - `in_progress`：空心圈或细 spinner + 正常字色（与 pending 区分即可，保持克制）
- 文本单行省略（`truncate`）；列表区域最大高度 + 纵向滚动。
- 视觉对齐现有 studio chat（border / bg token），贴近参考截图：浅底、圆角、轻阴影。

### 4.2 工具详情

- 默认 `toolRuns` 列表过滤掉 `write_todos`。
- 「工具详情」折叠区展示含 `write_todos` 在内的完整 trace（若存在）。
- 无 todos、亦无被隐藏工具时，不渲染空折叠控件。

### 4.3 空态

`todos` 缺失或长度为 0 → **不渲染卡片、不占位**。

---

## 5. 错误处理与边界

| 场景 | 行为 |
|---|---|
| 非法 todo 项 | 丢弃坏项；剩余合法项仍更新；全无效则不发 / 不更新 |
| 多次 write_todos | 后到快照覆盖 |
| 流 error / 取消 | 保留最后快照并落库（若有） |
| DeepAgent hang | 不新增专项逻辑；已知风险，可取消请求 |
| 历史消息无 todos 字段 | 视为简单任务消息，无卡片 |

---

## 6. 主要改动面

### Backend

- `api/v1/spider.py`：导入切回 DeepAgent stream；persist 收集 `todos`。
- `spider/services/spider_agent_service.py`：检测 `write_todos`，yield `todos_updated`。
- `spider/services/chat_persistence.py`：`spider_meta` 增加 `todos`。

### Frontend

- `features/spider/types/events.ts`：`todos_updated`。
- `hooks/studioChat/types.ts`：`StudioChatMessage.todos`。
- `features/spider/hooks/useSpiderChat.ts`：消费事件、隐藏默认 write_todos。
- `features/spider/services/api/sessions.ts`：恢复 todos。
- 新组件：`features/spider/components/SpiderTodoCard.tsx`（及必要时小组件）。
- `components/chat/StudioAssistantMessage.tsx`（及 MessageList）：插入卡片；工具详情折叠。
- i18n：`en.json` / `zh-CN.json` 进度文案。

---

## 7. 测试计划

- 简单任务：无 `write_todos` → UI 无卡片。
- 复杂任务：多轮 `write_todos` → 卡片覆盖更新；完成数正确。
- 折叠 × → 摘要行；再点展开。
- 「工具详情」可见 `write_todos`，默认列表不可见。
- 刷新后恢复最终 todos。
- 中途 error：已有 todos 仍可见且已落库。

---

## 8. 已知风险

切回 DeepAgent 后，子智能体 `task` 委托在部分环境可能挂起——这是历史改用 pipeline 的原因。本功能刻意选择真实 todo 能力，接受该运行时风险；若 hang 不可接受，应另开规格评估「pipeline 伪 todo」或「DeepAgent 无 task 模式」，不在本规格范围。

---

## 9. 实现顺序建议

1. Backend：SSE `todos_updated` + persist + API 切回 DeepAgent。  
2. Frontend：类型 / store / `useSpiderChat` 消费。  
3. `SpiderTodoCard` + 助手消息布局。  
4. 工具详情折叠 + 会话恢复。  
5. 手动冒烟（简单 vs 复杂任务）。
