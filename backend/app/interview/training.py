"""Goal-driven interview prompts: role + difficulty + salary, optionally enriched by resume."""

from __future__ import annotations

from dataclasses import dataclass


ROUTE_NODES = (
    "Position",
    "Principle",
    "Mechanism",
    "Trade-off",
    "Evidence",
)

NODE_SIGNALS: dict[str, tuple[str, ...]] = {
    "Position": ("解决", "问题", "场景", "需求", "目标", "用于", "用来", "what", "problem", "use case"),
    "Principle": ("原理", "本质", "核心", "因为", "所以", "why", "principle", "idea"),
    "Mechanism": ("怎么", "如何", "流程", "机制", "实现", "步骤", "协议", "how", "mechanism", "flow"),
    "Trade-off": ("取舍", "权衡", "对比", "而不是", "替代", "优缺点", "代价", "trade", "instead", "vs", "versus"),
    "Evidence": ("项目", "线上", "生产", "指标", "延迟", "我们", "我负责", "证据", "evidence", "latency", "prod"),
}

NODE_HINTS: dict[str, dict[str, str]] = {
    "Position": {
        "recall": "它首先解决的是什么通信/业务问题？",
        "keywords": "适用场景 · 问题边界 · 谁受益",
        "example": "先用一句话定位：它解决的是哪一类问题、在什么边界内成立。",
    },
    "Principle": {
        "recall": "它依赖的底层原则是什么？",
        "keywords": "核心约束 · 为什么这样抽象",
        "example": "补一句原则：抓住不可妥协的约束，再说因此采用的思路。",
    },
    "Mechanism": {
        "recall": "关键路径是怎样走完的？",
        "keywords": "主路径 · 关键步骤 · 失败点",
        "example": "按时间线说：输入 → 关键处理 → 输出，并点出最容易坏的一环。",
    },
    "Trade-off": {
        "recall": "和最容易混淆的替代方案比，你为什么留下这个？",
        "keywords": "替代方案 · 成本 · 复杂度 · 适用边界",
        "example": "先点名一个具体替代方案，再说在什么约束下你不选它。",
    },
    "Evidence": {
        "recall": "你的项目里有什么可核对的证据？",
        "keywords": "职责 · 现象 · 结果（不编造数字）",
        "example": "只说你确认过的事实；没有指标就明确说没有。",
    },
}

ATLAS_BY_SKILL: dict[str, list[str]] = {
    "SSE": ["HTTP", "streaming", "SSE", "reconnect"],
    "WebSocket": ["HTTP", "duplex", "WebSocket", "heartbeat"],
    "React": ["UI state", "React", "re-render", "effects"],
    "TypeScript": ["JS runtime", "types", "TypeScript", "contracts"],
    "FastAPI": ["HTTP API", "ASGI", "FastAPI", "deps"],
    "Docker": ["process", "image", "Docker", "compose"],
    "LLM": ["prompt", "LLM", "tool use", "eval"],
    "RAG": ["retrieval", "embedding", "RAG", "grounding"],
    "LangGraph": ["agent loop", "graph", "LangGraph", "checkpoint"],
    "Agent": ["LLM", "planning", "tools", "Agent", "feedback loop"],
    "Memory": ["context", "short-term", "long-term", "Memory", "compaction"],
    "Redis": ["cache", "Redis", "TTL", "invalidation"],
    "PostgreSQL": ["SQL", "transactions", "PostgreSQL", "indexes"],
    "Kubernetes": ["containers", "orchestration", "Kubernetes", "rollout"],
    "性能优化": ["瓶颈定位", "度量", "性能优化", "回归"],
    "系统设计": ["需求边界", "容量", "系统设计", "权衡"],
    "组件设计": ["职责拆分", "组件设计", "状态边界", "复用"],
    "API 设计": ["资源模型", "API 设计", "兼容性", "错误处理"],
    "缓存": ["读路径", "缓存", "失效", "一致性"],
    "可观测性": ["日志", "指标", "链路追踪", "告警"],
    "Agent 评测": ["任务定义", "评测集", "Agent 评测", "回归"],
    "Python": ["解释器", "GIL", "asyncio", "类型与工程"],
}

ROLE_TOPIC_BANK: dict[str, tuple[str, ...]] = {
    "前端": ("React", "TypeScript", "组件设计", "性能优化", "SSE", "WebSocket"),
    "全栈": ("React", "FastAPI", "TypeScript", "API 设计", "Docker", "SSE"),
    "后端": ("FastAPI", "PostgreSQL", "Redis", "API 设计", "缓存", "可观测性"),
    "AI 应用工程": (
        "LLM",
        "RAG",
        "Python",
        "Agent",
        "LangGraph",
        "Memory",
        "SSE",
        "Agent 评测",
        "可观测性",
        "FastAPI",
    ),
}

DEFAULT_STARTER_TOPICS: tuple[str, ...] = (
    "SSE",
    "React",
    "FastAPI",
    "LLM",
    "RAG",
    "Python",
    "Docker",
    "TypeScript",
    "WebSocket",
    "Redis",
    "LangGraph",
    "系统设计",
    "性能优化",
)

# UI difficulty → answer-route depth (P5/P6/P7)
DIFFICULTY_TO_LEVEL = {
    "初级": "P5",
    "中级": "P6",
    "高级": "P7",
    "P5": "P5",
    "P6": "P6",
    "P7": "P7",
}

# Concrete interview stems per skill × depth. PRD example: 「为什么不是 WebSocket？」
# Avoid empty shells like 「为什么选 X 而不是更常见的替代方案」.
TOPIC_QUESTIONS: dict[str, dict[str, str]] = {
    "SSE": {
        "P5": "SSE 解决的是哪一类通信问题？它在 HTTP 体系里处在什么位置？",
        "P6": "流式聊天 / 推送场景里，为什么选 SSE 而不是 WebSocket？断线后怎么恢复？",
        "P7": "落地 SSE 时，代理缓冲、重连状态、观测与容量你怎么处理？有什么可核对证据？",
    },
    "WebSocket": {
        "P5": "WebSocket 解决什么通信问题？和普通 HTTP 请求有何本质不同？",
        "P6": "什么时候必须用 WebSocket，而不是 SSE 或短轮询？讲清双向需求与成本。",
        "P7": "生产里 WebSocket 的心跳、重连风暴、水平扩展你怎么设计？证据是什么？",
    },
    "React": {
        "P5": "React 组件里「state 变化触发重渲染」解决的是什么问题？",
        "P6": "一个列表页要避免多余渲染：你会用 memo / 状态上提 / 拆分组件里的哪几种，取舍是什么？",
        "P7": "你在项目里定位过一次 React 性能问题吗？现象、排查路径与结果是什么？",
    },
    "TypeScript": {
        "P5": "TypeScript 类型系统首先帮你挡住哪类运行时问题？",
        "P6": "接口契约用 interface / zod / OpenAPI 生成类型，你会怎么选？各自代价是什么？",
        "P7": "类型与运行时校验不同步时你怎么兜底？举一个真实踩坑或防护。",
    },
    "FastAPI": {
        "P5": "FastAPI 适合解决什么 API 问题？它和 Flask/Django 的定位差在哪？",
        "P6": "依赖注入、Pydantic 校验、异步路由——你在接口设计里怎么取舍同步/异步？",
        "P7": "线上 FastAPI 服务的超时、依赖生命周期与错误模型你怎么落地？有何证据？",
    },
    "Docker": {
        "P5": "Docker 镜像解决的是什么交付问题？",
        "P6": "本地能跑、容器挂掉：你会查镜像层、环境变量还是卷挂载？为什么不直接上 K8s？",
        "P7": "镜像体积、多阶段构建与密钥注入你怎么做？出过什么事故或防护？",
    },
    "LLM": {
        "P5": "业务里直接调 LLM，它主要解决什么问题？边界在哪（不擅长什么）？",
        "P6": "同一需求：纯 Prompt、加 Tool calling、还是上 Agent 框架——你怎么选？",
        "P7": "幻觉、延迟、成本与安全（提示注入）你怎么在工程里控？有可核对指标吗？",
    },
    "RAG": {
        "P5": "企业知识库问答里，RAG 解决的是什么问题？它和「把文档整段塞进 Prompt」差在哪？",
        "P6": "什么场景该上 RAG，而不是 Fine-tuning 或长上下文直接塞文档？讲清检索、时效与成本的取舍。",
        "P7": "落地 RAG 时，分块/召回质量、权限隔离与幻觉你怎么处理？有哪些可核对的工程证据？",
    },
    "Python": {
        "P5": "写 Agent / 调模型服务时，Python 协程首先解决什么问题？和多线程差在哪？",
        "P6": "GIL 存在时，CPU 密集与 IO 密集（打多个模型 API）你会怎么选 asyncio / 线程 / 多进程？取舍是什么？",
        "P7": "线上 Python 服务里超时、取消、背压或 Typing/校验不同步，你怎么落地过？有何证据？",
    },
    "LangGraph": {
        "P5": "LangGraph（或同类图工作流）解决 Agent 编排里的什么问题？",
        "P6": "简单 ReAct 循环够用时，为什么还要上图/状态机？checkpoint 与人工介入点怎么取舍？",
        "P7": "多步 Agent 失败重试、状态恢复与评测你怎么做？举可核对例子。",
    },
    "Agent": {
        "P5": "一句话说明什么是 AI Agent？它和单次 LLM 调用差在哪？",
        "P6": "ReAct、Plan-and-Execute、纯 Tool calling——同一需求你怎么选？取舍是什么？",
        "P7": "Agent 死循环、工具选错或幻觉你怎么在工程里控？有可核对证据吗？",
    },
    "Memory": {
        "P5": "Agent 为什么需要记忆？没有会怎样？",
        "P6": "短期窗口记忆 vs 长期向量记忆，你会怎么分工与取舍？",
        "P7": "记忆脏数据、衰减误删重要事实时你怎么治理？举例子。",
    },
    "Redis": {
        "P5": "Redis 通常解决读路径上的什么问题？",
        "P6": "缓存穿透 / 击穿 / 雪崩里，你优先防哪一种？为什么不直接加长 TTL？",
        "P7": "缓存与 DB 一致性你怎么选？出过脏读或雪崩吗？证据是什么？",
    },
    "PostgreSQL": {
        "P5": "PostgreSQL 事务帮你保证什么？和「应用层自己拼」差在哪？",
        "P6": "慢查询你会先看索引、执行计划还是锁？什么时候该反范式？",
        "P7": "迁移、锁等待或主从延迟你怎么处理过？结果如何验证？",
    },
    "Kubernetes": {
        "P5": "K8s 相对单机 Docker Compose，主要解决什么运维问题？",
        "P6": "滚动发布与回滚：你如何在可用性与发布速度之间取舍？",
        "P7": "资源配额、探针失败或发布事故你怎么排查？证据是什么？",
    },
    "性能优化": {
        "P5": "性能优化前，你如何定义「慢」和成功标准？",
        "P6": "前端 / 后端 / 数据库，你通常按什么顺序定位瓶颈？为什么不是先改代码？",
        "P7": "讲一次你做过的优化：基线指标、改动与回归结果。",
    },
    "系统设计": {
        "P5": "接到一个系统设计题，你先澄清哪些边界？",
        "P6": "容量估算与瓶颈假设：你会先保可用性还是先保一致性？举例说明。",
        "P7": "讲一个你设计或改造过的系统：关键权衡与上线后的验证。",
    },
    "组件设计": {
        "P5": "拆组件时，你用什么标准判断「该不该拆」？",
        "P6": "状态放在父组件、Context 还是服务端——怎么选？各自代价？",
        "P7": "讲一个你重构过的组件/模块：前后职责与可测性变化。",
    },
    "API 设计": {
        "P5": "一个好的 HTTP API，资源命名与错误码首先要解决什么？",
        "P6": "分页、过滤、版本升级：向前兼容你怎么做？什么时候 breaking？",
        "P7": "线上 API 兼容事故或契约测试你怎么建？证据是什么？",
    },
    "缓存": {
        "P5": "加缓存前，你如何确认问题真的在读路径？",
        "P6": "旁路缓存 vs 读写穿透，你怎么选？失效策略如何定？",
        "P7": "缓存导致的一致性问题你怎么发现和修？",
    },
    "可观测性": {
        "P5": "日志、指标、链路追踪各回答什么问题？",
        "P6": "告警太多 vs 漏告警，你如何定 SLI/SLO 与噪声平衡？",
        "P7": "讲一次靠观测定位的线上问题：信号、路径与修复。",
    },
    "Agent 评测": {
        "P5": "Agent 评测和普通单元测试差在哪？评什么？",
        "P6": "离线集、线上影子流量、人工抽检——你会怎么组合？成本如何控？",
        "P7": "讲一次评测拦住回归或评测失灵的例子。",
    },
}

# Fallback only when topic is unknown / custom.
LEVEL_QUESTIONS = {
    "P5": "用 30 秒说明 {topic} 解决什么问题，以及它和相邻概念的边界。",
    "P6": "在真实业务里，什么场景该用 {topic}？和最容易混淆的替代方案比，关键取舍是什么？",
    "P7": "落地 {topic} 时你遇到过哪些工程约束与风险？可核对的证据是什么（没有就直说）？",
}

PROJECT_QUESTION = (
    "结合项目「{topic}」讲清一条经历路径："
    "用户/业务问题 → 你做的关键选择 → 与备选方案的取舍 → 可核对结果（没有指标就说明没有）。"
)

EXPERIENCE_QUESTION = (
    "结合工作经历「{topic}」讲清："
    "你的职责边界 → 一次关键决策 → 取舍理由 → 可核对结果。"
)


def normalize_level(difficulty: str | None, fallback: str = "P6") -> str:
    if not difficulty:
        return fallback
    return DIFFICULTY_TO_LEVEL.get(difficulty.strip(), fallback if fallback in {"P5", "P6", "P7"} else "P6")


def topics_for_role(role: str | None) -> tuple[str, ...]:
    if not role:
        return DEFAULT_STARTER_TOPICS
    key = role.strip()
    if key in ROLE_TOPIC_BANK:
        return ROLE_TOPIC_BANK[key]
    # Free-form role: keep a general full-stack-ish bank.
    return DEFAULT_STARTER_TOPICS


def pick_topic_from_bank(
    bank: tuple[str, ...] | list[str],
    practiced: set[str] | None = None,
    exclude: set[str] | None = None,
) -> str:
    practiced = practiced or set()
    exclude = exclude or set()
    for topic in bank:
        if topic not in practiced and topic not in exclude:
            return topic
    for topic in bank:
        if topic not in exclude:
            return topic
    return bank[len(practiced) % len(bank)]


def pick_starter_topic(
    practiced_topics: set[str] | None = None,
    role: str | None = None,
    exclude_topics: set[str] | None = None,
) -> str:
    return pick_topic_from_bank(topics_for_role(role), practiced_topics, exclude_topics)


@dataclass(frozen=True)
class TrainingPrompt:
    topic: str
    question: str
    atlas: list[str]
    route_nodes: list[str]
    missing_nodes: list[str]
    level: str
    category: str
    focus_node: str


def build_atlas(topic: str, category: str) -> list[str]:
    if category == "project":
        return ["用户问题", "方案候选", topic, "取舍", "工程证据", "结果"]
    if category == "role":
        return ["职责边界", "关键决策", topic, "取舍", "结果"]
    return ATLAS_BY_SKILL.get(topic, ["领域基础", "关联概念", topic, "Trade-off", "Engineering evidence"])


def build_training_prompt(
    *,
    topic: str,
    category: str,
    level: str = "P6",
    role: str | None = None,
    difficulty: str | None = None,
    salary_band: str | None = None,
    practiced_topics: set[str] | None = None,
    question_override: str | None = None,
) -> TrainingPrompt:
    _ = practiced_topics
    # Goal context (role / difficulty / salary) is frozen on the attempt / UI header,
    # not stuffed into every question stem — that produced empty shells like
    # 「为什么相关场景选 RAG」.
    _ = (role, difficulty, salary_band)

    atlas = build_atlas(topic, category)
    route_level = normalize_level(level) if level in {"P5", "P6", "P7"} else normalize_level(difficulty, "P6")
    focus = "Trade-off" if route_level == "P6" else ("Evidence" if route_level == "P7" else "Position")

    if category == "project":
        question = PROJECT_QUESTION.format(topic=topic)
        focus = "Evidence"
    elif category == "role":
        question = EXPERIENCE_QUESTION.format(topic=topic)
        focus = "Evidence"
    else:
        topic_bank = TOPIC_QUESTIONS.get(topic)
        if topic_bank and route_level in topic_bank:
            question = topic_bank[route_level]
        else:
            question = LEVEL_QUESTIONS.get(route_level, LEVEL_QUESTIONS["P6"]).format(topic=topic)

    if question_override:
        question = question_override

    return TrainingPrompt(
        topic=topic,
        question=question,
        atlas=atlas,
        route_nodes=list(ROUTE_NODES),
        missing_nodes=list(ROUTE_NODES),
        level=route_level,
        category=category,
        focus_node=focus,
    )


def evaluate_answer(answer: str, focus_node: str | None = None) -> dict[str, object]:
    text = (answer or "").strip().lower()
    covered: list[str] = []
    missing: list[str] = []
    signals_hit: dict[str, list[str]] = {}
    for node in ROUTE_NODES:
        signals = NODE_SIGNALS[node]
        hits = [signal for signal in signals if signal.lower() in text]
        if hits:
            covered.append(node)
            signals_hit[node] = hits[:3]
        else:
            missing.append(node)

    breakpoint = missing[0] if missing else None
    if focus_node and focus_node in missing:
        breakpoint = focus_node

    hint = None
    if breakpoint:
        meta = NODE_HINTS.get(breakpoint, {})
        hint = {
            "node": breakpoint,
            "recall": meta.get("recall", f"补上 {breakpoint}"),
            "keywords": meta.get("keywords", ""),
            "example": meta.get("example", ""),
        }

    return {
        "covered_nodes": covered,
        "missing_nodes": missing,
        "breakpoint": breakpoint,
        "hint": hint,
        "next_step": (
            f"用一句话补上「{breakpoint}」节点，然后重答。"
            if breakpoint
            else "路径已基本走通。可完成闭环，或提高一层难度再练。"
        ),
        "complete": len(missing) == 0,
        "signals_hit": signals_hit,
    }


def hint_for(node: str, level: int = 1) -> dict[str, str]:
    meta = NODE_HINTS.get(node, {})
    if level <= 1:
        return {"level": "1", "content": f"当前断点节点：{node}"}
    if level == 2:
        return {"level": "2", "content": meta.get("recall", f"回想：{node} 该怎么讲？")}
    if level == 3:
        return {"level": "3", "content": f"关键词：{meta.get('keywords', node)}"}
    return {"level": "4", "content": meta.get("example", f"组织方式：先点名 {node}，再用一句项目事实收尾。")}
