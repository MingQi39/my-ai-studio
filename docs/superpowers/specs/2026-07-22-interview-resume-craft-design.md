# 面试页一键简历升维（Resume Craft）设计

**日期：** 2026-07-22  
**状态：** 已确认（用户选定方案 2，并一次性确认全部设计段落）  
**范围：** Interview Navigator 附属能力（非独立简历产品）

## 目标

在面试训练页提供「生成简历」：基于 **已确认 ResumeClaim** + **近 7 天 committed 训练证据**，生成一份可复制的中文 Markdown 简历。  
LLM 只做措辞与排版升维，**禁止新增数字、职责、项目或成果**。

与 PRD「首期不做通用代写简历 / 不虚构指标」一致：本能力是 **证据绑定的简历升维**，不是空白代写。

## 非目标（P0）

- PDF / DOCX 导出
- 独立简历工作台、多模板切换、所见即所得编辑
- 英文简历、岗位 JD 定制多版本
- 自动编造或「合理猜测」量化指标
- 持久化多版简历历史库（可后续加）

## 产品决策（已锁定）

| 项 | 选择 |
| --- | --- |
| 入口 | 面试页一键生成（方案 A） |
| 输出 | 页内 Markdown + 一键复制 |
| 门槛 | 已确认 claim 够用 **且** 近 7 天 ≥1 次 committed（方案 B） |
| 实现 | 结构化草稿 JSON → LLM 润色（方案 2） |

## 解锁门槛（Eligibility）

同时满足才可生成；否则按钮禁用，并展示可读原因。

1. **Confirmed claims：** `status == "confirmed"` 的 `InterviewClaim` 数量 **≥ 3**  
   - 其中至少 **1** 条 `category` 属于项目/经历类（实现时映射现有 category 枚举，如 `project` / `experience`；若库中无该 category，则要求至少 1 条非纯 `skill` 的 claim，或退化为「≥3 条 confirmed」并在 UI 提示建议补充项目事实）。
2. **Recent commit：** 近 **7 天**（与 progress 的 route_depth 窗口一致）至少 **1** 条 `InterviewTrainingAttempt.status == "committed"`。

前置建议（不硬挡，仅文案提示）：已设置 `target_role` / `target_level`；缺失时简历标题区用占位「目标岗位待定」。

### Eligibility API

`GET /interview/resume/eligibility`

```json
{
  "eligible": false,
  "reasons": [
    "需要至少 3 条已确认的简历事实（当前 1）",
    "近 7 天需要至少 1 次已提交的训练闭环"
  ],
  "stats": {
    "confirmed_claims": 1,
    "confirmed_project_like_claims": 0,
    "committed_attempts_7d": 0
  }
}
```

前端用该接口控制按钮 `disabled` 与 tooltip/旁注；生成接口在服务端再次校验（防绕过）。

## 架构

```text
[InterviewPage]
  「生成简历」──disabled?──► GET /resume/eligibility
        │
        └─ POST /resume/craft
              │
              ├─ load profile + confirmed claims
              ├─ load committed attempts (7d) + linked review cards
              ├─ build ResumeDraft (白名单事实，无 LLM)
              ├─ LLM polish (purpose=resume_craft) — 只能改写 draft
              └─ return { markdown, draft_meta, sources }
```

模块建议：

- `backend/app/interview/resume_craft.py` — eligibility、draft 组装、prompt、生成编排  
- `backend/app/api/v1/interview.py` — 路由挂载  
- `model_roles.py` — 新增 purpose `resume_craft`（temperature 略高于 reflect，如 0.3；默认走现有 openai_compatible / 可配置）  
- 前端：`InterviewPage` 按钮 + Modal/面板展示 Markdown + Copy；`api.ts` 两个方法

不新建独立 Agent 会话表；P0 为单次请求-响应。

## 数据流：ResumeDraft（白名单）

生成前先组装不可由模型发明的草稿，字段示意：

```json
{
  "profile": {
    "target_role": "AI 应用工程师",
    "target_level": "P6",
    "salary_band": "30-50k",
    "keywords": ["FastAPI", "SSE", "RAG"]
  },
  "claims": [
    {
      "id": "...",
      "category": "project",
      "label": "Qi AI Studio · 面试导航",
      "keywords": ["FastAPI", "SSE"]
    }
  ],
  "evidence_from_training": [
    {
      "attempt_id": "...",
      "topic": "SSE",
      "focus_node": "trade-off",
      "covered_nodes": ["principle", "trade-off", "evidence"],
      "source_claim_ids": ["..."],
      "user_answer_excerpts": ["选用 SSE 因为单向推送与现有 HTTP 栈一致…"],
      "evaluation_flags": {"has_tradeoff": true, "has_evidence": true}
    }
  ],
  "constraints": [
    "Do not invent metrics, headcount, revenue, latency numbers, or employers.",
    "Only rephrase facts present in claims and evidence_from_training.",
    "If a bullet lacks quantitative evidence, write qualitative impact only or mark （待补充数据）."
  ]
}
```

`user_answer_excerpts`：从 committed attempt 的 `answers` 中取最后一次/最高质量短摘录（截断，如每条 ≤280 字），供润色引用，不当作可编造素材源以外的事实。

## 生成 API

`POST /interview/resume/craft`

成功：

```json
{
  "markdown": "# …",
  "sources": {
    "claim_ids": ["..."],
    "attempt_ids": ["..."]
  },
  "warnings": ["未设置目标岗位，标题区已用占位"]
}
```

失败：

- `403` + `detail.reasons[]`：未过 eligibility（与 GET 一致）  
- `503` / 降级：LLM 不可用时，可选 **直接用模板渲染 draft 为 Markdown**（无润色），并设 `warnings` 含 `degraded:template_only`；P0 必须有这一条，避免按钮可点却硬失败。

幂等：不强制；每次点击重新生成。P0 不落库；可选后续 `interview_resume_artifacts`。

## Markdown 简历结构（固定骨架）

中文一页友好结构：

1. 标题：姓名占位（若 claim/profile 无姓名则 `（姓名）`）+ 目标岗位/级别  
2. 专业摘要（3–4 句，只能用 keywords + 已覆盖 topic）  
3. 技能关键词（来自 confirmed claims + profile.keywords，去重）  
4. 项目经历（按 project-like claims；每条 2–4 bullet）  
   - 有训练证据的 topic：优先写成「决策 / 取舍 / 结果」句式  
   - 无量化：禁止编造；可用「待补充数据」或纯定性  
5. （可选）近期训练证明力：不单独成「证书」章节；证据融入项目 bullet  
6. 文末小字：`本稿基于已确认简历事实与近 7 日训练闭环生成；未经验证的数据未写入。`

## 防编造约束（硬规则）

1. Prompt 明确：输出只能改写 `ResumeDraft`；新实体、新数字、新公司名 → 禁止。  
2. 服务端轻量校验（P0）：对生成 Markdown 做简单扫描——若出现明显「新增」模式（可选：正则抓 `%`、`万`、`QPS`、`ms` 等且 draft 原文未出现）→ 丢弃润色结果，回退模板 Markdown，并 warning。  
   - P0 校验宜保守，宁可误杀润色，不可放过瞎编数字。  
3. UI 展示 `sources`（claim / attempt 数量即可），增强可审计感。

## 前端 UX

- 位置：面试页工具区，靠近「更新简历 / 进展面板」，文案：**生成简历**  
- `eligible === false`：按钮 disabled；旁注拼接 `reasons`（或 hover）  
- 点击后 loading；成功打开面板/Dialog：等宽字体或 Markdown 预览 + **复制**  
- 复制成功 toast  
- 不引入新路由页（P0）

## 配置

- `INTERVIEW_RESUME_CRAFT_PROVIDER` / `INTERVIEW_RESUME_CRAFT_MODEL`（默认可与 reflect 相同）  
- 门槛常量：`MIN_CONFIRMED_CLAIMS = 3`，`MIN_COMMITTED_7D = 1`（代码常量即可，不必先上 env）

## 测试

- eligibility：不足 claim / 无 7d commit / 两者都满足  
- draft 组装：只含 confirmed；candidate/rejected 不进  
- craft：未达标 → 403  
- craft：LLM mock 返回含「提升 300%」且 draft 无该数字 → 回退模板  
- craft：LLM 不可用 → template_only 成功  
- 前端：disabled 态与复制（组件级或手测清单）

## 实现切片（建议票序）

1. **P0a** eligibility API + 单元测试  
2. **P0b** draft builder + 模板 Markdown（无 LLM）  
3. **P0c** LLM polish + 防编造回退 + `POST /resume/craft`  
4. **P0d** 前端按钮 / 面板 / 复制  

## 风险与后续

- 姓名/联系方式：当前 claim 模型可能无结构化联系人 → P0 用占位，用户粘贴后自改  
- 「高大上」与诚实的张力：靠训练证据句式（取舍/机制）抬质量，不靠假数据  
- P1 可加：落库历史版本、按 JD 微调、导出 PDF
