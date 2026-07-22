"""Lightweight training attempt orchestrator (retrieve → evaluate → optional reflect)."""

from __future__ import annotations

from typing import Any, Protocol

from app.config import settings
from app.interview.attempt_fsm import RULE_VERSION
from app.interview.question_bank_retrieval import RetrievedQuestion, retrieval_span_dict
from app.interview.route_reflector import (
    RouteReflection,
    merge_rule_and_reflection,
    rule_reflect,
)
from app.interview.training import evaluate_answer


class RetrieverProtocol(Protocol):
    async def retrieve_with_meta(self, **kwargs: Any) -> RetrievedQuestion | None:
        ...


def evaluate_with_optional_reflect(
    *,
    answer: str,
    focus_node: str | None,
    question: str,
    route_nodes: list[str],
    reflection: RouteReflection | None = None,
    enable_llm_reflect: bool = False,
    retrieval_span: dict | None = None,
) -> dict[str, Any]:
    """Rule eval first; optionally merge route reflection. Never emits full answers."""
    raw = evaluate_answer(answer, focus_node=focus_node)
    # Always run cheap rule reflection for suspicious metrics
    auto = rule_reflect(answer=answer, focus_node=focus_node or raw.get("breakpoint"))  # type: ignore[arg-type]
    merged_reflection = reflection
    if merged_reflection is None and (auto.hallucinated_metrics or enable_llm_reflect):
        merged_reflection = auto
    elif merged_reflection is not None and auto.hallucinated_metrics:
        metrics = list(dict.fromkeys([*merged_reflection.hallucinated_metrics, *auto.hallucinated_metrics]))
        merged_reflection = RouteReflection(
            covered=merged_reflection.covered,
            missing=merged_reflection.missing,
            hallucinated_metrics=metrics,
            min_hint=merged_reflection.min_hint or auto.min_hint,
            source=merged_reflection.source,
            raw_model_output=merged_reflection.raw_model_output,
            parse_error=merged_reflection.parse_error,
        )

    if merged_reflection is not None:
        body = merge_rule_and_reflection(raw, merged_reflection)
    else:
        body = dict(raw)
        body["llm"] = None

    return {
        "covered_nodes": list(body["covered_nodes"]),
        "missing_nodes": list(body["missing_nodes"]),
        "breakpoint": body.get("breakpoint"),
        "hint": body.get("hint") if isinstance(body.get("hint"), dict) else None,
        "next_step": str(body["next_step"]),
        "complete": bool(body["complete"]),
        "deterministic": {
            "rule_version": RULE_VERSION,
            "signals_hit": raw.get("signals_hit") or {},
        },
        "llm": body.get("llm"),
        "status": "ok",
        "retrieval": retrieval_span,
        "signals_hit": raw.get("signals_hit") or {},
    }


class TrainingOrchestrator:
    """Explicit fallback-friendly pipeline; does not produce Final Answers."""

    def __init__(self, retriever: RetrieverProtocol | None = None):
        self.retriever = retriever

    async def retrieve_question(
        self,
        *,
        role: str | None,
        topic: str,
        level: str,
        focus_node: str | None = None,
        exclude_questions: set[str] | None = None,
        prefer_source_url_substr: str | None = None,
        prefer_source_section_substr: str | None = None,
    ) -> RetrievedQuestion | None:
        if self.retriever is None:
            raise RuntimeError("retriever not configured")
        return await self.retriever.retrieve_with_meta(
            role=role,
            topic=topic,
            level=level,
            focus_node=focus_node,
            exclude_questions=exclude_questions,
            prefer_source_url_substr=prefer_source_url_substr,
            prefer_source_section_substr=prefer_source_section_substr,
        )

    @staticmethod
    def retrieval_span(q: RetrievedQuestion | None) -> dict | None:
        return retrieval_span_dict(q)

    def evaluate(
        self,
        *,
        answer: str,
        focus_node: str | None,
        question: str,
        route_nodes: list[str],
        retrieval_span: dict | None = None,
        reflection: RouteReflection | None = None,
    ) -> dict[str, Any]:
        enable = bool(getattr(settings, "INTERVIEW_ROUTE_REFLECTION_LLM", False))
        return evaluate_with_optional_reflect(
            answer=answer,
            focus_node=focus_node,
            question=question,
            route_nodes=route_nodes,
            reflection=reflection,
            enable_llm_reflect=enable,
            retrieval_span=retrieval_span,
        )
