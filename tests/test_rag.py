from fpa.rag import DocIndex


def test_pinned_chunks_always_included():
    docs = DocIndex("tfidf").retrieve(["gross margin definition"])
    ids = {c.id for c in docs}
    assert {"glossary#narrative-rules", "glossary#materiality", "reporting_notes#sign-conventions"} <= ids
    assert "glossary#gross-margin-percent" in ids


def test_retrieval_finds_relevant_chunk():
    top = DocIndex("tfidf").backend.search("discount rate definition", 1)[0][0]
    assert top.id == "glossary#discount-rate"
