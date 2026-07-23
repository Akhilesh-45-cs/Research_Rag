from src.retrieval.retriever import retrieve
from src.llm.groq_client import get_llm
from src.prompts.prompt_templates import build_prompt


def ask_question(query, top_k=5):
    category = classify_query(query)

    if category == "greeting":
        return "Hi! Ask me anything about the research papers in your library.", []

    if category == "irrelevant":
        return "I can only answer questions related to the research papers you've provided.", []

    if is_comparison_query(query):
        return ask_comparison_question(query)

    # normal single-topic research question
    results = retrieve(query, top_k=top_k)
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    context = "\n\n".join(documents)
    prompt = build_prompt(context, query)
    llm = get_llm()
    response = llm.invoke(prompt)
    sources = sorted(set(m["source"] for m in metadatas))
    return response.content, sources

def is_comparison_query(query):
    keywords = ["compare", "best", "across papers", "which paper", "all papers", "each paper", "better"]
    return any(kw in query.lower() for kw in keywords)


def ask_comparison_question(query):
    from src.retrieval.retriever import get_chunks_by_section

    grouped = get_chunks_by_section("result")
    if not grouped:
        return "No results sections were found across the papers to compare.", []

    context_parts = []
    for source, chunks in grouped.items():
        combined = "\n".join(chunks[:2])  # limit to avoid overloading the prompt
        context_parts.append(f"Paper: {source}\nResults:\n{combined}")

    context = "\n\n---\n\n".join(context_parts)

    prompt = f"""You are comparing results across multiple research papers.
Based on the results sections below, answer the question. Reference specific papers by name.

{context}

Question: {query}

Answer:"""

    llm = get_llm()
    response = llm.invoke(prompt)

    return response.content, list(grouped.keys())


if __name__ == "__main__":
    print("Ask questions about your papers (type 'exit' to quit)\n")

    while True:
        query = input("Your question: ")
        if query.lower() == "exit":
            break

        ask_question(query)
        print("\n" + "=" * 50 + "\n")