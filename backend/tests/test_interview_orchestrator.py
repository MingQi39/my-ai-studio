"""Orchestrator pipeline shape (retrieve → evaluate → optional reflect)."""

import pytest

from app.interview.orchestrator import TrainingOrchestrator, evaluate_with_optional_reflect


def test_evaluate_pipeline_rule_only():
    result = evaluate_with_optional_reflect(
        answer="SSE 用来推消息，机制是长连接",
        focus_node="Trade-off",
        question="SSE vs WebSocket",
        route_nodes=["Position", "Mechanism", "Trade-off", "Evidence"],
        reflection=None,
        enable_llm_reflect=False,
    )
    assert result["status"] == "ok"
    assert "Trade-off" in result["missing_nodes"]
    assert result["deterministic"]["rule_version"]
    assert result.get("retrieval") is None


def test_evaluate_pipeline_attaches_retrieval_span():
    retrieval = {
        "mode": "hybrid",
        "score": 0.81,
        "vector_score": 0.77,
        "bm25_score": 3.2,
        "degraded": False,
        "item_id": "abc",
    }
    result = evaluate_with_optional_reflect(
        answer="只有立场",
        focus_node="Position",
        question="q",
        route_nodes=["Position", "Mechanism", "Trade-off", "Evidence"],
        reflection=None,
        enable_llm_reflect=False,
        retrieval_span=retrieval,
    )
    assert result["retrieval"]["mode"] == "hybrid"
    assert result["retrieval"]["degraded"] is False


@pytest.mark.asyncio
async def test_orchestrator_retrieve_fallback_marks_degraded():
    class FakeRetriever:
        async def retrieve_with_meta(self, **kwargs):
            from app.interview.question_bank_retrieval import RetrievedQuestion

            return RetrievedQuestion(
                item_id="x",
                question="fallback q",
                topic="RAG",
                level="P6",
                source_url=None,
                source_title=None,
                source_section=None,
                retrieval_score=0.0,
                retrieval_mode="metadata_fallback",
                degraded=True,
                degraded_reason="embedding_circuit_open",
                vector_score=None,
                bm25_score=None,
            )

    orch = TrainingOrchestrator(retriever=FakeRetriever())
    got = await orch.retrieve_question(role="AI", topic="RAG", level="P6")
    assert got is not None
    assert got.degraded is True
    assert got.degraded_reason == "embedding_circuit_open"
    span = orch.retrieval_span(got)
    assert span["mode"] == "metadata_fallback"
    assert span["degraded"] is True
