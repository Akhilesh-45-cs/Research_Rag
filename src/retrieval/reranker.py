from sentence_transformers import CrossEncoder

_reranker_model = None


def get_reranker():
    """Loads the cross-encoder model once and caches it (first call downloads ~80MB)."""
    global _reranker_model
    if _reranker_model is None:
        _reranker_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _reranker_model


def rerank(query, candidates, top_k=8):
    """
    Re-scores a list of candidate chunks against the query using a cross-encoder,
    which is more precise than embedding similarity alone but slower - meant to run
    on a small shortlist (e.g. 15-20 candidates), not a whole library.

    candidates: list of dicts, each must have a "text" key.
    Returns the same dicts, sorted by relevance, with a "rerank_score" added, top_k only.
    """
    if not candidates:
        return []

    model = get_reranker()
    pairs = [[query, c["text"]] for c in candidates]
    scores = model.predict(pairs)

    for candidate, score in zip(candidates, scores):
        candidate["rerank_score"] = float(score)

    candidates.sort(key=lambda c: c["rerank_score"], reverse=True)
    return candidates[:top_k]


if __name__ == "__main__":
    test_query = "what is the RMSE and MAE for the LSTM model in SOC estimation"
    test_candidates = [
        {"text": "The LSTM model achieved an RMSE of 3.6076 and MAE of 3.1049 for SOC prediction."},
        {"text": "This paper discusses electric vehicle adoption trends globally."},
        {"text": "Random Forest achieved the lowest RMSE of 0.1298 among all tested models."},
        {"text": "Battery thermal management systems regulate temperature during charging."},
    ]

    results = rerank(test_query, test_candidates, top_k=4)
    for r in results:
        print(f"Score: {r['rerank_score']:.3f} | {r['text'][:80]}")