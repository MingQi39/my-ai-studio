# Agent Skills 使用指南

本仓库工程 skill 已配置完成（见 `AGENTS.md` → Agent skills + `docs/agents/*.md`）。技能本体装在个人目录：

```text
~/.cursor/skills/<name>/SKILL.md
```

在 Cursor 对话里启用：

```text
/skill-name
```

或自然语言：`请使用 <skill-name> skill` / `按 grill-with-docs 来`。

不确定用哪个 → **`/which-skill`**。只要 Matt 工程技能图 → **`/ask-matt`**。

---

## 主流程：idea → ship

有代码库、要落地功能时，默认走这条路：

```text
/grill-with-docs
        │
        ├─ 问题只能靠可运行物回答 → /handoff → /prototype → /handoff 回原线程
        │
        ├─ 单会话装得下 → /implement（内建 /tdd + /code-review）
        │
        └─ 要跨多会话 → /to-spec → /to-tickets → 每个 ticket 新开 /implement
```

上下文卫生：grilling → spec → tickets **尽量同窗**；每个 `/implement` **清上下文新开**。

无代码库、纯方案拷问 → `/grill-me`（不写 `CONTEXT.md`）。

---

## 怎么选

| 你说的话 | Skill |
| --- | --- |
| 「用哪个 skill / 怎么开始」 | which-skill |
| 「只看 Matt 工程路由图」 | ask-matt |
| 「先对齐需求再写」 | grill-with-docs |
| 「无仓库，拷问方案」 | grill-me / grilling |
| 「写成正式 spec」 | to-spec |
| 「拆成可阻塞的票」 | to-tickets |
| 「实现 #123 / 这张票」 | implement |
| 「测试先行」 | tdd |
| 「review 这个分支」 | code-review |
| 「查为什么挂了」 | diagnosing-bugs |
| 「调研 XX」 | research |
| 「交接给下一个 agent」 | handoff |
| 「扫架构债 / 加深模块」 | improve-codebase-architecture |
| 「设计模块边界」 | codebase-design |
| 「统一术语 / 写 ADR」 | domain-modeling |
| 「先做个可抛弃原型」 | prototype |
| 「分流 issue」 | triage |
| 「大雾立项，地图式推进」 | wayfinder |
| 「解决 merge/rebase 冲突」 | resolving-merge-conflicts |
| 「教我这模块」 | teach |
| 「写 / 改 skill」 | writing-great-skills |
| 「学概念 / 面试知识图谱」 | kan |
| 「这个仓库今天学什么」 | project-learning-coach |
| 「前端→AI 长期成长」 | ai-engineer-coach |
| 「品牌 Logo / favicon」 | brand-logo |

---

## 完整目录

### 路由 · 基础设施

| Skill | 何时用 |
| --- | --- |
| [which-skill](~/.cursor/skills/which-skill/SKILL.md) | 覆盖本机全部 skill，中文裁定「该用哪个」 |
| [ask-matt](~/.cursor/skills/ask-matt/SKILL.md) | Matt 工程技能图 / flow 细节 |
| [setup-matt-pocock-skills](~/.cursor/skills/setup-matt-pocock-skills/SKILL.md) | **首次**配 Issue Tracker、Triage、Domain 布局（本仓已完成） |
| [writing-great-skills](~/.cursor/skills/writing-great-skills/SKILL.md) | 自建或改写 skill |

```text
/which-skill 我要给旅行 Agent 加一个新工具，怎么走？
/ask-matt 这条需求该进主流程还是 wayfinder？
```

本仓配置落点：

| 配置 | 路径 |
| --- | --- |
| Issue tracker | [`docs/agents/issue-tracker.md`](./issue-tracker.md)（GitHub + `gh`） |
| Triage labels | [`docs/agents/triage-labels.md`](./triage-labels.md) |
| Domain docs | [`docs/agents/domain.md`](./domain.md) + 根目录 `CONTEXT.md` / `docs/adr/` |

### 规划 · 研究 · 文档

| Skill | 何时用 |
| --- | --- |
| [grill-with-docs](~/.cursor/skills/grill-with-docs/SKILL.md) | 有代码库时对齐需求，同步磨 `CONTEXT.md` / ADR |
| [grill-me](~/.cursor/skills/grill-me/SKILL.md) | 无代码库的拷问式对齐 |
| [grilling](~/.cursor/skills/grilling/SKILL.md) | 上述两者共用的拷问原语（可被模型自动拉起） |
| [to-spec](~/.cursor/skills/to-spec/SKILL.md) | 把当前对话合成 spec，发布到 Issue Tracker |
| [to-tickets](~/.cursor/skills/to-tickets/SKILL.md) | 把 spec/计划拆成带 blocking edges 的 tracer-bullet tickets |
| [domain-modeling](~/.cursor/skills/domain-modeling/SKILL.md) | 统一语言、术语表、ADR |
| [research](~/.cursor/skills/research/SKILL.md) | 查一手来源，产出带引用的调研 Markdown |
| [handoff](~/.cursor/skills/handoff/SKILL.md) | 压缩对话为交接文档，换会话继续 |
| [wayfinder](~/.cursor/skills/wayfinder/SKILL.md) | 超大/雾区工作：地图式决策票，清雾后再 `/to-spec` |

```text
/grill-with-docs 我想给聊天页加「会话文件夹」。
/to-spec 根据刚才讨论写 spec 并建 GitHub issue。
/to-tickets 把这份 spec 拆成 tickets。
/research 调研 SSE 断线重连最佳实践，写到 docs/。
```

### 设计 · 架构 · 原型

| Skill | 何时用 |
| --- | --- |
| [codebase-design](~/.cursor/skills/codebase-design/SKILL.md) | 深模块：大量行为藏在小接口后，定 seam |
| [improve-codebase-architecture](~/.cursor/skills/improve-codebase-architecture/SKILL.md) | 扫描加深机会，出 HTML 报告后逐项 grill |
| [prototype](~/.cursor/skills/prototype/SKILL.md) | 可抛弃原型验证状态机 / UI 方向 |
| [resolving-merge-conflicts](~/.cursor/skills/resolving-merge-conflicts/SKILL.md) | 按意图解冲突并完成 merge/rebase，不 abort |

```text
/improve-codebase-architecture 扫 backend/app 的加深机会。
/prototype 用 throwaway 页面验证旅行 Agent 对比模式状态机。
```

### 实现 · 测试 · Review · 排错

| Skill | 何时用 |
| --- | --- |
| [implement](~/.cursor/skills/implement/SKILL.md) | 按 spec/ticket 实现（内建 tdd + code-review） |
| [tdd](~/.cursor/skills/tdd/SKILL.md) | Red-Green-Refactor，纵向切片 |
| [code-review](~/.cursor/skills/code-review/SKILL.md) | Standards + Spec 双轴 Review |
| [diagnosing-bugs](~/.cursor/skills/diagnosing-bugs/SKILL.md) | 难 bug / 间歇 flake / 性能回归 |
| [triage](~/.cursor/skills/triage/SKILL.md) | 外来 Issue 状态机分流，写 agent-ready brief |

```text
/implement 实现 issue #42。
/tdd 先写测试再实现天气工具失败重试。
/code-review 对比 main...HEAD，Standards + Spec。
/diagnosing-bugs SSE 偶发断流，本地难复现。
/triage 分到 ready-for-agent 并写 brief。
```

不要对 `/to-tickets` 已产出的票再跑 `/triage`（那些票已经是 agent-ready）。

### 学习（个人 skill，非 Matt）

| Skill | 何时用 |
| --- | --- |
| [kan](~/.cursor/skills/kan/SKILL.md) | 概念/面试：知识图谱导航，Zoom In/Out |
| [project-learning-coach](~/.cursor/skills/project-learning-coach/SKILL.md) | 学某个仓库怎么跑、今日任务 |
| [ai-engineer-coach](~/.cursor/skills/ai-engineer-coach/SKILL.md) | 前端 → AI 应用/平台长期成长 |
| [teach](~/.cursor/skills/teach/SKILL.md) | 在本仓语境里系统学某个模块 |
| [brand-logo](~/.cursor/skills/brand-logo/SKILL.md) | 品牌 Logo / favicon / 站点标识 |

学习类与工程交货类**不要混开**：学仓库用 coach；在仓库里改产品用 Matt 主流程。

---

## 本仓建议口令（复制即用）

```text
/which-skill <一句话目标>
/grill-with-docs <功能想法>
/to-spec
/to-tickets
/implement #<issue>
/tdd <小行为>
/diagnosing-bugs <现象 + 如何复现>
/improve-codebase-architecture
```

---

## 和参考仓库的差异

参考仓（`aigcode-autopilot-forntend`）把 skill 拷进 `.agents/skills/`，用 `@.agents/skills/<name>/SKILL.md` 引用；命名上仍有 `to-prd` / `to-issues`。

本仓：

| 项 | 本仓 |
| --- | --- |
| 技能位置 | `~/.cursor/skills/`（个人全局） |
| 启用方式 | `/skill-name` 或自然语言 |
| Spec / 拆票 | `to-spec` / `to-tickets` |
| Issue tracker | GitHub Issues（`gh`），见 `issue-tracker.md` |
| 路由入口 | `which-skill` + `ask-matt` |

改 tracker / triage / domain 布局：编辑 `docs/agents/*.md`，或再跑 `/setup-matt-pocock-skills`。
