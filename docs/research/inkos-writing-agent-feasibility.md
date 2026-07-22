# InkOS 写作 Agent 调研与集成可行性

调研日期：2026-07-21。范围：本机相邻项目 `../inkos` 的 README、`packages/core`、`packages/studio`、`packages/cli` 与核心测试。本文只基于一手源码；未运行 InkOS，未修改产品代码。

## 结论先行

可以把 InkOS 的**写作工作流思想**引入 Qi AI Studio，并做成一个用于学习的写作 Agent；但不建议把 InkOS 的代码、包或 Studio 直接嵌入当前产品。

原因有三点：

1. InkOS 的高价值在于“先治理输入与记忆、再写作、再结构化复盘”的闭环，而不是某一段 prompt。其 canonical state、可审计的章节上下文、受限的自动修订，尤其适合学习型写作流程。
2. 它是一个面向小说/IP 制作的独立 Node/TypeScript monorepo；当前产品是 FastAPI + React。直接引入会形成两套运行时、认证、持久化、会话和模型配置体系。
3. InkOS 根包、core、studio、cli 均声明 `AGPL-3.0-only`，直接复制、链接或作为网络服务集成前必须先做许可证与发布义务评估；本建议因此仅复用设计原则、重新实现，不复用其实现代码。见 [package.json](/Users/houmingqi/Desktop/my_own/inkos/package.json:21)、[core package.json](/Users/houmingqi/Desktop/my_own/inkos/packages/core/package.json:42)、[studio package.json](/Users/houmingqi/Desktop/my_own/inkos/packages/studio/package.json:12)、[cli package.json](/Users/houmingqi/Desktop/my_own/inkos/packages/cli/package.json:32)。

## InkOS 的写作 Agent 是什么

它不是单一“Writer”聊天机器人，而是一个有明确产物边界的小说生产线：

```text
作者意图 + 近期焦点 + 结构化记忆
        ↓
Planner（章节意图） → Composer（上下文包 / 规则栈 / trace）
        ↓
Writer（草稿） → Audit（连续性与硬规则） → 最多一次 Revise
        ↓
结构化 delta 校验/落盘 → 可读 Markdown 投影 → 下章检索
```

README 对角色分工的定义包括 Planner、Composer、Writer、Observer、Reflector、Normalizer、Continuity Auditor、Reviser；Reflector 只产生 JSON delta，代码再校验并写入状态。[README.en.md](/Users/houmingqi/Desktop/my_own/inkos/README.en.md:391) 其“一键”路径默认是 `plan → compose → write`，并保留可单独调用的原子操作，适合 UI 或外部 Agent 编排。[README.en.md](/Users/houmingqi/Desktop/my_own/inkos/README.en.md:455)

### 工作流要点

- 写入前：`prepareWriteInput` 形成输入；随后 `WriterAgent.writeChapter` 只接收该输入及长度治理规则。[runner.ts](/Users/houmingqi/Desktop/my_own/inkos/packages/core/src/pipeline/runner.ts:1609)
- 写入后：非手动模式执行审稿循环，包含连续性审稿、长度归一、AI 痕迹/敏感词/硬规则检查，并将最大迭代次数作为显式配置。[runner.ts](/Users/houmingqi/Desktop/my_own/inkos/packages/core/src/pipeline/runner.ts:1694)
- 质量循环不是无限自我改写。测试验证了：审稿解析失败时不自动改写；多轮时保留评分最佳版本而非最后版本。[chapter-review-cycle.test.ts](/Users/houmingqi/Desktop/my_own/inkos/packages/core/src/__tests__/chapter-review-cycle.test.ts:104) [chapter-review-cycle.test.ts](/Users/houmingqi/Desktop/my_own/inkos/packages/core/src/__tests__/chapter-review-cycle.test.ts:154)
- 落盘被书级锁包围，修订完成后再保存快照并同步叙事记忆索引。[runner.ts](/Users/houmingqi/Desktop/my_own/inkos/packages/core/src/pipeline/runner.ts:1582) [runner.ts](/Users/houmingqi/Desktop/my_own/inkos/packages/core/src/pipeline/runner.ts:1498)

## 状态与上下文治理：最值得学习的部分

### 1. 三层记忆、单一权威源

InkOS 把状态分为：结构化 JSON（权威）、面向作者的 Markdown 投影、SQLite 检索加速层。README 明确把 JSON 定为 authoritative；SQLite 只用于相关性检索。[README.en.md](/Users/houmingqi/Desktop/my_own/inkos/README.en.md:412)

源码也贯彻了这一点：检索时 hook 优先使用结构化状态，因为 SQLite 不保留核心 hook / 依赖等治理元数据；只有权威路径没有活动 hook 时才回退到数据库。[memory-retrieval.ts](/Users/houmingqi/Desktop/my_own/inkos/packages/core/src/utils/memory-retrieval.ts:105)

**可迁移原则**：学习 Agent 的记忆不能只是一段不断增长的聊天摘要。应把“用户目标、素材、已确认大纲、已完成草稿、反馈、待处理问题”结构化保存；Markdown/聊天摘要仅是可读投影，向量库或全文检索只能是加速索引。

### 2. 章节级的上下文包，而非全量 prompt 拼接

InkOS 将长期 `author_intent.md`、短期 `current_focus.md` 与每章的 intent/context/rule-stack/trace 区分开；`context.json` 是实际送入本章的上下文，`trace.json` 则用于解释它为何被选中。[README.en.md](/Users/houmingqi/Desktop/my_own/inkos/README.en.md:328) [README.en.md](/Users/houmingqi/Desktop/my_own/inkos/README.en.md:432)

检索函数先从章节目标、提纲节点、must-keep 提取关键词，按相关性选择摘要、事实、hook 与卷摘要，而非把全部历史塞入模型。[memory-retrieval.ts](/Users/houmingqi/Desktop/my_own/inkos/packages/core/src/utils/memory-retrieval.ts:56) 对“待回收 hook”还建立了明确的章节沉默阈值（5/8/10 章）和排序规则，避免长期线索被遗忘。[memory-retrieval.ts](/Users/houmingqi/Desktop/my_own/inkos/packages/core/src/utils/memory-retrieval.ts:168)

**可迁移原则**：每次写作都应生成可展示的 `writing brief`：本轮目标、目标读者、事实来源、必须覆盖/避免事项、长度、风格约束和冲突说明。这样用户可以在生成前纠偏，并能学习 Agent 的取舍。

这种治理并非 README 层面的命名：源码使用 Zod 为章节 memo、intent、被选上下文（含选择理由与摘录）、带优先级/覆盖关系的 rule stack，以及 token budget 的 trace 建立了独立契约。[input-governance.ts](/Users/houmingqi/Desktop/my_own/inkos/packages/core/src/models/input-governance.ts:3) [input-governance.ts](/Users/houmingqi/Desktop/my_own/inkos/packages/core/src/models/input-governance.ts:91) Planner 会基于种子材料和检索结果推导 intent，写出可追溯的章节意图工件；LLM memo 最多重试三次，仍失败则返回带警告但有效的降级结果，不让单个格式错误中断全流程。[planner.ts](/Users/houmingqi/Desktop/my_own/inkos/packages/core/src/agents/planner.ts:55) [planner.ts](/Users/houmingqi/Desktop/my_own/inkos/packages/core/src/agents/planner.ts:76) [planner.ts](/Users/houmingqi/Desktop/my_own/inkos/packages/core/src/agents/planner.ts:175)

### 3. LLM 提建议，代码守住状态边界

`applyRuntimeStateDelta` 先用 schema 解析快照和 delta，拒绝章节倒退、摘要章节不匹配、重复写入；应用后再跑完整状态校验，失败即抛错而不是传播脏状态。[state-reducer.ts](/Users/houmingqi/Desktop/my_own/inkos/packages/core/src/state/state-reducer.ts:25) 对应测试验证了正常更新和重复章节摘要被拒绝。[state-reducer.test.ts](/Users/houmingqi/Desktop/my_own/inkos/packages/core/src/__tests__/state-reducer.test.ts:5) [state-reducer.test.ts](/Users/houmingqi/Desktop/my_own/inkos/packages/core/src/__tests__/state-reducer.test.ts:105)

**可迁移原则**：Agent 不应直接改写“项目真相”。它应输出受 schema 限制的 patch/proposal；后端验证、展示 diff、由用户确认后再提交。这也适合现有产品的确认操作与 SSE 架构。

另一项可借鉴的边界是“创作”和“记忆结算”分离：Writer 先以较高温度创作正文，再以较低温度生成状态结算；最终将 prose、state delta、可读状态投影分别返回。[writer.ts](/Users/houmingqi/Desktop/my_own/inkos/packages/core/src/agents/writer.ts:220) [writer.ts](/Users/houmingqi/Desktop/my_own/inkos/packages/core/src/agents/writer.ts:303) [writer.ts](/Users/houmingqi/Desktop/my_own/inkos/packages/core/src/agents/writer.ts:423) 对学习 Agent 可对应为：先写/改文，再单独提议“本次可记住的写作偏好或练习结论”，后者必须经用户确认。

### 4. 工作集缩减要可解释

InkOS 依据当前 context package、章节意图内的 Hook Agenda 和最近章节窗口，裁剪 pending hooks；当筛选没有价值时退回原文。[governed-working-set.ts](/Users/houmingqi/Desktop/my_own/inkos/packages/core/src/utils/governed-working-set.ts:10) 

**可迁移原则**：向学习者展示“本次用了哪些素材、为什么”，比仅展示最终成文更重要；同时设置 token/条目上限，防止上下文膨胀。

### 5. 规则检查应尽量确定化

在调用审稿模型之外，InkOS 对篇章表面、体裁/书籍规则、跨章重复、段落长度漂移做零额外 LLM 成本的检查，再把 AI-tell 结果作为另一层信号。[writer.ts](/Users/houmingqi/Desktop/my_own/inkos/packages/core/src/agents/writer.ts:382)

**可迁移原则**：先实现可解释的确定性检查（长度、标题、段落、链接/引用、敏感表达、用户自定禁忌），再用 LLM 评估论证、叙事与语气；避免把可确定的问题交给模型“感觉”。

## 对 Qi AI Studio 的适配判断

| InkOS 能力 | 对学习型写作 Agent 的价值 | 建议 |
| --- | --- | --- |
| `Intent → Context → Rules → Draft` | 高：把写作过程显性化，便于学习与可控生成 | 首期实现 |
| 结构化记忆 + 可读投影 + retrieval | 高：支持跨会话、跨作品的连续学习 | 首期只做轻量 schema；后续加检索 |
| 审稿 / 修订闭环 | 高：形成“写—评—改”训练 | 首期人工确认后再改；自动修订最多一次 |
| 风格分析 / genre profile | 中：可做练习 rubric 和示例分析 | 第二期，避免承诺“模仿某作者” |
| 小说 hook ledger、37 维连续性审计 | 中低：对长篇连载很有价值 | 按写作类型做可插拔 rubric，不要照搬 37 项 |
| Play、互动电影、封面、CLI/TUI | 低：与当前“写作学习 Agent”范围无关 | 不纳入 |
| InkOS Node core/studio/cli 实现 | 低且风险高：双栈、AGPL、耦合重 | 不直接集成/复制 |

当前 InkOS Studio 本身也将“普通讨论”与“明确创建请求”区分，并要求重操作确认；这值得借鉴到现有 chat action surface，但不构成可直接复用的前端实现。[README.en.md](/Users/houmingqi/Desktop/my_own/inkos/README.en.md:306) 它的 agent session 有 5 分钟缓存与按 session 串行队列，说明多轮工具型会话需要并发治理；在本产品中应使用既有后端会话/任务边界重新实现。[agent-session.ts](/Users/houmingqi/Desktop/my_own/inkos/packages/core/src/agent/agent-session.ts:134) [agent-session.ts](/Users/houmingqi/Desktop/my_own/inkos/packages/core/src/agent/agent-session.ts:238)

## 建议的最小学习型 Agent（讨论稿，不实施）

建议命名为“写作教练”而不是“小说自动生成器”。首期聚焦短文、公众号、小红书/博客、技术写作等；长篇小说作为未来的专用模式。

1. **澄清与诊断**：用户给主题/素材/读者/平台，Agent 先输出“写作 Brief”和缺口，而不是立即写全文。
2. **写作计划**：输出可编辑的大纲、论点/叙事线、证据/素材清单、风格与禁忌、篇幅预算；用户确认后冻结该版 brief。
3. **起草或陪写**：支持“我先写，Agent 点评”与“Agent 先出初稿”两种模式；生成时显示所用素材与规则。
4. **Rubric 评审**：按体裁输出有限、可行动的反馈（例如受众匹配、结构、具体性、论证/叙事、语言）；反馈与改写建议分开，绝不静默覆盖用户原稿。
5. **反思卡片**：每轮沉淀用户偏好、常见问题和下次练习建议；仅在用户确认后写入长期档案。

### 建议的数据边界

```text
WritingProject (主题、受众、体裁、目标、风格偏好)
  ├─ SourceItem[]       用户素材及来源/权限
  ├─ WritingBrief vN    已确认的目标、提纲、约束、token 预算
  ├─ Draft vN           用户原稿 / Agent 建议稿，均保留版本
  ├─ Review vN          rubric 分数、证据定位、可执行建议
  └─ LearnerProfile     明确确认后沉淀的偏好与练习历史
```

其中 `WritingBrief` 是写作时的唯一输入合同；检索结果、模型选择和提示词版本写入 trace。长期偏好与原稿均不由模型自行覆盖。

## 需要在下一轮讨论决定的产品问题

1. 第一目标用户与体裁：个人表达/内容创作、技术写作，还是小说？这会决定 brief、rubric 和状态模型，不能混成一个泛化大 prompt。
2. “供我学习”的主路径：更偏 Socratic 追问、逐段批改，还是允许先生成范文再拆解？我的建议是默认“先规划/用户写/Agent 点评”，生成稿作为可选对照。
3. 记忆范围：默认按项目保存，还是跨项目学习用户风格？后者必须明确启用、可查看和可删除。
4. 交互入口：独立 Agent/工作台，还是在现有聊天中以 `写作教练` 模式出现？建议先作为现有 chat 的专用会话类型，复用认证、模型配置和 SSE，但后台数据模型独立。

## 验证与局限

本文以源码与单元测试为证据，未执行 `pnpm test`；因此测试结论是“测试意图/断言覆盖”，不是本机实测通过。InkOS README 是项目自述，架构判断以 core 源码和 tests 为准。
