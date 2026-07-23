import re
import chromadb
from src.embeddings.embedding_model import get_embedding_model

DB_DIR = "data/vector_db"

FILLER_WORDS = ["paper", "report", "article", "study", "document"]


def get_retriever():
    client = chromadb.PersistentClient(path=DB_DIR)
    collection = client.get_or_create_collection(
        name="research_papers",
        metadata={"hnsw:space": "cosine"}
    )
    embedding_model = get_embedding_model()
    return collection, embedding_model


def retrieve(query, top_k=5):
    collection, embedding_model = get_retriever()

    query_vector = embedding_model.embed_query(query)

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=top_k
    )

    return results


def print_results(results):
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for i in range(len(documents)):
        print(f"\n--- Result {i+1} ---")
        print(f"Source: {metadatas[i]['source']}")
        print(f"Similarity Distance: {distances[i]:.4f}  (lower = more similar)")
        print(f"Text: {documents[i][:300]}...")


def get_chunks_by_section(section_keyword="result", only_papers=None):
    collection, _ = get_retriever()
    all_data = collection.get(include=["documents", "metadatas"])

    grouped = {}
    for doc, meta in zip(all_data["documents"], all_data["metadatas"]):
        section = meta.get("section", "")
        source = meta["source"]
        if section_keyword in section.lower():
            if only_papers and source not in only_papers:
                continue
            grouped.setdefault(source, []).append(doc)

    return grouped


def get_all_paper_names():
    """Returns list of distinct source (paper) names currently in the DB."""
    collection, _ = get_retriever()
    all_data = collection.get(include=["metadatas"])
    sources = set(m["source"] for m in all_data["metadatas"])
    return list(sources)


def find_matching_paper(query, paper_names):
    """Checks if the query text contains words matching a known paper's name."""
    query_lower = query.lower()
    for name in paper_names:
        name_words = name.lower().replace("_", " ").replace("-", " ").split()
        matches = sum(1 for w in name_words if len(w) > 3 and w in query_lower)
        if matches >= 2:
            return name
    return None


def clean_query_for_paper_search(query, paper_name):
    """Removes words from the query that reference the paper's own name/filler terms,
    since these don't appear in the paper's actual body content and dilute embedding match."""
    cleaned = query.lower()

    for word in FILLER_WORDS:
        cleaned = re.sub(rf"\b{word}\b", "", cleaned)

    name_words = paper_name.lower().replace("_", " ").replace("-", " ").split()
    for word in name_words:
        if len(word) > 3:
            cleaned = re.sub(rf"\b{re.escape(word)}\b", "", cleaned)

    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if cleaned else query  # fallback to original if we stripped everything


def retrieve_from_paper(query, source_name, top_k=8):
    """Retrieves chunks ONLY from one specific paper, using hybrid (vector + BM25) search."""
    from src.retrieval.hybrid_search import hybrid_search  # local import avoids circular dependency

    cleaned_query = clean_query_for_paper_search(query, source_name)

    hybrid_results = hybrid_search(cleaned_query, top_k=top_k, only_papers=[source_name])

    result_keywords = ["result", "performance", "accuracy", "metric", "error", "rmse", "mae", "r2", "r²"]
    if any(kw in query.lower() for kw in result_keywords):
        boost_results = hybrid_search(
            "results performance metrics RMSE MAE R2 accuracy table",
            top_k=5,
            only_papers=[source_name]
        )
        existing_texts = set(r["text"] for r in hybrid_results)
        for r in boost_results:
            if r["text"] not in existing_texts:
                hybrid_results.append(r)
                existing_texts.add(r["text"])

    documents = [r["text"] for r in hybrid_results]
    metadatas = [{"source": r["source"], "section": r["section"]} for r in hybrid_results]

    return {"documents": [documents], "metadatas": [metadatas]}

def resolve_paper_names(candidate_names, all_paper_names):
    """
    Matches router-provided paper names (which may be slightly off - truncated, 
    missing prefixes, etc.) against the real paper names in the DB using substring matching.
    """
    resolved = []
    for candidate in candidate_names:
        candidate_clean = candidate.lower().strip()
        match = None

        for real_name in all_paper_names:
            real_clean = real_name.lower().strip()
            # exact match first
            if candidate_clean == real_clean:
                match = real_name
                break
            # substring match in either direction (handles missing prefixes/suffixes)
            if candidate_clean in real_clean or real_clean in candidate_clean:
                match = real_name
                break

        if match:
            resolved.append(match)

    return resolved


if __name__ == "__main__":
    print("Type your question below (type 'exit' to quit)\n")

    while True:
        query = input("Your question: ")
        if query.lower() == "exit":
            break

        results = retrieve(query, top_k=5)
        print_results(results)
        print("\n" + "=" * 50 + "\n")