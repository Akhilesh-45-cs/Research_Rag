import chromadb
from collections import Counter

DB_DIR = "data/vector_db"

client = chromadb.PersistentClient(path=DB_DIR)
collection = client.get_or_create_collection(
    name="research_papers",
    metadata={"hnsw:space": "cosine"}
)

all_data = collection.get(include=["metadatas"])
sections = [m.get("section", "MISSING") for m in all_data["metadatas"]]

print(f"Total chunks: {len(sections)}\n")
print("Section value counts:")
for section, count in Counter(sections).most_common(30):
    print(f"  {count:4d}  |  {section}")