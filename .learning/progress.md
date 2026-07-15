# Learning Progress — Qi AI Studio

> `/ai-engineer-coach` 的进度台账。主素材库在同目录 `interview-highlights.md`。
> 目标线：Frontend Engineer → **AI Application Engineer** → AI Platform Engineer。

---

## 2026-07-15

### Mode
Mode 2 - Repo-to-Capability Mapping（首次在本仓建立学习 OS + 面试档案）

### Today Mission
把 Qi AI Studio 的真实工程亮点勘探清楚，沉淀成可持续积累、经得起追问的面试档案（`interview-highlights.md`）。

### Completed
- 四路并行代码勘探（均带 file:line 证据）：
  - Chat 核心：SSE 断连续跑 + resume/retry、BYOK Fernet 加密、多 Provider 工厂+模板方法。
  - Spider：双运行时混合、反爬分类 + 有界浏览器升级、AST codegen 守卫、checkpoint reducer、cookie-as-secret、Docker 沙箱。
  - Travel/Fitness：手写 ReAct vs LangChain 对比、compare 双流合并、HITL + 反幻觉守卫、卡路里多源链。
  - 前端：通用 fetch-SSE 客户端、流恢复状态机、Zustand + 离屏会话缓存、9 语言 i18n、EllipsisTooltip。
- 产出 13 条亮点（H1–H13）+ 架构地图 + 能力雷达 + 生产就绪自查 + 累积模板。

### Capability Delta
- LLM Runtime 抽象：Lv2 → **Lv3**（工厂+模板方法，类型化错误映射）
- Agent Runtime：Lv2 → **Lv3**（三种 agent 实现 + 有界升级状态机）
- Streaming/持久化：Lv2 → **Lv3→4**（背压队列 + 断连续跑 + checkpoint reducer）
- Evaluation：**Lv1**（仅数据校验闸门，无 eval harness）— 明确瓶颈
- Observability：**Lv2**（structlog + request id + token 用量 + 工件报告）
- 综合定位：**Lv3 Agent 架构师**，向 Lv4 生产化平台

### Knowledge Tree Update
- Node: LLM Runtime — Mastered: 多 Provider 适配/错误映射；Not Mastered: retry/熔断接线；Loc: `backend/app/core/adapters/*`
- Node: Agent Runtime — Mastered: ReAct/LangChain/DeepAgent-pipeline 三形态；Not Mastered: 统一运行时接口；Loc: `backend/app/{travel,fitness,spider}/services/*`
- Node: Streaming — Mastered: 后台续跑+resume+checkpoint；Not Mastered: 多副本水平扩展（内存态）；Loc: `backend/app/api/v1/chat.py`, `spider/services/stream_checkpoint.py`
- Node: Evaluation — Not Mastered: 无 golden set / 回归；Loc: 待建
- Node: Observability — Mastered: 结构化日志+token 用量；Not Mastered: tracing/metrics 看板

### Production Readiness Check
- 有：structlog、X-Request-ID、tokens_used、ToolExecution 审计、Docker 隔离、数据校验闸门。
- 缺：eval harness / golden set、tracing/metrics、retry 接线、限流、核心链路测试、热路径 `print()`、`get_current_user` 后门、`eval/exec` 工具。

### Interview Expression（本次沉淀的一句）
「三个 Agent 都长在同一套 BYOK + SSE + 持久化地基上——所以它是一个平台，不是三个 demo。最能体现工程判断的是 spider 的双运行时混合：DeepAgent 会 hang，我保留它的前端事件契约，底下换成确定性状态机。」

### Next Step
1. 选一条深挖成「3 分钟口述稿」并做一次 Mode 5 模拟面试（首推 H4 spider 双运行时 或 H1 SSE 续跑）。
2. 补 Evaluation：给 travel/fitness 建一个最小 golden set + 回归脚本（把 Evaluation 从 Lv1 抬到 Lv2）。
3. 之后每加一个功能：说「更新档案」，按 `interview-highlights.md` §5 模板追加 H{n} + 更新能力雷达 + 记 CHANGELOG。
