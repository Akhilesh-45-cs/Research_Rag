from src.retrieval.retriever import get_retriever
from src.retrieval.bm25_search import bm25_search
from src.retrieval.reranker import rerank

def hybrid_search(query, top_k=8, only_papers=None, vector_weight=0.5, bm25_weight=0.5):
    """
    Combines vector similarity search and BM25 keyword search into one ranked result set.
    Uses min-max normalization on each score type before blending, since vector distances 
    and BM25 scores are on completely different scales.
    """
    collection, embedding_model = get_retriever()
    query_vector = embedding_model.embed_query(query)

    vector_n = top_k * 3  # over-fetch from each method before merging
    where_clause = {"source": {"$in": only_papers}} if only_papers else None

    vector_results = collection.query(
        query_embeddings=[query_vector],
        n_results=vector_n,
        where=where_clause
    )

    vector_hits = {}
    docs = vector_results["documents"][0]
    metas = vector_results["metadatas"][0]
    dists = vector_results["distances"][0]
    for doc, meta, dist in zip(docs, metas, dists):
        # cosine distance: lower = better, convert to a similarity score (higher = better)
        similarity = 1 - dist
        key = (doc, meta["source"])
        vector_hits[key] = {"text": doc, "source": meta["source"], "section": meta.get("section", ""), "vector_score": similarity}

    bm25_hits_list = bm25_search(query, top_k=vector_n, only_papers=only_papers)
    bm25_hits = {}
    for hit in bm25_hits_list:
        key = (hit["text"], hit["source"])
        bm25_hits[key] = hit["score"]

    # normalize each score type to 0-1 range before combining
    def normalize(values):
        if not values:
            return {}
        min_v, max_v = min(values.values()), max(values.values())
        if max_v == min_v:
            return {k: 1.0 for k in values}
        return {k: (v - min_v) / (max_v - min_v) for k, v in values.items()}

    vector_scores_raw = {k: v["vector_score"] for k, v in vector_hits.items()}
    vector_scores_norm = normalize(vector_scores_raw)
    bm25_scores_norm = normalize(bm25_hits)

    all_keys = set(vector_hits.keys()) | set(bm25_hits.keys())

    combined = []
    for key in all_keys:
        v_score = vector_scores_norm.get(key, 0)
        b_score = bm25_scores_norm.get(key, 0)
        final_score = (vector_weight * v_score) + (bm25_weight * b_score)

        text, source = key
        section = vector_hits.get(key, {}).get("section", "")
        combined.append({"text": text, "source": source, "section": section, "final_score": final_score})

    combined.sort(key=lambda x: x["final_score"], reverse=True)

    # Rerank only a small shortlist (not the whole combined set) for precision,
    # since cross-encoder scoring is slower than the vector/BM25 blend above
    shortlist = combined[:min(len(combined), top_k * 3)]
    reranked = rerank(query, shortlist, top_k=top_k)

    return reranked

if __name__ == "__main__":
    results = hybrid_search("RMSE MAE R2 CNN-LSTM results", top_k=5)
    for r in results:
        print(f"\nRerank Score: {r['rerank_score']:.3f} (hybrid blend: {r['final_score']:.3f}) | Source: {r['source']}")
        print(r["text"][:200])