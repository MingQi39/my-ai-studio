"""Ollama embedding client for interview question bank (with circuit breaker)."""

from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.core.exceptions import CircuitBreakerOpenError
from app.core.retry import CircuitBreakerConfig, circuit_breaker_registry

logger = logging.getLogger(__name__)

EMBEDDING_BREAKER_NAME = "interview_embedding"


class EmbeddingError(Exception):
    """Raised when embedding provider fails."""


class OllamaEmbeddingService:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ):
        self.base_url = (base_url or settings.INTERVIEW_EMBEDDING_BASE_URL).rstrip("/")
        self.model = model or settings.INTERVIEW_EMBEDDING_MODEL
        self.timeout = timeout or settings.INTERVIEW_EMBEDDING_TIMEOUT

    def _breaker(self):
        return circuit_breaker_registry.get_or_create(
            EMBEDDING_BREAKER_NAME,
            CircuitBreakerConfig(
                failure_threshold=int(getattr(settings, "INTERVIEW_EMBEDDING_BREAKER_FAILURES", 3)),
                recovery_timeout=int(getattr(settings, "INTERVIEW_EMBEDDING_BREAKER_RECOVERY", 30)),
                half_open_max_calls=1,
            ),
        )

    async def _embed_texts_raw(self, texts: list[str]) -> list[list[float]]:
        payload = {"model": self.model, "input": texts}
        url = f"{self.base_url}/api/embed"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.ConnectError as exc:
            raise EmbeddingError(
                f"无法连接 Ollama（{self.base_url}）。请先启动 Ollama 并执行: ollama pull {self.model}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            text = ""
            try:
                text = exc.response.text or ""
            except Exception:
                text = ""
            if "model" in text.lower() and "not found" in text.lower():
                raise EmbeddingError(
                    f"Ollama 模型未找到：{self.model}。\n"
                    f"请先执行：ollama pull {self.model}"
                ) from exc
            raise EmbeddingError(f"Ollama embedding 请求失败: {text}") from exc
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(f"Ollama embedding 异常: {exc}") from exc

        embeddings = data.get("embeddings")
        if not embeddings:
            single = data.get("embedding")
            if single:
                embeddings = [single]
        if not embeddings or len(embeddings) != len(texts):
            raise EmbeddingError("Ollama 返回的 embedding 数量与输入不匹配")

        for vec in embeddings:
            if not vec or not isinstance(vec, list):
                raise EmbeddingError("Ollama 返回空向量")
        return embeddings

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        breaker = self._breaker()
        try:
            return await breaker.call(self._embed_texts_raw, texts)
        except CircuitBreakerOpenError as exc:
            raise EmbeddingError(
                f"embedding 熔断已打开（{EMBEDDING_BREAKER_NAME}），稍后重试或走元数据降级"
            ) from exc
        except EmbeddingError:
            raise

    async def embed_text(self, text: str) -> list[float]:
        vectors = await self.embed_texts([text])
        return vectors[0]

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False
