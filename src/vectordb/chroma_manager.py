import os
import chromadb
from src.embeddings.embedding_model import get_embedding_model

CHUNKS_DIR = "data/cache/chunks"
DB_DIR = "data/vector_db"

os.makedirs(DB_DIR, exist_ok=True)


def load_chunks():
    """Reads all *_chunks.txt files and returns list of (chunk_text, source_file, chunk_id, section)"""
    all_chunks = []

    for filename in os.listdir(CHUNKS_DIR):
        if filename.endswith("_chunks.txt"):
            path = os.path.join(CHUNKS_DIR, filename)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            parts = content.split("--- CHUNK ")[1:]
            for part in parts:
                # header looks like: "0 | SECTION: introduction ---\n<chunk text>\n\n"
                header, chunk_text = part.split(" ---\n", 1)
                chunk_id, section_part = header.split(" | SECTION: ")

                all_chunks.append({
                    "text": chunk_text.strip(),
                    "source": filename.replace("_chunks.txt", ""),
                    "chunk_id": chunk_id,
                    "section": section_part.strip()
                })

    return all_chunks


def build_vector_db():
    print("Loading chunks...")
    chunks = load_chunks()
    print(f"Total chunks to embed: {len(chunks)}")

    print("Loading embedding model...")
    embedding_model = get_embedding_model()

    print("Connecting to ChromaDB...")
    client = chromadb.PersistentClient(path=DB_DIR)

    # Force a clean slate every time this runs
    try:
        client.delete_collection(name="research_papers")
        print("Deleted old collection.")
    except Exception:
        print("No existing collection to delete.")

    collection = client.get_or_create_collection(
        name="research_papers",
        metadata={"hnsw:space": "cosine"}
    )

    print("Embedding and storing chunks (this may take a few minutes)...")
    for i, chunk in enumerate(chunks):
        vector = embedding_model.embed_query(chunk["text"])
        collection.add(
            ids=[f"{chunk['source']}_{chunk['chunk_id']}"],
            embeddings=[vector],
            documents=[chunk["text"]],
            metadatas=[{"source": chunk["source"], "section": chunk["section"]}]
        )
        if (i + 1) % 20 == 0:
            print(f"  Stored {i + 1}/{len(chunks)} chunks")

    print(f"Done. Total chunks stored: {collection.count()}")

def delete_paper_from_db(source_name):
    client = chromadb.PersistentClient(path=DB_DIR)
    collection = client.get_or_create_collection(
        name="research_papers",
        metadata={"hnsw:space": "cosine"}
    )
    collection.delete(where={"source": source_name})


if __name__ == "__main__":
    build_vector_db()