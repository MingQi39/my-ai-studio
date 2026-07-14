# Spider Cookie 注入设计规格

**日期**：2026-07-14  
**状态**：已定稿（已实现）  
**模块代号**：`spider` / `cookie-injection`  
**关联**：

- [`2026-07-14-spider-browser-escalation-design.md`](./2026-07-14-spider-browser-escalation-design.md)（曾将 Cookie 列为非目标；本规格为其后续增量）
- [`2026-07-14-spider-visitor-wall-hard-fail-design.md`](./2026-07-14-spider-visitor-wall-hard-fail-design.md)（访客墙硬失败仍保留；有 Cookie 时先注入再判定）

---

## 1. 背景与目标

微博等站点会返回访客系统 / 登录墙，Pipeline 将其判为 `anti_scrape_hard` 并提示「当前不支持 Cookie 注入」。用户已有合法登录 Cookie 时，应允许注入登录态继续分析与执行，而不是自动破解验证码。

### 1.1 成功标准

- 用户在爬虫页配置 Cookie 后，同会话后续运行可复用（可选记住）。
- **Pipeline**：宿主 HTTP 分析抓取、沙箱 Playwright 分析抓取、沙箱执行的 `requests` / Playwright 脚本均带上同一 Cookie。
- **DeepAgent**：`fetch_url` 与后续沙箱执行同样带上 Cookie。
- Cookie **不落库**、不写入聊天 `spider_meta`、不写入生成代码字面量、不进入 SSE / tool_trace 明文。
- 未配置 Cookie 时，访客墙仍按现有 `anti_scrape_hard` 失败（行为不变）。
- 已配置 Cookie 仍命中访客墙 / CAPTCHA：仍 `hard` 失败，hints 提示 Cookie 可能过期或无效。

### 1.2 非目标

- 自动绕过人机验证、打码、访客系统逆向、登录自动化。
- 代理池、独立 Auth Profile 服务、账户级长期存 Cookie。
- 服务端数据库 / 磁盘长期持久化 Cookie。
- 修改 Todo 四阶段语义。

### 1.3 已确认产品决策

| 项 | 选择 |
|---|---|
| 能力范围 | 仅 Cookie 注入（不做自动硬破） |
| UX | 会话级配置（与目标 URL 同级区域） |
| 存储 | 默认仅内存 + 当次请求；勾选「记住到本会话」才进浏览器 `sessionStorage`；**永不落库** |
| 运行覆盖 | Pipeline + DeepAgent |
| 注入层 | 分析抓取 + 沙箱执行 |
| 实现路线 | 请求字段 + **运行时注入**（环境变量 / 临时文件），不把 Cookie 写进 `spider.py` 字面量 |

---

## 2. 用户体验

### 2.1 UI

在目标网址输入框下方增加可折叠「登录 Cookie（可选）」区域：

1. 多行文本框：粘贴浏览器请求头中的 `Cookie` 字符串（形如 `SUB=...; SUBP=...`）。
2. 复选框「记住到本会话」：默认 **未勾选**。
   - 未勾选：仅存在前端 store 内存；刷新页面丢失（除非用户再次粘贴）。
   - 勾选：写入 `sessionStorage`，key = `spider:cookies:{sessionId}`（无 session 时用 draft key，创建会话后迁移，模式对齐 `targetUrl`）。
3. 简短说明：仅用于本人已登录态；不会保存到服务器；关闭标签页后清除（即便勾选，也仅本标签页会话级）。
4. 发送聊天 / 启动 Pipeline 时，请求体带上当前 Cookie 文本（空则省略字段或传 `null`）。

### 2.2 前端状态

- `useSpiderChatStore` 增加 `cookies: string`、`rememberCookies: boolean` 及 setter。
- `setRememberCookies(true)` 时把当前 cookies 写入 `sessionStorage`；`false` 时删除对应 key。
- 切换 / 恢复会话：从 `sessionStorage` 读回（仅当曾勾选记住）；**绝不**从消息历史 / 后端 workspace meta 恢复 Cookie。
- 文件列表、预览、侧栏会话信息：不展示 Cookie 内容（最多「已配置 Cookie」布尔提示，可选，本版可不做）。

---

## 3. API 与请求契约

### 3.1 请求体

扩展 `SpiderAgentRequest`：

```python
class SpiderAgentRequest(BaseModel):
    message: str
    session_id: UUID | None = None
    model_config_id: UUID
    target_url: str | None = None
    cookies: str | None = Field(default=None, max_length=16384)
```

- 值为 **原始 Cookie header 字符串**（不含 `Cookie:` 前缀）；前后空白 trim；空串视为 `None`。
- 服务端校验：长度上限 16KiB；禁止含裸换行控制字符（归一化为单行）。非法格式 → `400`（简短错误，不回显原文）。

### 3.2 持久化禁令

| 位置 | 规则 |
|---|---|
| `save_spider_user_message` / assistant meta | **不得**写入 `cookies` |
| SSE `session` / `error` / tool 事件 | **不得**回传完整 Cookie；tool args 序列化时对 `cookies` / `Cookie` 头做脱敏（`***`） |
| 工作区列表 / 文件预览 API | 排除 Cookie 临时文件（见 §5） |
| 服务端日志 | 只记 `cookies_configured: true/false` 与长度，不记内容 |

---

## 4. 后端注入架构

### 4.1 请求级上下文

与现有 `_sandbox_var` 同模式，新增 ContextVar：

```python
_cookies_var: ContextVar[str | None] = ContextVar("spider_request_cookies", default=None)

def set_request_cookies(cookies: str | None) -> None: ...
def get_request_cookies() -> str | None: ...
```

在 `/spider/...` 流式入口（Pipeline 与 DeepAgent 分支之前）`set_request_cookies`，`finally` 清空。禁止把 Cookie 塞进跨请求全局单例。

### 4.2 分析阶段 — HTTP `fetch_url`

`get_safe_headers(url)` 之后：若 `get_request_cookies()` 非空，则 `headers["Cookie"] = cookies`。

Pipeline 直接调用 / DeepAgent tool 调用同一实现，无需给 `fetch_url` 增加用户可见参数（避免 LLM 把 Cookie 抄进 tool 调用记录）。若工具层不得不暴露参数，也只从 ContextVar 读取，忽略模型传入值。

### 4.3 分析阶段 — Playwright

`browser_fetch` / `playwright_fetch.py`：

- 通过运行时环境变量 `SPIDER_COOKIE` 传入（启动抓取脚本前由宿主写入沙箱临时文件或 `export`）。
- 脚本内：若存在 Cookie，对 `context` 使用 `set_extra_http_headers({"Cookie": cookie})`，或解析为 playwright `cookies` 列表（按下述 §4.5）；二者择一，实现锁定 **extra HTTP headers** 为首选（实现简单、与站点无关）。

有 Cookie 时仍走现有 classify；注入后若仍为访客墙 → `hard`。

### 4.4 执行阶段 — 沙箱脚本

1. 执行前：若有 Cookie，写入工作区文件 `_spider_runtime_cookies`（名称以下划线前缀，列入「隐藏文件」过滤）。
2. `execute_in_sandbox` 运行命令形如：

   ```bash
   export SPIDER_COOKIE="$(cat _spider_runtime_cookies 2>/dev/null)"
   python spider.py
   ```

3. 执行结束后尽力删除 `_spider_runtime_cookies`（成功/失败都删）。
4. `list_workspace_files` / 预览路径：**过滤**该文件名，避免 UI 打开泄密。

### 4.5 Cookie 解析（可选辅助）

本版不强制结构化解析。脚本侧约定：

```python
import os
COOKIE = os.environ.get("SPIDER_COOKIE") or ""
# requests
headers = {...}
if COOKIE:
    headers["Cookie"] = COOKIE
```

Codegen system prompt / fallback 模板（HTTP 与 Playwright）必须：

- 从 `os.environ.get("SPIDER_COOKIE")` 读取；
- **禁止**把用户 Cookie 或示例登录 Cookie 写进源码字面量；
- 已有自定义 headers 时合并而非覆盖掉 Cookie。

### 4.6 DeepAgent

- Agent 构建 / 流入口同样 `set_request_cookies`。
- `fetch_url` 读 ContextVar。
- `execute_in_sandbox` 与 Pipeline 共用同一工具工厂逻辑（写入临时文件 + `SPIDER_COOKIE`）。
- 系统提示可增加一行：「若环境已配置登录 Cookie，fetch 与执行会自动带上；勿要求用户把 Cookie 贴进对话。」

---

## 5. 与反爬分级的关系

| 场景 | 行为 |
|---|---|
| 无 Cookie + 访客墙 / CAPTCHA | 保持现状 → `anti_scrape_hard` |
| 有 Cookie + 抓取后仍访客墙 / CAPTCHA | 仍 `anti_scrape_hard`；hints 指向「Cookie 可能过期或无效，请更新」 |
| 有 Cookie + 正常 HTML | 按 `none` / `soft` / `js_render` 原逻辑继续（可升级 Playwright，且升级也带 Cookie） |

更新 `_ERROR_HINTS["anti_scrape_hard"]`：

- 去掉「当前不支持 … Cookie 注入」。
- 改为：可在目标网址下方粘贴登录 Cookie；仍失败则换公开列表页或更新 Cookie。
- 当次请求 `cookies_configured=true` 时，优先返回「已注入 Cookie 仍被拦截」类 hints（实现可用 `hints_for_error_code(code, *, cookies_configured=False)`）。

**不改变**「不做自动硬破」原则：Cookie 只是用户自备登录态，不是破解器。

---

## 6. 组件与文件变更一览

| 区域 | 文件（预期） | 变更 |
|---|---|---|
| Schema / API | `backend/app/spider/schemas.py`，`api/v1/spider.py` | 新增 `cookies` 字段；入口 set/clear ContextVar |
| 上下文 | 新建 `backend/app/spider/services/request_cookies.py`（或并入 `tools.py`） | ContextVar + getter/setter |
| HTTP 抓取 | `tools.py` `fetch_url` / `get_safe_headers` 调用点 | 附加 Cookie 头 |
| 浏览器抓取 | `browser_fetch.py`（及 playwright 脚本） | 注入 `SPIDER_COOKIE` |
| 沙箱执行 | `sandbox.py` `create_execute_in_sandbox_tool` | 写/删临时文件 + export；列表过滤 |
| Codegen | `spider_pipeline_service.py` 模板与 prompt | 读 `SPIDER_COOKIE` |
| 反爬文案 | `anti_scrape.py` | 更新 hints；可选 `cookies_configured` |
| 前端 UI | `SpiderChatView.tsx` 等 | Cookie 区 + 记住勾选 |
| 前端状态 | `useSpiderChatStore.ts`，`constants/session.ts`，`useSpiderChat.ts` | 状态、storage key、请求体字段 |
| i18n | 中英文 locale | 文案 |
| 测试 | `tests/spider/...` | 见 §8 |

---

## 7. 错误处理

| 情况 | 处理 |
|---|---|
| Cookie 超长 / 非法控制字符 | HTTP 400，不启动流 |
| 注入后仍 hard | `anti_scrape_hard` + 更新 hints |
| 临时 Cookie 文件写入失败 | 本轮失败 `execution_failed` / `fetch_failed`，detail 不含 Cookie 原文 |
| 删除临时文件失败 | 记 warning；依赖列表过滤兜底隐藏 |

---

## 8. 测试计划

1. **单元**：`get_safe_headers` / fetch 组装在 ContextVar 有 Cookie 时包含 `Cookie` 头；无 Cookie 时行为不变。
2. **单元**：`hints_for_error_code("anti_scrape_hard", cookies_configured=True/False)` 文案符合 §5。
3. **单元**：workspace 列表过滤 `_spider_runtime_cookies`。
4. **单元 / 契约**：codegen fallback 模板含 `os.environ.get("SPIDER_COOKIE")`，且样本 Cookie 不会出现在生成源码常量中。
5. **Pipeline 集成（可 mock fetch）**：带 Cookie 请求进入分析阶段时，mock 的 fetch 收到 Cookie 头。
6. **持久化回归**：assistant/user message meta **不含** cookies 字段。
7. **前端（轻量）**：store remember 开关读写 `sessionStorage`；请求 payload 含 `cookies`。

人工验收：对微博等访客墙站，粘贴有效登录 Cookie 后应能越过 hard 墙进入后续阶段（具体站点成功率取决 Cookie 有效性，不作为自动化固定断言）。

---

## 9. 安全备注

- Cookie 属会话密钥；本设计刻意避免服务端长期存储与代码落盘。
- 文档 / UI 声明：仅注入用户自有登录态，用于本人授权场景；不提供自动绕过验证码。
- 沙箱内短时文件属于残余风险：靠结束后删除 + 列表过滤 + 下划线隐藏文件约定缓解；容器复用场景下下一轮执行前若检测到残留文件亦覆盖写或删除。

---

## 10. 验收清单

- [ ] 无 Cookie 时微博访客页仍 `anti_scrape_hard`，hints 引导去配置 Cookie / 换公开页。
- [ ] 有 Cookie 时 HTTP / Playwright 分析请求带 `Cookie` 头（或等价）。
- [ ] 生成/模板脚本通过 `SPIDER_COOKIE` 读取，源码无字面量 Cookie。
- [ ] DeepAgent `fetch_url` 与执行路径同样生效。
- [ ] DB 消息、SSE、工作区文件列表均无 Cookie 明文。
- [ ] 「记住到本会话」仅影响 `sessionStorage`；默认不记住。
