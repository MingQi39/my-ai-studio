"""Embedding circuit breaker for interview RAG."""

import pytest

from app.core.exceptions import CircuitBreakerOpenError
from app.core.retry import (
    CircuitBreakerConfig,
    CircuitBreakerState,
    circuit_breaker_registry,
)
from app.interview.embedding_service import EmbeddingError, OllamaEmbeddingService


@pytest.fixture(autouse=True)
def _fresh_breaker():
    name = "interview_embedding"
    breaker = circuit_breaker_registry.get_or_create(
        name,
        CircuitBreakerConfig(failure_threshold=2, recovery_timeout=60, half_open_max_calls=1),
    )
    breaker.config = CircuitBreakerConfig(
        failure_threshold=2, recovery_timeout=60, half_open_max_calls=1
    )
    # Force closed between tests (sync fields; avoid create_task race).
    breaker._state = CircuitBreakerState.CLOSED
    breaker._failure_count = 0
    breaker._success_count = 0
    breaker._last_failure_time = None
    yield
    breaker._state = CircuitBreakerState.CLOSED
    breaker._failure_count = 0


@pytest.mark.asyncio
async def test_embed_opens_circuit_after_failures(monkeypatch):
    svc = OllamaEmbeddingService(base_url="http://127.0.0.1:9", model="fake", timeout=0.1)

    async def boom(_texts):
        raise EmbeddingError("down")

    monkeypatch.setattr(svc, "_embed_texts_raw", boom)

    with pytest.raises(EmbeddingError):
        await svc.embed_texts(["a"])
    with pytest.raises(EmbeddingError):
        await svc.embed_texts(["b"])

    # Third call should fail fast via open circuit
    with pytest.raises(EmbeddingError) as exc:
        await svc.embed_texts(["c"])
    assert "circuit" in str(exc.value).lower() or "熔断" in str(exc.value)


@pytest.mark.asyncio
async def test_open_circuit_skips_raw_call(monkeypatch):
    svc = OllamaEmbeddingService(base_url="http://127.0.0.1:9", model="fake", timeout=0.1)
    breaker = circuit_breaker_registry.get_or_create("interview_embedding")
    breaker._state = CircuitBreakerState.OPEN
    from datetime import datetime, timedelta

    breaker._last_failure_time = datetime.utcnow()  # not yet recoverable

    called = {"n": 0}

    async def raw(_texts):
        called["n"] += 1
        return [[0.1]]

    monkeypatch.setattr(svc, "_embed_texts_raw", raw)

    with pytest.raises(EmbeddingError):
        await svc.embed_texts(["x"])
    assert called["n"] == 0
