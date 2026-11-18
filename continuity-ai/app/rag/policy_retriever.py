def search(store, query: str, k: int = 3, category: str | None = None) -> dict:
    """Policy RAG retrieval with an abstain rule: below the similarity threshold we report
    'not found' instead of handing weak matches to the LLM."""
    hits = store.query(query, k=k, category=category)
    good = [h for h in hits if h["score"] >= store.embedder.min_score]
    return {"found": bool(good), "hits": good, "threshold": store.embedder.min_score}
