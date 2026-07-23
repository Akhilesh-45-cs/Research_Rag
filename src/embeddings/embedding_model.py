from langchain_huggingface import HuggingFaceEmbeddings

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def get_embedding_model():
    embeddings = HuggingFaceEmbeddings(model_name=MODEL_NAME)
    return embeddings


if __name__ == "__main__":
    model = get_embedding_model()

    sample_text = "EV battery health monitoring using machine learning."
    vector = model.embed_query(sample_text)

    print(f"Model: {MODEL_NAME}")
    print(f"Vector length: {len(vector)}")
    print(f"First 5 values: {vector[:5]}")