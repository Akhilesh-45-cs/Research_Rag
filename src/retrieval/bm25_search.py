import chromadb
from rank_bm25 import BM25Okapi

DB_DIR = "data/vector_db"

_bm25_cache = None
_chunk_cache = None


def _build_bm25_index():
    """Builds (and caches) a BM25 index over all chunks currently in the DB."""
    global _bm25_cache, _chunk_cache

    client = chromadb.PersistentClient(path=DB_DIR)
    collection = client.get_or_create_collection(
        name="research_papers",
        metadata={"hnsw:space": "cosine"}
    )
    all_data = collection.get(include=["documents", "metadatas"])

    documents = all_data["documents"]
    metadatas = all_data["metadatas"]

    tokenized = [doc.lower().split() for doc in documents]
    bm25 = BM25Okapi(tokenized)

    _bm25_cache = bm25
    _chunk_cache = list(zip(documents, metadatas))

    return bm25, _chunk_cache


def bm25_search(query, top_k=10, only_papers=None):
    """Returns top_k chunks ranked by BM25 keyword relevance."""
    bm25, chunks = _build_bm25_index()  # rebuilt each call - fine for our scale, see note below

    tokenized_query = query.lower().split()
    scores = bm25.get_scores(tokenized_query)

    scored_chunks = list(zip(chunks, scores))
    scored_chunks.sort(key=lambda x: x[1], reverse=True)

    results = []
    for (doc, meta), score in scored_chunks:
        if only_papers and meta["source"] not in only_papers:
            continue
        results.append({"text": doc, "source": meta["source"], "section": meta.get("section", ""), "score": score})
        if len(results) >= top_k:
            break

    return results


if __name__ == "__main__":
    results = bm25_search("RMSE MAE R2 CNN-LSTM", top_k=5)
    for r in results:
        print(f"\nScore: {r['score']:.2f} | Source: {r['source']}")
        print(r["text"][:200])