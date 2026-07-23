"""Curated daily reading units aligned with ai-agent-interview-guide chapters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReadingUnit:
    section_title: str
    bullets: tuple[str, ...]


@dataclass(frozen=True)
class StageDocMeta:
    doc_title: str
    source_file: str


STAGE_DOC_META: dict[str, StageDocMeta] = {
    "s1_llm_prompt": StageDocMeta("大模型与 Prompt 工程", "07-大模型基础.md / 09-Prompt工程.md"),
    "s2_rag": StageDocMeta("RAG 技术", "03-RAG技术.md"),
    "s3_agent_tools": StageDocMeta("Agent 框架与工具", "01-基础概念.md / 02-核心框架.md / 04-工具调用.md"),
    "s4_memory_multi": StageDocMeta("记忆系统", "05-记忆系统.md"),
    "s5_engineering": StageDocMeta("工程化与项目表达", "08-工程化实践.md / 06-多智能体.md"),
}

STAGE_READING_UNITS: dict[str, tuple[ReadingUnit, ...]] = {
    "s1_llm_prompt": (
        ReadingUnit(
            "Transformer 与注意力机制",
            (
                "自注意力：每个 token 对序列中其他 token 计算权重，并行建模全局依赖",
                "Q/K/V 投影：Query 查、Key 被匹配、Value 提供内容，缩放点积后 softmax",
                "面试口述：为什么比 RNN 更适合长上下文并行训练",
            ),
        ),
        ReadingUnit(
            "Token、上下文窗口与成本",
            (
                "Token 是模型读写的基本单位；中英文、代码切分粒度不同",
                "上下文窗口决定一次能「看见」多少历史；超出需截断或摘要",
                "成本 ≈ 输入 token + 输出 token；长 prompt 与多轮对话都会累加",
            ),
        ),
        ReadingUnit(
            "温度、Top-p 与输出稳定性",
            (
                "temperature 越高分布越平，创意多但幻觉风险上升",
                "Top-p（nucleus）在累积概率阈值内采样，兼顾多样与可控",
                "生产场景常低温 + 结构化输出；探索/头脑风暴可略升温",
            ),
        ),
        ReadingUnit(
            "结构化 Prompt 设计",
            (
                "角色 + 任务 + 约束 + 输出格式，四段式最稳",
                "用 XML/JSON/Markdown 分隔指令与数据，减少模型串台",
                "负面约束写清楚「不要做什么」，比只说「做好」更有效",
            ),
        ),
        ReadingUnit(
            "Few-shot 与示例选择",
            (
                "示例数量 2～5 条通常够用；质量 > 数量",
                "示例应覆盖边界情况，且输入输出格式与真实请求一致",
                "动态示例检索（按相似度选 shot）比固定写死更省 token",
            ),
        ),
        ReadingUnit(
            "Chain-of-Thought 与推理链",
            (
                "显式要求「先分析再结论」，复杂题准确率明显提升",
                "可要求中间步骤结构化（步骤 1/2/3），便于断点审查",
                "面试点：CoT 增加延迟与 token，需在质量与成本间取舍",
            ),
        ),
    ),
    "s2_rag": (
        ReadingUnit(
            "文档分块（Chunking）策略",
            (
                "按标题/段落/固定长度分块；代码与表格需单独策略",
                "块太大检索噪声多，太小语义断裂；常 256～1024 token 试探",
                "重叠（overlap）可缓解边界截断，但索引体积会增大",
            ),
        ),
        ReadingUnit(
            "Embedding 与向量索引",
            (
                "文本 → 向量；语义相近的 chunk 在空间中距离更近",
                "常见索引：HNSW、IVF；需关注召回率与查询延迟",
                "同一知识库应固定 embedding 模型，换模型需全量重嵌",
            ),
        ),
        ReadingUnit(
            "检索：向量 + 关键词混合",
            (
                "纯向量对专有名词、版本号可能弱；BM25 补精确匹配",
                "RRF 等融合策略合并多路召回，工程上比手工加权稳",
                "面试口述：何时加 HyDE、Multi-Query、查询改写",
            ),
        ),
        ReadingUnit(
            "重排序（Rerank）",
            (
                "粗召回 top-K 后用 cross-encoder 精排，显著提升前 3 条质量",
                "Rerank 增加延迟；K 太大性价比低，常 20～50 → 取 top 5",
                "无 rerank 时可用 LLM 对候选打相关性分",
            ),
        ),
        ReadingUnit(
            "幻觉治理与引用",
            (
                "要求模型「仅依据检索片段回答」，无依据则明确说不知道",
                "返回引用 chunk id/页码，用户可核对来源",
                "CRAG/Self-RAG 思路：检索质量差时触发改写查询或拒答",
            ),
        ),
    ),
    "s3_agent_tools": (
        ReadingUnit(
            "ReAct 循环",
            (
                "Thought → Action → Observation 交替，直到得出 Final Answer",
                "Thought 暴露推理链，便于调试与断点审查",
                "工具返回的 Observation 必须结构化，避免模型误读长日志",
            ),
        ),
        ReadingUnit(
            "LangGraph 与状态机",
            (
                "用图节点表示步骤，边表示转移；比自由 ReAct 更可控",
                "状态对象集中管理 messages、tool results、用户上下文",
                "适合加检查点、人工审批、失败重试等生产化能力",
            ),
        ),
        ReadingUnit(
            "Tool Calling 设计",
            (
                "工具描述要含：用途、参数 schema、失败时行为",
                "参数校验在调用前完成，不要把脏数据交给外部 API",
                "幂等与超时：写操作需确认，长任务应异步 + 轮询",
            ),
        ),
        ReadingUnit(
            "MCP 与工具生态",
            (
                "Model Context Protocol：统一工具发现与调用协议",
                "对比「每个 Agent 手写集成」：MCP 降低重复胶水代码",
                "安全：工具权限最小化，敏感操作走 HITL",
            ),
        ),
    ),
    "s4_memory_multi": (
        ReadingUnit(
            "短期记忆（对话上下文）",
            (
                "滑动窗口保留最近 N 轮；超出用摘要压缩早期对话",
                "系统消息与工具结果占用同一窗口，需主动裁剪",
                "与「长期记忆」分工：短期管当前任务，长期管用户偏好",
            ),
        ),
        ReadingUnit(
            "长期记忆存储",
            (
                "用户事实、偏好、历史决策可写入向量库或结构化表",
                "写入前做去重与冲突检测，避免记忆污染",
                "检索记忆时带时间衰减或重要性权重",
            ),
        ),
        ReadingUnit(
            "多 Agent 协作模式",
            (
                "主管-工人：Planner 拆任务，Worker 执行，Reviewer 验收",
                "消息总线 vs 共享黑板：权衡耦合度与可观测性",
                "失败时谁重试、谁升级人工——需在架构层写清楚",
            ),
        ),
    ),
    "s5_engineering": (
        ReadingUnit(
            "可观测性：日志、追踪、指标",
            (
                "每次 LLM 调用记录：prompt 摘要、token、延迟、模型版本",
                "分布式 trace 串起 tool call 与多 Agent 步骤",
                "业务指标：任务成功率、人工接管率、平均轮次",
            ),
        ),
        ReadingUnit(
            "熔断、降级与超时",
            (
                "模型超时 → 换备用模型或模板回复，避免无限挂起",
                "工具连续失败触发熔断，防止 Agent 死循环调工具",
                "降级路径要在代码里显式实现，不能仅靠 prompt 祈祷",
            ),
        ),
        ReadingUnit(
            "Agent 评测",
            (
                "离线：固定数据集 + 自动评分（规则或 LLM-as-judge）",
                "在线：用户反馈、隐式信号（重试率、放弃率）",
                "评测集要覆盖工具失败、空检索、恶意输入等边界",
            ),
        ),
        ReadingUnit(
            "项目表达与面试证据",
            (
                "STAR：情境、任务、你的行动、量化结果",
                "技术题必须落到取舍：为什么选 A 不选 B，代价是什么",
                "准备 1～2 个可画图的真实链路（请求路径 + 失败处理）",
            ),
        ),
    ),
}

REVIEW_UNIT = ReadingUnit(
    "今日复习",
    (
        "合上文档，用自己的话复述今日 3 个要点",
        "对照复习卡，口述关键取舍与项目证据",
        "卡住的节点标记下来，明天训练时重点练",
    ),
)

CONSOLIDATE_UNIT = ReadingUnit(
    "巩固拓宽",
    (
        "复习到期卡片，每条控制在 2 分钟内口述",
        "开「项目模拟」，用 STAR 结构讲真实经历",
        "查漏补缺：对照学习路线，找还没闭环的主题",
    ),
)


def _topic_freestyle_unit(topic: str | None) -> tuple[str, str, tuple[str, ...]]:
    label = (topic or "").strip() or "今日主题"
    return (
        f"{label} 专题",
        f"{label} 面试表达",
        (
            f"用自己的话定义「{label}」并说明它解决什么问题",
            f"讲清 {label} 的关键机制（输入 → 处理 → 输出）",
            f"对比一个替代方案，说清为什么选 {label}（或何时不选）",
        ),
    )


def reading_unit_for_day(
    stage_id: str | None,
    *,
    task_type: str,
    day_index_in_stage: int,
    topic: str | None = None,
) -> tuple[str, str, tuple[str, ...]]:
    """Return (doc_title, section_title, bullets) for a plan day."""
    if task_type == "review":
        meta = STAGE_DOC_META.get(stage_id or "", StageDocMeta("复习", ""))
        return meta.doc_title, REVIEW_UNIT.section_title, REVIEW_UNIT.bullets

    if task_type == "consolidate":
        return "综合巩固", CONSOLIDATE_UNIT.section_title, CONSOLIDATE_UNIT.bullets

    if not stage_id:
        return _topic_freestyle_unit(topic)

    meta = STAGE_DOC_META.get(stage_id)
    units = STAGE_READING_UNITS.get(stage_id, ())
    if not meta or not units:
        return "学习资料", "今日阅读", ("阅读今日主题相关章节", "整理 3 条可复述要点")

    unit = units[day_index_in_stage % len(units)]
    return meta.doc_title, unit.section_title, unit.bullets


def stage_unit_count(stage_id: str | None) -> int:
    if not stage_id:
        return 1
    return max(1, len(STAGE_READING_UNITS.get(stage_id, ())))


def unit_key(stage_id: str, unit_index: int) -> str:
    return f"{stage_id}:{unit_index}"


def reading_bundle_for_unit_indices(
    stage_id: str | None,
    unit_indices: list[int],
    *,
    task_type: str = "train",
) -> tuple[str, str, tuple[str, ...], list[str]]:
    """
    Pack one or more curriculum units into a single day.
    Returns (doc_title, section_title, bullets, unit_keys).
    """
    if task_type == "review":
        meta = STAGE_DOC_META.get(stage_id or "", StageDocMeta("复习", ""))
        return meta.doc_title, REVIEW_UNIT.section_title, REVIEW_UNIT.bullets, []
    if task_type == "consolidate":
        return "综合巩固", CONSOLIDATE_UNIT.section_title, CONSOLIDATE_UNIT.bullets, []
    if not stage_id:
        doc_title, section_title, bullets = _topic_freestyle_unit(None)
        return doc_title, section_title, bullets, []

    meta = STAGE_DOC_META.get(stage_id)
    units = STAGE_READING_UNITS.get(stage_id, ())
    if not meta or not units:
        return "学习资料", "今日阅读", ("阅读今日主题相关章节", "整理 3 条可复述要点"), []

    indices = [i for i in unit_indices if 0 <= i < len(units)]
    if not indices:
        indices = [0]
    picked = [units[i] for i in indices]
    keys = [unit_key(stage_id, i) for i in indices]
    if len(picked) == 1:
        section = picked[0].section_title
    else:
        section = " · ".join(u.section_title for u in picked[:2])
        if len(picked) > 2:
            section += f" 等 {len(picked)} 节"
    bullets: list[str] = []
    for u in picked:
        bullets.extend(u.bullets)
    # Cap extreme packing so a single day stays learnable.
    return meta.doc_title, section, tuple(bullets[:12]), keys


def format_learning_doc_message(doc_title: str, section_title: str, bullets: tuple[str, ...]) -> str:
    lines = [f"📖 {doc_title} · {section_title}"]
    lines.extend(f"· {b}" for b in bullets[:4])
    return "\n".join(lines)
