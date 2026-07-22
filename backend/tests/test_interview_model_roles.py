"""Model role routing + lexical rerank (P2)."""

from app.interview.model_roles import resolve_model_role
from app.interview.rerank import lexical_rerank


def test_resolve_model_roles_defaults():
    assert resolve_model_role("evaluate").model_id == "rules"
    assert resolve_model_role("hint").provider_hint == "rules"
    assert resolve_model_role("embed").provider_hint == "ollama"
    reflect = resolve_model_role("reflect")
    assert reflect.temperature == 0.1
    assert reflect.model_id


def test_lexical_rerank_boosts_overlap():
    docs = [
        ("a", "Python GIL 细节", 1.0),
        ("b", "向量召回与重排实践", 1.0),
        ("c", "React hooks", 1.0),
    ]
    ranked = lexical_rerank("向量 召回", docs, topic="RAG", level="P6")
    assert ranked[0][0] == "b"
