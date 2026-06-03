"""
OMP / One Hub 适配器

将本机 ~/.omp/agent/models.yml 配置的 OpenAI 兼容网关直接接入本系统。
凭证（base_url + api_key + model_id）来源于用户在前端创建的 ModelConfig。

复用 OpenAICompatibleAdapter，使其支持 /v1/models /v1/chat/completions 等标准端点。

注意：OMP / One Hub 背后的部分上游（Anthropic on Bedrock、Doubao）已经拒绝
OpenAI 兼容字段 `temperature` / `top_p`，会直接 400 拒绝。本适配器默认把它们
从请求里剥掉；调用方仍然可以通过传 ``temperature=...`` / ``top_p=...`` 显式
覆盖（值为 ``None`` 表示不发送）。
"""

from __future__ import annotations

from typing import Any

from ..official.base import OpenAICompatibleAdapter
from ..types import ChatMessage


class OmpAdapter(OpenAICompatibleAdapter):
    """OMP / One Hub OpenAI-兼容网关适配器"""

    PROVIDER = "omp"
    # 仅作为占位；实际 base_url 必须由 ModelConfig 提供
    DEFAULT_BASE_URL = "http://localhost:30131/v1"

    def _build_request_params(
        self,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int | None,
        top_p: float | None,
        stream: bool,
        tools: list[dict] | None,
        **kwargs: Any,
    ) -> dict:
        params: dict[str, Any] = {
            "model": self.model_id,
            "messages": self._convert_messages(messages),
            "stream": stream,
        }
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        if tools:
            params["tools"] = tools
        # 默认不发送 temperature / top_p；如果 caller 明确传了非默认值，再带上
        explicit_temp = kwargs.pop("temperature", None)
        if explicit_temp is not None:
            params["temperature"] = explicit_temp
        explicit_top_p = kwargs.pop("top_p", None)
        if explicit_top_p is not None:
            params["top_p"] = explicit_top_p
        # OMP 网关不认 OpenAI SDK 之外的扩展字段，丢弃 ChatService 透传的私有参数
        for unsupported in ("enable_reasoning",):
            kwargs.pop(unsupported, None)
        # 透传剩余的 OpenAI-兼容字段（仅在未被显式覆盖时填入）
        for key, value in kwargs.items():
            params.setdefault(key, value)
        return params