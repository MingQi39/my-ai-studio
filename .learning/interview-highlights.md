# Qi AI Studio — 面试亮点档案（可持续积累）

> 用途：把这个项目沉淀成**可在面试中讲透、经得起追问**的素材库。
> 维护方式：每加一个功能，就来一句「更新档案」，`/ai-engineer-coach` 会按本文件底部的模板追加一条亮点 + 更新能力雷达 + 记一笔 CHANGELOG。
> 原则：**只写代码里真实存在、能带 `file:line` 证据的东西**；短板照实写，面试官追问时反而是加分项。

- 项目一句话：**全栈 AI 聊天工作台 + 三个垂直 Agent（travel / fitness / spider），BYOK 多 Provider，SSE 流式，自托管可部署。**
- 电梯陈述（30s）：「我独立做了一个全栈 AI Studio：核心是一套支持 6 家 LLM Provider 的 BYOK 聊天平台，密钥 Fernet 加密落库；流式聊天做到了『断线不中断生成 + 刷新可恢复』。在这套地基上我搭了三个 Agent——旅行 Agent 是**手写 ReAct 循环**，健身 Agent 用 **LangChain 工具调用 + 人在环审批**，爬虫 Agent 是**确定性 pipeline 与 DeepAgent 双运行时混合**，还带反爬分类、浏览器升级、代码沙箱和断点续跑。前端 React18 + Zustand，9 语言 i18n，一套通用 SSE 客户端复用给所有 Agent。」

---

## 0. 架构地图（知识图谱，不是纯树）

```
                         ┌─────────────────────────────────────────────┐
                         │  React18 + Vite + Tailwind + Radix (frontend)│
                         │  Zustand · 9-lang i18n · 通用 SSEClient       │
                         └───────────────┬──────────────┬──────────────┘
                                         │ fetch+ReadableStream (SSE, 带 JWT/POST)
                                         ▼              ▼
      ┌───────────────────────── FastAPI (backend/app) ─────────────────────────┐
      │  JWT auth ── dependencies.py ── structlog + X-Request-ID 中间件           │
      │                                                                          │
      │   ┌────────────┐   共享地基   ┌───────────────────────────────────────┐  │
      │   │ Chat 核心   │◄────────────┤  BYOK ModelConfig (Fernet 加密落库)     │  │
      │   │ SSE 流式    │             │  多 Provider 适配层 (工厂+模板方法)      │  │
      │   │ 断连续跑    │             │  DeepSeek/OpenAI/Gemini/Qwen/OR/Ollama   │  │
      │   └─────┬──────┘             └───────────────────┬───────────────────┘  │
      │         │ 复用 resolve_travel_llm / 同一 BYOK      │                       │
      │         ▼                                          ▼                       │
      │  ┌──────────────┐   ┌──────────────┐   ┌────────────────────────────────┐ │
      │  │ Travel Agent │   │ Fitness Agent│   │ Spider Agent (最新/最深)         │ │
      │  │ 手写 ReAct    │   │ LangChain    │   │ 双运行时: deterministic pipeline│ │
      │  │ O→T→A→V      │   │ +HITL 审批    │   │ ↔ DeepAgent(4 subagent)         │ │
      │  │ compare 模式  │   │ +反幻觉守卫   │   │ 反爬分类→浏览器升级→codegen→     │ │
      │  │ PDF 导出     │   │ 卡路里多源链  │   │ Docker 沙箱执行→数据校验→断点续跑│ │
      │  └──────────────┘   └──────────────┘   └────────────────────────────────┘ │
      │         └────────── 工具层: AMAP/Juhe/Tavily/USDA + calculator ───────────┘ │
      │  SQLAlchemy 2.0 async + Alembic  ·  每会话 Docker 容器/命名卷 (spider)      │
      └──────────────────────────────────────────────────────────────────────────┘

图例：═ 共享地基（面试主线，别只讲 Agent 花活）   │▼ 数据/控制流
关键关系：三个 Agent 都长在同一套 BYOK + SSE + 持久化地基上 → 你能讲「抽象复用」而不是「三个 demo」。
```

**知识图谱 7 大节点**（面试按节点组织，比按功能罗列更显体系）：
`LLM Runtime` · `Agent Runtime` · `Tool Calling` · `Streaming/持久化` · `Evaluation` · `Observability` · `Infra & Deployment`

---

## 1. 能力雷达（按能力档位自评，不是「读了几个仓库」）

阶梯：Lv0 API 调用 → Lv1 聊天 → Lv2 Agent 循环 → Lv3 Agent 架构师 → Lv4 生产化平台 → Lv5 AI Infra

| 能力节点 | 当前档位 | 证据（可当场翻代码） | 差一口气到下一档 |
|---|---|---|---|
| LLM Runtime（多 Provider 抽象） | **Lv3** | 模板方法 `OpenAICompatibleAdapter` + 工厂 `LLMAdapterFactory`；429/402/503 映射为类型化异常 | 把 `retry.py`/`CircuitBreaker` 真正接线到适配器 |
| Agent Runtime | **Lv3** | 手写 ReAct（travel）+ LangChain（fitness）+ DeepAgent/pipeline 双运行时（spider）；有界升级状态机 | 统一 agent 运行时接口 + eval 驱动迭代 |
| Tool Calling | **Lv3** | 工具注册表 + OpenAI schema；最多 5 轮工具；HITL 审批；流式子工具进度 | 工具级重试/超时策略 + 失败可观测 |
| Streaming / 持久化 | **Lv3→4** | 后台生产者 + 有界队列(512) 背压；断连不中断；`stream-resume`；checkpoint reducer；实时落库 | 状态从内存搬到 Redis，支持多副本水平扩展 |
| Evaluation | **Lv1** | 只有数据校验闸门（非空 title / exit0+≥1 记录） | **无 eval harness / golden set**（最大短板） |
| Observability | **Lv2** | structlog(JSON) + `X-Request-ID` + `tokens_used` 落库 + 工件报告(analysis/validation_report.json) | 引入 tracing/metrics（延迟、成本、失败率看板） |
| Infra & Deployment | **Lv3** | 每会话 Docker 容器 + 命名卷隔离；Caddy 自动 HTTPS；compose；BYOK 加密 | 容器生命周期 GC + 出网策略/网络隔离 |

**一句话定位**：可信地宣称达到 **Lv3「Agent 架构师」**，正在往 **Lv4「生产化 Agent 平台」**爬——瓶颈是 evaluation 与 observability。面试里主动说这句，比被问出来强。

---

## 2. 亮点清单（面试主菜，每条自带口述稿 + 追问预案）

> 讲法建议：先讲 **H1/H2/H3 地基**（证明是「平台」不是「demo」），再挑 1 个 Agent 深挖（**首推 H4/H5 spider**，最能体现工程判断）。

### H1 · SSE 流式聊天：断线不中断 + 刷新可恢复 + 实时落库
- **是什么**：`POST /chat/stream` 用「后台生产者 task + `asyncio.Queue(maxsize=512)` 背压」跑 LLM 生成；客户端断开触发 `CancelledError` 时**生成任务不取消，继续在后台跑**；配合内存态 `StreamStateManager` + `GET /chat/stream-resume/{id}` 增量补发；生成过程实时写库，异常标 `is_complete=False`，`POST /chat/retry` 精确重生成残缺回复。
- **为什么值得讲**：比「naive `async for` yield」高一档——解决了真实产品痛点「用户刷新页面/网络抖动就丢半条回复」。生产者/消费者 + 有界队列体现了背压意识。
- **证据**：`backend/app/api/v1/chat.py` `_stream_chat_events` L28-98（断连续跑 L90-98）、`stream_chat` L112-137（`X-Accel-Buffering:no`）、resume L201-280；`backend/app/core/stream_state.py` L27-101；`chat_service.py` finalize L631-709。
- **口述稿（2min）**：「流式最容易被忽略的是断线。我把生成放进后台 task，SSE 消费循环只从队列取；客户端断开时我**故意不 cancel 生成**，让它在后台把整条跑完并落库。前端重连时先查 stream-status，如果还在生成就走 stream-resume 把已生成部分增量补上，否则轮询 DB 直到 is_complete。所以刷新页面不丢回复，这在多数玩具项目里是没有的。」
- **可能追问 → 应对**：
  - 「多 worker/多副本怎么办？」→ 诚实：`StreamStateManager` 是**进程内内存单例**，当前单实例可用；水平扩展要搬到 Redis pub/sub 或粘性会话，这是我明确的下一步。
  - 「队列满了？」→ `maxsize=512` 做背压，生产快于消费时自然阻塞 producer。

### H2 · 多 Provider LLM 适配层（工厂 + 模板方法 + 类型化错误映射）
- **是什么**：抽象基类 `BaseLLMAdapter`；OpenAI 兼容家族共享 `OpenAICompatibleAdapter`，只覆写差异 hook（`_build_request_params`/`_parse_chunk`/`_handle_error`）；不兼容的 Ollama 用 `httpx` 独立解析 NDJSON 并自己拆 `<think>` 标签；`LLMAdapterFactory` + `config/providers.yaml` 装配。HTTP 429/402/503/504 精确映射成 `RateLimitError/InsufficientBalanceError/ModelUnavailableError`。
- **为什么值得讲**：经典「模板方法 + 工厂」把 provider 差异「关」在子类里；DeepSeek 的 reasoning/tools 互斥、Qwen 的 `thinking_budget`、OpenRouter 的 `reasoning_details` 都是真实差异点，说明不是套壳。
- **证据**：`core/adapters/base.py` L13-118；`official/base.py` L31-294（错误映射 L214-260）；`official/deepseek.py` L67-118；`official/qwen.py` L97-147；`ollama/adapter.py` L373-565；`factory.py` L25-235。
- **诚实短板**：`anthropic`/`gemini` 目前复用通用兼容适配器（非专用实现）；`vLLM` 是占位 stub（会抛 `UnsupportedFeatureError`）。宣称「支持 N 家」时要区分「一等公民」和「兼容接入」。

### H3 · BYOK 静态加密（Fernet + 三级密钥 + 密钥漂移显式处理）
- **是什么**：用户 API Key 用 `cryptography.Fernet` 加密后存 `ModelConfig.encrypted_api_key`；密钥三级优先级：env `API_KEY_ENCRYPTION_KEY` → 本地 `.encryption_key` 文件 → 自动生成落盘；读配置接口**不返回明文 key**；解密失败给「密钥可能已更换，请重新配置」的可操作提示；会话级「多配置逐个降级」容错。
- **证据**：`services/model_service.py` L33-102、`_create_adapter` 解密 L529-575、容错 L472-527；`models/database.py` `ModelConfig` L312-347。
- **诚实短板**：单把进程级 Fernet key（非 per-user KMS），换 key 即全量失效，无密钥轮换——面试可答「真正生产要上 KMS + 信封加密」。

### H4 · Spider 双运行时混合：确定性 pipeline「伪装」成 Agent（最能体现工程判断）
- **是什么**：同一个 SSE 端点后面挂两套引擎，按请求选择：有 URL → **确定性 4 阶段 pipeline**（web_analyzer→code_generator→debug_agent→data_processor），无 URL/纯追问 → **真 DeepAgent（4 subagent）**。pipeline **保留了 DeepAgent 的 UX 契约**（subagent 事件 + 实时 todos），只是把易 hang 的 `task` 委派换成可靠状态机，两套并存、可回滚。
- **为什么是「面试金句」**：这是成熟的「**上线要可靠，理想路径也留着**」决策，且**有 docstring 明确写动机**（DeepAgents `task` 在某些环境会 hang），证明是刻意设计不是碰巧。体现「我会为可靠性做工程取舍」。
- **证据**：`spider/services/runtime_route.py` L12-16；`spider_pipeline_service.py` 顶部 docstring L1-5 + 4 阶段 L849-1355；`agent_builder.py` L86-138（4 subagent）；设计文档 `docs/superpowers/specs/2026-07-14-spider-pipeline-todos-hybrid-design.md`。
- **口述稿**：「我先用 DeepAgent 做爬虫，但它的子任务委派在某些环境会 hang。我没有推倒重来，而是**保留它对前端的事件契约**——subagent 开始/结束、实时 todos——底下换成一个确定性的 4 阶段状态机，前端根本分不出是哪套引擎。真 Agent 路径留给『用户没给 URL、需要追问』的场景。这样既上线可靠，又保留了 agent 的可扩展性。」

### H5 · 反爬分类器 + 有界浏览器升级状态机
- **是什么**：`classify_fetch_result` 把页面分成 `none/soft/js_render/hard`：**登录/访客墙先于 JS 渲染启发式判定为 hard-fail**（避免微博 Sina Visitor System 白跑一整轮 Playwright）；**CAPTCHA 只在可见文本里算数**（因为验证码字符串常出现在打包 JS 里）；`decide_initial_fetch_mode` 决定 HTTP / Playwright / 直接 block；升级是**有界状态机**——三种命名升级原因，最多升级一次浏览器，并把 `escalation_reason` 写进 `analysis_report.json` 供事后诊断。
- **为什么值得讲**：「可见文本 vs 打包 JS」是真实爬虫踩坑经验；「先判访客墙再判 JS 渲染」是从一个具体 bug（白跑一轮）反推出的排序修复；有界 + 命名原因 = 没有死循环、可测试、可诊断。
- **证据**：`spider/services/anti_scrape.py` L58-161（访客墙 L71-82、CAPTCHA 可见文本 L84-102）；`spider_pipeline_service.py` `decide_initial_fetch_mode` L532-549、升级判定 L552-569；Playwright 在**沙箱内**跑 `browser_fetch.py` L124-178。

### H6 · LLM codegen 的 AST import 白名单守卫
- **是什么**：LLM 生成爬虫代码前，用 `ast.parse` 遍历 import，按引擎（requests / playwright）走**默认拒绝的白名单**：`bs4` 只允许 `BeautifulSoup/Tag`、playwright 只允许 `from playwright.sync_api import sync_playwright`、requests 引擎禁止任何异步客户端；失败则 `llm → llm_fixed → 确定性 template` 逐级降级。
- **为什么值得讲**：抓的是「语法合法但运行必崩」的幻觉 import（如 `from playwright.sync_api import Soup`），在进沙箱前拦截；~150 行纯函数模块，好演示、好测试。
- **边界要说清**：这是**纠正性白名单**（防 ImportError + 强制同步引擎），**不是安全沙箱**；真正隔离靠 Docker。
- **证据**：`spider/services/code_guards.py` `validate_spider_imports` L46-71、规则 L92-149；降级 `_generate_spider_code_with_retry` L674-729。

### H7 · Mid-stream checkpoint reducer（刷新不丢 in-progress 轨迹）
- **是什么**：把「SSE 事件 → 持久化动作」建模成**纯 reducer** `apply_persist_event`：`chunk/final_response` → debounced（≥2s 或 ≥200 字符 flush 一次），`tool_call_start/result/todos_updated/error` → immediate；断连时在 `finally` 落一份 `is_complete=False` 快照；单条消息 upsert 不重复。
- **证据**：`spider/services/stream_checkpoint.py` L46-106；wrapper `api/v1/spider.py` `_persist_spider_stream` L74-135；`chat_persistence.py` L112-146。
- **为什么值得讲**：纯函数 reducer = 可单测、debounce = 不打爆 DB、cancel-safe = 刷新看到「中断但有内容」的气泡。

### H8 · 手写 ReAct（travel）vs LangChain（fitness）——刻意的框架对比
- **是什么**：travel 是**全手写 ReAct**（裸 OpenAI SDK function-calling，Observe→Think→Act→Verify 循环，无框架）；fitness 是 **LangChain 工具调用**（`StructuredTool.from_function` + `ChatOpenAI.bind_tools` 的手动循环，非 `AgentExecutor`）；**都没用 LangGraph**，且设计文档明确写了 v1 拒绝 LangGraph 的理由。
- **为什么是加分项**：同一套地基跑两种 agent 实现 = 你能可信地谈「裸 function-calling 与框架工具调用的取舍」，并解释为什么当前不需要 LangGraph。这是「懂权衡」信号。
- **证据**：`travel/services/react_agent.py` L60-471（Think 的 `tool_choice="auto"` L247-252）；`fitness/services/fitness_agent_service.py` L522-906（LangChain 循环 L722-896）；`requirements.txt` L80-83；spec `2026-07-08-fitness-agent-design.md` §3.1。
- **诚实短板**：travel 的 Observe 是**脚本化**的（硬编码 20 城、默认「杭州」、每轮必查天气），是「ReAct 形」但部分确定性；每轮 Think+Verify 最多 3 次 LLM 调用，成本高且未统计 token。

### H9 · Compare 模式：并行双流合并（asyncio.Queue fan-in）
- **是什么**：`/travel/compare` 并发跑「纯 LLM」和「ReAct Agent」，用一个 `asyncio.Queue` 把两条 SSE 流交错合并，每个事件打 `source` 标签，单流错误隔离，两侧结果按 `compare_group` 落库可回放。
- **证据**：`travel/services/sse_merge.py` L37-54；`travel.py` L185-251。

### H10 · Fitness 人在环审批 + 反幻觉写入守卫
- **是什么**：所有写/删工具（`log_meal`/`set_daily_calorie_goal`/`delete_diary_entry`）执行前**暂停**，发 `approval_required` + 人类可读预览，用户经 `/fitness/agent/approve` 才提交（propose/commit 分离）；另有守卫：若模型声称「已记录」但实际没有写工具成功，则把回复重写成安全版本。
- **为什么值得讲**：这是**具体、可讲的可靠性/安全机制**——面试聊「Agent 幻觉/误操作怎么防」时直接甩这两个。
- **证据**：`fitness_agent_service.py` HITL L162-191/L764-785、反幻觉 L739-748；`hitl.py` L10-153。

### H11 · 前端流恢复状态机 + 一套通用 SSE 客户端
- **是什么**：前端用 **`fetch` + `ReadableStream`**（而非 `EventSource`，因为要带 JWT header + POST body）实现通用 `SSEClient`，三个 Agent + 主聊天复用；主聊天的**恢复状态机**：刷新后查 stream-status → 在线则 re-attach `stream-resume`，已结束则用「内容指纹 + 3 轮稳定」轮询 DB，仍不完整则给 in-chat retry；用单调计数器防快速切会话的竞态。还有 spider 的**离屏会话缓存**（切走后长任务仍更新缓存）。
- **证据**：`frontend/src/lib/sseClient.ts`；`hooks/useStudioChat.ts` L280-333/L408-498；`hooks/studioChat/pollGeneration.ts` L1-88；`features/spider/stores/sessionMessageCache.ts` L46-89。

### H12 · 9 语言 i18n + IP/浏览器自动检测
- **是什么**：9 语言 `react-i18next`；检测优先级：`localStorage['app_lang']` → `ipapi.co` 国家映射 → `navigator.language` → `en`；手动选择后禁用 IP 自动检测；`zh` 按地区归一到 `zh-CN/zh-TW`。
- **证据**：`frontend/src/i18n/index.ts` L23-215。
- **诚实短板**：`spider`/`fitness` 命名空间**只有 en + zh-CN** 全，其余 7 语言回退英文；`ipapi.co` 是硬编码外部依赖。

### H13 · Cookie-as-secret 纪律 + 每会话 Docker 沙箱
- **是什么**：用户登录 cookie 用**请求作用域 ContextVar**（非全局），运行时才注入（HTTP header / Playwright 临时文件 + env + `finally` 删除 / 沙箱执行同法），从工作区列表、下载 API、生成代码里全程过滤，绝不落库/进 SSE/写进源码；每个 spider 会话独立 Docker 容器 + 命名卷，镜像变更时重建。
- **合规站位（可讲）**：cookie 明确定位为「用户自带登录态」，**不做自动化 CAPTCHA 绕过**——一个可辩护的伦理/合规立场。
- **证据**：`spider/services/request_cookies.py` L10-46；`browser_fetch.py` L140-178；`sandbox.py` L44-50/L208-297。

---

## 3. 生产就绪自查（AI 项目必答：Evaluation + Observability）

**已具备**：structlog(JSON) + `X-Request-ID` 请求日志；`Message.tokens_used` token 用量落库 + 各 provider 用量口径适配；`ToolExecution` 工具审计表 + 耗时；spider 工件报告（analysis/validation_report.json、escalation_reason）；数据校验闸门（非空 title、exit0+≥1 记录）；容器资源限制（mem/cpu/shm）。

**明确缺口（面试主动认，并给方向）**：
1. **无 eval harness / golden dataset**（Evaluation 停在 Lv1）→ 下一步：为 travel/fitness 建小型 golden set + 回归脚本。
2. **无 tracing/metrics 看板**（延迟/成本/失败率）→ 下一步：接 OpenTelemetry 或简易 metrics。
3. **retry/CircuitBreaker 建了没接线**（`core/retry.py` 未被适配器调用）→ 下一步：包住 LLM/外部 API 调用。
4. **无速率限制**（多用户会被「how to prevent abuse/cost blowup」命中）。
5. **核心聊天链路测试薄弱**（仅 2 个单测文件，无 auth/adapter/SSE/加解密集成测试）。
6. **热路径有 `print()` 调试语句**（`official/base.py`，绕过 structlog，潜在敏感信息泄漏）。
7. **安全一致性**：`system_instructions.py` 6 处仍用返回固定 `DEFAULT_USER_ID` 的 `get_current_user`（绕过 JWT）；`calculate`/`execute_python` 用 `eval`/`exec`（有 charset/空 builtins 兜底但非真隔离）。

> 这一节是「诚实清单」：把它当**改进 backlog**，每修一条就回来更新档位 + 记 CHANGELOG，你的成长轨迹就是可见的。

---

## 4. 高频面试问题 → 你的答案锚点（速查）

| 面试官问 | 你翻哪条 | 一句话锚点 |
|---|---|---|
| 讲讲你这个项目最难的点 | H4 + H5 | 双运行时混合 + 反爬有界升级状态机 |
| 流式怎么做的 / 断线怎么办 | H1 + H11 | 后台续跑 + resume/poll/retry 恢复状态机 |
| 怎么支持多个大模型 | H2 | 模板方法+工厂，差异关在子类，错误类型化 |
| 密钥安全 | H3 + H13 | Fernet 落库 + cookie ContextVar 运行时注入 |
| Agent 是自己写还是用框架 | H8 | 手写 ReAct + LangChain 双实现，为何不用 LangGraph |
| 怎么防 Agent 幻觉/误操作 | H10 + H6 | HITL 审批 + 反幻觉守卫 + codegen import 守卫 |
| 生成代码安全吗 | H6 + H13 | AST 白名单（纠正）+ Docker 沙箱（隔离） |
| 上线还差什么 | §3 | eval/observability/retry 接线/限流（主动认） |
| 怎么水平扩展 | H1 追问 | 内存态搬 Redis + 粘性会话（诚实的下一步） |

---

## 5. 【累积模板】新增功能时，把下面这块复制进「§2 亮点清单」

```markdown
### H{下一个编号} · {功能标题}
- **是什么**：{1-2 句，做了什么}
- **为什么值得讲**：{技术深度点 / 解决的真实痛点}
- **证据**：{file:line 至少 1 处，必须真实}
- **口述稿**：{30s~2min 一段，第一人称}
- **可能追问 → 应对**：{追问1 → 答案；诚实短板 → 改进方向}
- **能力档位影响**：{哪个节点 LvX→LvY，或补齐了 §3 哪条缺口}
```

追加后记得：① 更新 §1 能力雷达对应行；② 若补了短板，更新 §3；③ 在 §6 CHANGELOG 记一笔。

---

## 6. CHANGELOG（积累轨迹）

- 2026-07-15 — 初始化档案。基于四路代码勘探（chat 核心 / spider / travel+fitness / 前端）产出 13 条亮点、能力雷达、生产就绪自查。当前定位 **Lv3 Agent 架构师，向 Lv4 生产化平台爬**。
