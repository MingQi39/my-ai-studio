"""Pure-unit tests for hybrid question-bank retrieval helpers."""

from app.interview.bm25 import BM25Index, rrf_fuse, tokenize


def test_tokenize_zh_en():
    tokens = tokenize("RAG 向量检索 embedding rerank")
    assert "rag" in tokens
    assert "向" in tokens and "量" in tokens
    assert "embedding" in tokens


def test_bm25_ranks_keyword_match_higher():
    index = BM25Index()
    index.add_document("a", "如何设计 Agent 的上下文管理")
    index.add_document("b", "向量数据库如何做召回与重排")
    index.add_document("c", "Python GIL 和协程区别")
    ranked = index.search("向量 召回 重排", top_k=3)
    assert ranked
    assert ranked[0][0] == "b"
    if len(ranked) > 1:
        assert ranked[0][1] > ranked[1][1]


def test_rrf_fuse_prefers_docs_in_both_lists():
    vector_ranked = [("v", 0.9), ("both", 0.8), ("x", 0.7)]
    bm25_ranked = [("b", 5.0), ("both", 4.0), ("y", 1.0)]
    fused = rrf_fuse(vector_ranked, bm25_ranked, k=60)
    ids = [doc_id for doc_id, _ in fused]
    assert ids[0] == "both"
    assert "v" in ids and "b" in ids


def test_rrf_fuse_handles_empty_side():
    only_vec = rrf_fuse([("a", 1.0)], [], k=60)
    assert only_vec[0][0] == "a"
    only_bm = rrf_fuse([], [("b", 2.0)], k=60)
    assert only_bm[0][0] == "b"
