"""Ask AI about a quoted snippet from a daily learning document."""

from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.interview.model_roles import resolve_model_role
from app.interview.schemas import LearningDocAskRequest, LearningDocAskResponse

logger = logging.getLogger(__name__)

ASK_SYSTEM = """你是「面试导航」学习教练。用户从今日学习讲义中选中了一段文字，并向你提问。

硬性要求：
1. 先紧扣「引用原文」作答，不要跑题。
2. 面向技术面试：优先讲清是什么 → 怎么工作 → 面试怎么口述/怎么取舍。
3. 用中文，结构清晰；可用短条目，避免空话。
4. 若引用本身不完整，可合理补全语境，但要标明这是补充。
5. 不要编造虚假项目指标。"""


def _fallback_answer(*, quote: str, question: str, topic: str | None, section_title: str | None) -> str:
    scope = " / ".join(p for p in (topic, section_title) if p) or "今日讲义"
    return (
        f"## 针对引用的说明\n"
        f"这段属于「{scope}」。原文大意是：{quote.strip()[:180]}\n\n"
        f"## 回答你的问题\n"
        f"**问题**：{question.strip()}\n\n"
        f"1. 先用自己的话复述引用里的核心概念。\n"
        f"2. 再按「输入 → 计算/机制 → 输出」讲清它怎么工作。\n"
        f"3. 面试收尾补一句：适用场景、代价，以及和相邻方案的对比。\n\n"
        f"> 当前为兜底答法（LLM 未配置或调用失败）。配置面试 HINT/DAILY_DOC 模型后可得到更贴合原文的解答。"
    )


async def _call_ask_llm(*, system: str, user: str) -> str | None:
    role = resolve_model_role("daily_doc")
    if role.provider_hint in {"rules", "template"}:
        role = resolve_model_role("hint")
    if role.provider_hint in {"rules", "template"}:
        return None

    base_url = (
        (getattr(settings, "INTERVIEW_DAILY_DOC_BASE_URL", "") or "").rstrip("/")
        or (settings.INTERVIEW_HINT_BASE_URL or "").rstrip("/")
        or (settings.INTERVIEW_RESUME_CRAFT_BASE_URL or "").rstrip("/")
    )
    if not base_url:
        return None
    api_key = (
        getattr(settings, "INTERVIEW_DAILY_DOC_API_KEY", "")
        or settings.INTERVIEW_HINT_API_KEY
        or settings.INTERVIEW_RESUME_CRAFT_API_KEY
        or ""
    )
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": role.model_id,
        "temperature": min(0.4, role.temperature + 0.05),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=90.0, trust_env=False) as client:
            resp = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
            if resp.status_code >= 400:
                logger.warning(
                    "learning_doc_ask_http_error",
                    extra={"status": resp.status_code, "model": role.model_id, "body": (resp.text or "")[:400]},
                )
                resp.raise_for_status()
            data = resp.json()
        message = data["choices"][0]["message"]
        content = message.get("content") or message.get("reasoning_content") or ""
        if isinstance(content, str) and content.strip():
            return content.strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("learning_doc_ask_failed", extra={"error": f"{type(exc).__name__}: {exc}"})
    return None


async def ask_about_learning_quote(data: LearningDocAskRequest) -> LearningDocAskResponse:
    quote = data.quote.strip()
    question = (data.question or "").strip() or "请解释这段话，并告诉我面试里怎么口述。"
    if len(quote) < 2:
        raise ValueError("请先选中讲义中的一段文字")
    if len(quote) > 4000:
        quote = quote[:4000]

    user_prompt = f"""## 讲义语境
- 主题：{data.topic or '未指定'}
- 章节：{data.section_title or '未指定'}
- 日期：{data.doc_date or '未指定'}

## 用户选中的引用
\"\"\"{quote}\"\"\"

## 用户问题
{question}

请直接给出可阅读的 Markdown 回答。"""

    answer = await _call_ask_llm(system=ASK_SYSTEM, user=user_prompt)
    if answer:
        return LearningDocAskResponse(
            answer=answer,
            quote=quote,
            question=question,
            generated_by="llm",
        )
    return LearningDocAskResponse(
        answer=_fallback_answer(
            quote=quote,
            question=question,
            topic=data.topic,
            section_title=data.section_title,
        ),
        quote=quote,
        question=question,
        generated_by="template",
    )
