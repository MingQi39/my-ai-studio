"""
Ollama 适配器

本地部署的开源模型适配器，支持流式响应、视觉模型和思考模式。
使用 httpx 直接调用 Ollama API，提供更好的错误处理和超时控制。
"""

import json
import base64
import logging
from typing import AsyncIterator, Any

import httpx

from ..base import BaseLLMAdapter
from ..types import ChatMessage, ChatCompletionChunk, ModelInfo, ChatCompletionResponse
from ...exceptions import (
    ProviderConnectionError,
    ProviderTimeoutError,
    ModelUnavailableError,
)

logger = logging.getLogger(__name__)


class OllamaAdapter(BaseLLMAdapter):
    """Ollama 适配器

    特性：
    - 支持流式和非流式响应
    - 支持视觉模型（通过 base64 传图）
    - 支持思考模式（Qwen3 等模型）
    - 健康检查和模型存在性验证
    - 完善的错误处理和超时控制
    """

    PROVIDER = "ollama"
    DEFAULT_BASE_URL = "http://localhost:11434"

    # 已知支持视觉的模型前缀
    VISION_MODEL_PREFIXES = ("llava", "bakllava", "moondream", "minicpm-v")

    # 已知支持思考模式的模型前缀
    REASONING_MODEL_PREFIXES = ("qwen3", "deepseek-r1")

    @staticmethod
    def _normalize_base_url(url: str) -> str:
        """规范化 base_url

        Ollama 不使用 /v1 前缀，但用户可能会误加。
        自动移除 /v1 或 /v1/ 后缀。

        Args:
            url: 原始 URL

        Returns:
            规范化后的 URL
        """
        url = url.rstrip("/")  # 移除尾部斜杠
        
        # 移除 /v1 后缀（用户可能从其他 API 习惯中误加）
        if url.endswith("/v1"):
            url = url[:-3]
            logger.info(f"Removed /v1 suffix from Ollama base URL")
        
        return url

    def __init__(
        self,
        api_key: str = "",
        base_url: str | None = None,
        model_id: str = "",
        timeout: int = 300,
        connect_timeout: float = 10.0,
        enable_health_check: bool = True,
    ):
        """初始化 Ollama 适配器

        Args:
            api_key: API 密钥（Ollama 通常不需要）
            base_url: Ollama 服务地址（自动处理 /v1 后缀）
            model_id: 模型 ID（如 qwen3:0.6b）
            timeout: 请求超时时间（秒），首次加载模型建议设置较长
            connect_timeout: 连接超时时间（秒）
            enable_health_check: 是否在初始化时检查服务健康状态
        """
        # 规范化 base_url，移除 /v1 后缀（Ollama 不使用 /v1）
        normalized_url = self._normalize_base_url(base_url or self.DEFAULT_BASE_URL)
        
        super().__init__(
            api_key=api_key,
            base_url=normalized_url,
            model_id=model_id,
            timeout=timeout
        )
        self.connect_timeout = connect_timeout
        self.enable_health_check = enable_health_check

        # 初始化 httpx 客户端，使用分离的超时配置
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(
                connect=connect_timeout,
                read=float(timeout),
                write=30.0,
                pool=5.0
            ),
            # 禁用代理以避免连接问题
            trust_env=False,
        )

        # 模型信息缓存
        self._models_cache: list[dict] | None = None
        self._model_info_cache: dict[str, dict] = {}

    async def _check_health(self) -> bool:
        """检查 Ollama 服务是否可用

        Returns:
            服务是否可用
        """
        try:
            response = await self._client.get("/", timeout=5.0)
            return response.status_code == 200 and "Ollama" in response.text
        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False

    async def _fetch_models(self, use_cache: bool = True) -> list[dict]:
        """获取可用模型列表

        Args:
            use_cache: 是否使用缓存

        Returns:
            模型列表
        """
        if use_cache and self._models_cache is not None:
            return self._models_cache

        try:
            response = await self._client.get("/api/tags", timeout=10.0)
            response.raise_for_status()
            data = response.json()
            self._models_cache = data.get("models", [])
            return self._models_cache
        except httpx.ConnectError as e:
            raise ProviderConnectionError(
                provider=self.PROVIDER,
                endpoint=self.base_url
            ) from e
        except httpx.TimeoutException as e:
            raise ProviderTimeoutError(timeout_seconds=10) from e
        except Exception as e:
            logger.error(f"Failed to fetch models: {e}")
            return []

    async def _get_model_info(self, model_name: str) -> dict | None:
        """获取模型详细信息

        Args:
            model_name: 模型名称

        Returns:
            模型信息字典
        """
        if model_name in self._model_info_cache:
            return self._model_info_cache[model_name]

        try:
            response = await self._client.post(
                "/api/show",
                json={"name": model_name},
                timeout=10.0
            )
            if response.status_code == 200:
                info = response.json()
                self._model_info_cache[model_name] = info
                return info
        except Exception as e:
            logger.debug(f"Failed to get model info for {model_name}: {e}")

        return None

    async def _ensure_model_exists(self) -> None:
        """确保模型存在，不存在则抛出明确错误"""
        models = await self._fetch_models(use_cache=False)
        model_names = [m.get("name", "") for m in models]

        if self.model_id not in model_names:
            # 显示前 5 个可用模型
            available = model_names[:5] if model_names else ["(无可用模型)"]
            raise ModelUnavailableError(
                model_id=self.model_id,
                reason=f"Model not found on Ollama server. Available: {', '.join(available)}"
            )

    def _is_vision_model(self, model_name: str | None = None) -> bool:
        """判断是否为视觉模型"""
        name = (model_name or self.model_id).lower()
        return any(name.startswith(prefix) for prefix in self.VISION_MODEL_PREFIXES)

    def _is_reasoning_model(self, model_name: str | None = None) -> bool:
        """判断是否支持思考模式"""
        name = (model_name or self.model_id).lower()
        return any(name.startswith(prefix) for prefix in self.REASONING_MODEL_PREFIXES)

    def _convert_messages(self, messages: list[ChatMessage]) -> list[dict]:
        """转换消息格式为 Ollama 格式

        Ollama 格式：
        - role: user/assistant/system
        - content: 文本内容
        - images: base64 编码的图片列表（可选）
        """
        converted = []

        for msg in messages:
            ollama_msg: dict[str, Any] = {
                "role": msg.get("role", "user"),
            }

            content = msg.get("content")

            # 处理多模态内容
            if isinstance(content, list):
                text_parts = []
                images = []

                for block in content:
                    if isinstance(block, dict):
                        block_type = block.get("type")

                        if block_type == "text":
                            text_parts.append(block.get("text", ""))

                        elif block_type == "image_url":
                            # 从 image_url 结构中提取 URL
                            image_url = block.get("image_url", {})
                            if isinstance(image_url, dict):
                                url = image_url.get("url", "")
                            else:
                                url = str(image_url)

                            # 处理 base64 数据 URL
                            if url.startswith("data:"):
                                # 格式: data:image/jpeg;base64,xxxxx
                                try:
                                    base64_data = url.split(",", 1)[1]
                                    images.append(base64_data)
                                except IndexError:
                                    logger.warning(f"Invalid data URL format")
                            else:
                                # 普通 URL，Ollama 不直接支持，需要下载
                                logger.warning(f"Ollama doesn't support image URLs directly: {url[:50]}...")

                        elif block_type == "image_base64":
                            # 直接的 base64 数据
                            base64_data = block.get("image_base64", "")
                            if base64_data:
                                images.append(base64_data)

                ollama_msg["content"] = "\n".join(text_parts) if text_parts else ""

                if images:
                    ollama_msg["images"] = images

            else:
                # 纯文本内容
                ollama_msg["content"] = content or ""

            converted.append(ollama_msg)

        return converted

    async def chat_completion(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float | None = None,
        stream: bool = True,
        tools: list[dict] | None = None,
        **kwargs,
    ) -> AsyncIterator[ChatCompletionChunk] | ChatCompletionResponse:
        """执行聊天补全

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大生成 token 数
            top_p: Top-p 采样参数
            stream: 是否流式响应
            tools: 工具定义列表
            **kwargs: 其他参数
                - enable_reasoning: 是否启用思考模式（默认自动检测）

        Returns:
            流式响应时返回 AsyncIterator[ChatCompletionChunk]
            非流式响应时返回 ChatCompletionResponse
        """
        # 检查模型是否存在
        await self._ensure_model_exists()

        # 构建请求参数
        payload = self._build_request_payload(
            messages, temperature, max_tokens, top_p, stream, tools, **kwargs
        )

        try:
            if stream:
                return self._stream_chat(payload)
            else:
                return await self._complete_chat(payload)
        except httpx.ConnectError as e:
            raise ProviderConnectionError(
                provider=self.PROVIDER,
                endpoint=self.base_url
            ) from e
        except httpx.TimeoutException as e:
            raise ProviderTimeoutError(timeout_seconds=self.timeout) from e
        except ModelUnavailableError:
            raise
        except Exception as e:
            logger.error(f"Chat completion failed: {e}")
            raise ProviderConnectionError(
                provider=self.PROVIDER,
                endpoint=self.base_url
            ) from e

    def _build_request_payload(
        self,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int | None,
        top_p: float | None,
        stream: bool,
        tools: list[dict] | None,
        **kwargs,
    ) -> dict:
        """构建 Ollama API 请求参数"""
        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": self._convert_messages(messages),
            "stream": stream,
            "options": {
                "temperature": temperature,
            }
        }

        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens

        if top_p is not None:
            payload["options"]["top_p"] = top_p

        # 处理思考模式
        enable_reasoning = kwargs.get("enable_reasoning")
        if enable_reasoning is None:
            enable_reasoning = self._is_reasoning_model()

        if enable_reasoning:
            # Qwen3 等模型的思考模式通过 /think 标签触发
            # 或者通过 options 设置
            payload["options"]["num_ctx"] = kwargs.get("num_ctx", 32768)

        # 工具调用
        if tools:
            payload["tools"] = tools

        return payload

    async def _stream_chat(self, payload: dict) -> AsyncIterator[ChatCompletionChunk]:
        """处理流式聊天响应

        Ollama 返回 NDJSON 格式（每行一个 JSON 对象）
        """
        try:
            async with self._client.stream(
                "POST",
                "/api/chat",
                json=payload,
                timeout=httpx.Timeout(
                    connect=self.connect_timeout,
                    read=float(self.timeout),
                    write=30.0,
                    pool=5.0
                )
            ) as response:
                # 检查响应状态
                if response.status_code == 404:
                    error_text = ""
                    async for chunk in response.aiter_text():
                        error_text += chunk
                    try:
                        error_data = json.loads(error_text)
                        error_msg = error_data.get("error", "Model not found")
                    except json.JSONDecodeError:
                        error_msg = error_text or "Model not found"
                    raise ModelUnavailableError(
                        model_id=self.model_id,
                        reason=error_msg
                    )

                response.raise_for_status()

                # 用于追踪思考模式
                in_thinking = False

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse JSON line: {line[:100]}")
                        continue

                    # 处理错误
                    if "error" in data:
                        yield ChatCompletionChunk(
                            type="error",
                            content=None,
                            thinking=None,
                            tool_call=None,
                            usage=None,
                            error=data["error"],
                        )
                        return

                    # 处理消息内容
                    if "message" in data:
                        msg = data["message"]
                        content = msg.get("content", "")

                        if content:
                            # 检测思考模式标签
                            # Qwen3 使用 <think>...</think> 标签
                            if "<think>" in content:
                                in_thinking = True
                                # 移除开始标签
                                content = content.replace("<think>", "")

                            if "</think>" in content:
                                in_thinking = False
                                # 移除结束标签，分离思考和正常内容
                                parts = content.split("</think>")
                                if len(parts) > 1:
                                    thinking_part = parts[0]
                                    normal_part = parts[1]

                                    if thinking_part:
                                        yield ChatCompletionChunk(
                                            type="thinking",
                                            content=None,
                                            thinking=thinking_part,
                                            tool_call=None,
                                            usage=None,
                                            error=None,
                                        )

                                    if normal_part:
                                        yield ChatCompletionChunk(
                                            type="content",
                                            content=normal_part,
                                            thinking=None,
                                            tool_call=None,
                                            usage=None,
                                            error=None,
                                        )
                                    continue
                                else:
                                    content = content.replace("</think>", "")

                            # 输出内容
                            if in_thinking:
                                yield ChatCompletionChunk(
                                    type="thinking",
                                    content=None,
                                    thinking=content,
                                    tool_call=None,
                                    usage=None,
                                    error=None,
                                )
                            else:
                                yield ChatCompletionChunk(
                                    type="content",
                                    content=content,
                                    thinking=None,
                                    tool_call=None,
                                    usage=None,
                                    error=None,
                                )

                        # 处理工具调用
                        tool_calls = msg.get("tool_calls")
                        if tool_calls:
                            for tool_call in tool_calls:
                                yield ChatCompletionChunk(
                                    type="tool_call",
                                    content=None,
                                    thinking=None,
                                    tool_call=tool_call,
                                    usage=None,
                                    error=None,
                                )

                    # 完成标志
                    if data.get("done"):
                        # 提取 usage 信息
                        usage = None
                        if "prompt_eval_count" in data or "eval_count" in data:
                            usage = {
                                "prompt_tokens": data.get("prompt_eval_count", 0),
                                "completion_tokens": data.get("eval_count", 0),
                                "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
                            }

                            # 添加额外的性能指标
                            if "eval_duration" in data:
                                eval_duration_sec = data["eval_duration"] / 1e9
                                eval_count = data.get("eval_count", 0)
                                if eval_duration_sec > 0 and eval_count > 0:
                                    usage["tokens_per_second"] = eval_count / eval_duration_sec

                        if usage:
                            yield ChatCompletionChunk(
                                type="usage",
                                content=None,
                                thinking=None,
                                tool_call=None,
                                usage=usage,
                                error=None,
                            )

                        yield ChatCompletionChunk(
                            type="done",
                            content=None,
                            thinking=None,
                            tool_call=None,
                            usage=None,
                            error=None,
                        )
                        return

        except httpx.ConnectError as e:
            raise ProviderConnectionError(
                provider=self.PROVIDER,
                endpoint=self.base_url
            ) from e
        except httpx.TimeoutException as e:
            raise ProviderTimeoutError(timeout_seconds=self.timeout) from e
        except ModelUnavailableError:
            raise
        except Exception as e:
            logger.error(f"Stream chat failed: {e}")
            yield ChatCompletionChunk(
                type="error",
                content=None,
                thinking=None,
                tool_call=None,
                usage=None,
                error=str(e),
            )

    async def _complete_chat(self, payload: dict) -> ChatCompletionResponse:
        """处理非流式聊天响应"""
        payload["stream"] = False

        response = await self._client.post(
            "/api/chat",
            json=payload,
        )

        if response.status_code == 404:
            try:
                error_data = response.json()
                error_msg = error_data.get("error", "Model not found")
            except json.JSONDecodeError:
                error_msg = response.text or "Model not found"
            raise ModelUnavailableError(
                model_id=self.model_id,
                reason=error_msg
            )

        response.raise_for_status()
        data = response.json()

        # 提取响应内容
        message = data.get("message", {})
        content = message.get("content", "")
        reasoning_content = None

        # 处理思考模式内容
        if "<think>" in content and "</think>" in content:
            import re
            think_match = re.search(r"<think>(.*?)</think>", content, re.DOTALL)
            if think_match:
                reasoning_content = think_match.group(1).strip()
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

        # 构建 usage 信息
        usage = None
        if "prompt_eval_count" in data or "eval_count" in data:
            usage = {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
            }

        return ChatCompletionResponse(
            content=content,
            reasoning_content=reasoning_content,
            tool_calls=message.get("tool_calls"),
            usage=usage,
            model=data.get("model", self.model_id),
            finish_reason="stop" if data.get("done") else None,
        )

    async def list_models(self) -> list[ModelInfo]:
        """列出可用模型"""
        try:
            models = await self._fetch_models(use_cache=False)

            result = []
            for model in models:
                name = model.get("name", "")
                details = model.get("details", {})

                # 根据模型名称推断能力
                supports_vision = self._is_vision_model(name)
                supports_reasoning = self._is_reasoning_model(name)

                # 从 details 中获取更多信息
                family = details.get("family", "").lower()
                if "llava" in family or "vision" in family:
                    supports_vision = True

                result.append(ModelInfo(
                    id=name,
                    name=model.get("name", name),
                    context_length=details.get("context_length", 4096),
                    supports_vision=supports_vision,
                    supports_tools=True,  # 大多数现代模型支持
                    supports_reasoning=supports_reasoning,
                    supports_audio=False,
                ))

            return result

        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []

    async def validate_credentials(self) -> bool:
        """验证服务可用性

        对于 Ollama，这主要检查服务是否运行以及模型是否存在
        """
        try:
            # 检查服务健康状态
            if not await self._check_health():
                return False

            # 检查模型是否存在
            if self.model_id:
                models = await self._fetch_models()
                model_names = [m.get("name", "") for m in models]
                if self.model_id not in model_names:
                    logger.warning(f"Model {self.model_id} not found. Available: {model_names}")
                    return False

            return True

        except Exception as e:
            logger.error(f"Credential validation failed: {e}")
            return False

    def supports_feature(self, feature: str) -> bool:
        """检查是否支持特定功能

        Args:
            feature: 功能名称 (vision, tools, reasoning, audio, streaming)

        Returns:
            是否支持
        """
        feature_map = {
            "vision": self._is_vision_model(),
            "tools": True,  # 大多数模型支持
            "reasoning": self._is_reasoning_model(),
            "audio": False,  # Ollama 目前不支持音频
            "streaming": True,  # 总是支持流式
        }
        return feature_map.get(feature, False)

    async def close(self) -> None:
        """关闭 HTTP 客户端连接"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def __repr__(self) -> str:
        return f"OllamaAdapter(base_url={self.base_url!r}, model={self.model_id!r})"
