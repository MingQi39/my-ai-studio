# Resume Craft 参考简历写法升维设计

**日期：** 2026-07-22  
**状态：** 已确认并实现中  
**前置：** [`2026-07-22-interview-resume-craft-design.md`](./2026-07-22-interview-resume-craft-design.md)（已上线）  
**触发：** 用户提供两份中文技术简历样例（工业 RAG-KG、医疗问诊 Agent），选定用于 **Resume Craft prompt 内的结构模板 + 脱敏 few-shot**。

## 已锁定产品决策

| 项 | 选择 |
| --- | --- |
| 用途 | 进 Resume Craft prompt（结构 + 脱敏 few-shot）；**不做**前端只读参考展示 |
| 输出结构 | 升为样例式「背景 · 技术栈 · 分块工作内容 · 成果」 |
| few-shot 数字 | 一律改为「（待补充数据）」，示范缺证据写法 |
| 实现形态 | 仓库内静态样例文件 + prompt 组装；模板降级共用同一骨架 |

## 目标

在 **不改变** eligibility、白名单 `ResumeDraft`、防编造回退策略的前提下，让 LLM 润色与模板降级输出更接近参考简历的专业密度与分区习惯。

## 非目标

- 前端展示参考简历或「参考写法」面板  
- 按 `target_role` / JD 动态挑选 few-shot  
- 放宽数字 / 实体编造规则  
- PDF / DOCX、多模板切换、持久化多版简历  
- 把用户提供的样例原文（含真实项目细节）原样入库供生成拷贝

## 与既有设计的关系

| 既有能力 | 本设计 |
| --- | --- |
| `GET/POST …/resume/*`、eligibility | 不变 |
| `build_resume_draft` 白名单字段 | 可小幅增强分组元数据（见下），**不**新增可编造字段 |
| `extract_novel_metrics` + 回退模板 | 不变；样例文件本身禁止含可匹配 metric |
| 旧 Markdown 骨架（摘要 / 技能 / 扁平 bullet） | **替换**为下文骨架（LLM 与 `render_template_markdown` 对齐） |

## 输出 Markdown 骨架（固定）

LLM 与模板降级共用：

```markdown
# （姓名） · {目标岗位} · {级别}

## 专业摘要
（3–4 句，仅 draft 事实）

## 技能关键词
A · B · C

## 项目经历

### {项目名}
**角色** · {时间或「待补充」}
**技术栈：** …
**项目背景：** …
**工作内容：**
1. **{分块标题}**
   - …
**项目成果：**
- …
（无证据的小节整段省略，不写空标题）

---
*本稿基于已确认简历事实与近 7 日训练闭环生成；未经验证的数据未写入。*
```

### Draft → 分区映射

| 输出块 | 来源 | 缺料时 |
| --- | --- | --- |
| 标题岗位/级别 | `profile.target_role` / `target_level` | 「目标岗位待定」；级别可省略 |
| 专业摘要 | keywords + project claims + 近期 topic | 1–2 句定性，不编造年限/规模 |
| 技能关键词 | `profile.keywords` + claim.keywords + skill claims | 「（待补充）」 |
| 项目名 | project-like claim `label` | 无 project-like 则提示补充 claim |
| 角色 / 时间 | claim 若无结构化字段 | 「角色待补充」·「时间待补充」 |
| 技术栈 | 该 claim 的 keywords ∪ 关联训练 topic | 省略「技术栈」行 |
| 项目背景 | 由 label + 关联证据摘录概括问题语境 | 省略「项目背景」段 |
| 工作内容分块 | 按关联 attempt 的 `focus_node` / `topic` 归组；过少则单组「职责与实现」 | 至少 1 条定性 bullet |
| 项目成果 | 仅定性收益句；数字仅当 draft/摘录已出现 | 「（待补充数据）」或省略整段 |

分块标题建议映射（实现可用固定中文表，未知 node 归入「职责与实现」）：

- `principle` / 机制类 → **原理与机制**  
- `trade-off` → **取舍与方案**  
- `evidence` → **证据与验证**  
- `position` / 场景 → **场景与定位**  
- 其余 → **职责与实现**

## 脱敏样例文件

**路径：** `backend/app/interview/fixtures/resume_craft_style_examples.md`

**文件头（必须）：** 标明「仅作润色风格 few-shot；禁止将示例中的项目名、技术细节、措辞原样写入用户简历」。

### Example A — 结构样（工业 RAG-KG，虚构）

示范完整项目块：标题行、技术栈一行、背景一段、工作内容 3–5 个编号分块、**项目成果** 子弹列表。  
技术名词可保留「混合检索 / 重排 / 知识图谱 / 权限过滤 / 证据不足拒答」等**写法级**词汇，但：

- 不得出现可被 `_METRIC_PATTERNS` 命中的数字模式（`%`、`倍`、`万`、`ms`、`QPS`+数字、`提升了 N` 等）  
- 凡「原样例会写数字」处统一为「（待补充数据）」  
- 项目名、公司、型号改为明显虚构前缀（如「示例·工业知识库 RAG-KG」）

### Example B — 价值样（医疗问诊 Agent，虚构）

篇幅短于 A：示范「痛点 → 模块方案（如 ReAct+图谱工具 / 双层记忆 / 流程控制）→ 项目价值」句式。  
同样禁止 metric 模式；量化处写「（待补充数据）」。

两例均用 Markdown，与最终输出骨架同构，便于模型模仿分区而非散文。

## Prompt 拼装

扩展 `POLISH_SYSTEM_PROMPT`（或拆成常量拼接），顺序：

1. **角色与硬规则**（保留并加强）  
   - 只根据用户提供的 `ResumeDraft` JSON 输出一份 Markdown  
   - 禁止新增数字、公司、职责、项目或成果  
   - 缺数据：写「（待补充数据）」或省略该小节  
   - 写法参考中的实体与措辞**不得**拷贝进输出  
2. **输出骨架** — 粘贴上文固定骨架说明  
3. **写法参考** — 运行时读取 `resume_craft_style_examples.md` 全文嵌入  

User 消息：仅 `ResumeDraft` JSON（与现网一致）。

读取失败时：退化为无 few-shot 的硬规则 + 骨架（仍可用模板降级）；日志 warning，不 500。

## 模板降级对齐

`render_template_markdown` 改为同一骨架：

- 每个 project-like claim 输出 `###` + 可选技术栈 / 背景 / 工作内容 / 成果  
- 有关联 `evidence_from_training`：工作内容按 focus_node 分块，bullet 用 topic + 摘录（截断规则不变）  
- 无证据：单组「职责与实现」+ 定性句 + 成果「（待补充数据）」  
- 文末免责声明保留（可用斜体一行，与骨架一致）

`polish_or_template` 行为不变：无润色 / 检出新 metric → 回退该模板。

## Draft 可选小增强（P0 允许）

为降低模型「乱拆分块」，`build_resume_draft` 可为每条 evidence 增加只读字段（仍来自已有 attempt，非发明）：

```json
"work_bucket": "trade-off"
```

模板与 prompt 均可消费；无该字段时按 `focus_node` 现算。

不新增姓名、公司、时间等结构化 claim 字段（仍占位）。

## 防编造与样例自检

1. 现有 `extract_novel_metrics` 继续作用于 LLM 输出。  
2. **新增测试：** 样例文件全文跑 `_collect_metrics` / `extract_novel_metrics` 同源逻辑，期望命中集合为空（或仅允许白名单占位短语，实现时约定：**零 metric 命中**）。  
3. 人工改写样例时禁止粘贴用户截图原文段落。

## 配置与依赖

- 无新 env；样例为打包内静态文件（注意 Docker 镜像需 `COPY` 到含 `fixtures/` 的路径；若当前 Dockerfile 只拷部分目录，实现时核对）。  
- `INTERVIEW_RESUME_CRAFT_*` 不变。

## 测试

| 用例 | 期望 |
| --- | --- |
| 样例文件无 metric | 断言通过 |
| `load_style_examples()` 可读 | 非空字符串 |
| 模板：仅有 claim 无 evidence | 仍输出骨架；省略空小节；含「（待补充数据）」或等价 |
| 模板：claim + 多 focus_node evidence | 工作内容出现多个分块标题 |
| polish：mock 输出含 draft 没有的 `提升 40%` | `degraded:metric_reject` + 模板 |
| polish：system prompt 含骨架关键词（如「项目成果」） | 单测断言组装后的 prompt 包含样例文件片段 |
| 既有 eligibility / craft 403 / template_only | 回归不破 |

## 实现切片（建议）

1. 新增 `fixtures/resume_craft_style_examples.md`（脱敏 A+B）+ metric 自检测试  
2. `load_style_examples` + 扩展 `POLISH_SYSTEM_PROMPT` 组装  
3. 重写 `render_template_markdown` 对齐骨架；按需给 draft 加 `work_bucket`  
4. 更新/补充 `resume_craft` 相关单元测试；手测一次真实 LLM（可选）

不改前端 API 契约；用户侧仅感知 Markdown 更「像正式项目经历」。

## 风险

| 风险 | 缓解 |
| --- | --- |
| few-shot 诱导抄示例技术细节 | prompt 明示禁止；输出仍过 metric 门；后续可加「示例项目名」黑名单扫描（P1） |
| prompt 变长、成本上升 | 两例控制篇幅；Example B 保持短 |
| 证据少时详版空洞 | 缺节省略 +「（待补充数据）」；不硬凑五段工作内容 |
| Docker 未打包 fixtures | 实现时改 Dockerfile.server；读取失败降级无 few-shot |

## 参考来源（不入库原文）

用户会话中提供的两份截图：工业知识库 RAG-KG 项目经历、医疗智能问诊（LLM+图谱）项目经历。本设计只抽取**分区与句式**，不复制其具体项目表述。
