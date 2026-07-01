"""
OpenAI 客户端封装
提供异步客户端和流式生成功能
"""
from openai import AsyncOpenAI
from typing import AsyncGenerator


def get_async_client(api_key: str, base_url: str) -> AsyncOpenAI:
    """
    获取异步 OpenAI 客户端
    """
    return AsyncOpenAI(
        api_key=api_key,
        base_url=base_url
    )


async def stream_chat(
    client: AsyncOpenAI,
    messages: list,
    model: str
) -> AsyncGenerator[str, None]:
    """
    流式生成聊天回复
    """
    stream = await client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        temperature=0.7
    )

    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


async def complete_chat(
    client: AsyncOpenAI,
    messages: list,
    model: str,
    *,
    temperature: float = 0.3,
    response_format: dict | None = None,
) -> str:
    """Non-streaming chat completion."""
    kwargs: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format

    response = await client.chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""
