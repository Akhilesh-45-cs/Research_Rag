from src.retrieval.retriever import (
    retrieve,
    retrieve_from_paper,
    get_all_paper_names,
    get_chunks_by_section,
    resolve_paper_names,
)
from src.llm.groq_client import get_llm
from src.llm.router import route_query
from src.prompts.prompt_templates import build_prompt
from src.library.registry import get_latest_n_papers
from src.agent.research_agent import run_research_agent

def ask_comparison_question(query, target_papers=None):
    grouped = get_chunks_by_section("result", only_papers=target_papers)

    if target_papers:
        for paper in target_papers:
            if paper not in grouped or not grouped[paper]:
                fallback_results = retrieve_from_paper(
                    "results, performance metrics, accuracy, error values",
                    paper,
                    top_k=5
                )
                fallback_chunks = fallback_results["documents"][0]
                if fallback_chunks:
                    grouped[paper] = fallback_chunks

    if not grouped:
        return "No results sections were found for the relevant papers to compare.", []

    context_parts = []
    for source, chunks in grouped.items():
        combined = "\n".join(chunks[:2])
        context_parts.append(f"Paper: {source}\nResults:\n{combined}")
    context = "\n\n---\n\n".join(context_parts)

    prompt = f"""You are comparing results across research papers.
Based on the results sections below, answer the question. Reference specific papers by name.

{context}

Question: {query}

Answer:"""

    llm = get_llm()
    response = llm.invoke(prompt)
    return response.content, list(grouped.keys())


def ask_scoped_question(query, target_papers, top_k_per_paper=3):
    """Answers a question using only chunks from the given list of papers."""
    all_chunks = []
    for paper in target_papers:
        results = retrieve_from_paper(query, paper, top_k=top_k_per_paper)
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            all_chunks.append((doc, meta["source"]))

    if not all_chunks:
        return "No relevant content was found in those papers.", []

    context = "\n\n".join(f"[{source}]\n{doc}" for doc, source in all_chunks)
    prompt = build_prompt(context, query)

    llm = get_llm()
    response = llm.invoke(prompt)

    sources = sorted(set(source for _, source in all_chunks))
    return response.content, sources


def ask_question(query, chat_history, top_k=5):
    """
    Core answer-routing logic. chat_history is a list of {"role": ..., "content": ...} dicts.
    Returns (answer_text, sources_list, route_label).
    """
    paper_names = get_all_paper_names()
    route_info = route_query(query, chat_history, paper_names)

    category = route_info.get("category", "general")
    raw_target_papers = route_info.get("target_papers") or []
    target_papers = resolve_paper_names(raw_target_papers, paper_names)
    standalone_question = route_info.get("standalone_question", query)

    if category == "greeting":
        return "Hi! Ask me anything about the research papers in your library.", [], "greeting"

    if category == "irrelevant":
        return "I can only answer questions related to the research papers you've provided.", [], "irrelevant"

    if category == "recent_papers":
        count = route_info.get("recent_count", 3) or 3
        recent = get_latest_n_papers(n=count)
        if not recent:
            return "No papers have been added yet (or they were added before paper tracking was enabled).", [], "recent_papers"

        listing_only_phrases = ["what are", "which are", "list", "show me", "what papers"]
        content_phrases = ["result", "model", "method", "accuracy", "used", "compare", "how"]

        is_pure_listing = any(p in query.lower() for p in listing_only_phrases) and not any(
            p in query.lower() for p in content_phrases
        )

        if is_pure_listing:
            listing = "\n".join(f"- {name}" for name in recent)
            return f"The latest {count} papers added are:\n\n{listing}", recent, f"recent {count} papers (direct listing)"

        answer, sources = ask_scoped_question(standalone_question, recent)
        return answer, sources, f"recent {count} papers: {recent}"

    if category == "comparison":
        answer, sources = ask_comparison_question(standalone_question, target_papers or None)
        label = f"comparison: {target_papers}" if target_papers else "comparison: all papers"
        return answer, sources, label

    if category == "library_meta":
        if not paper_names:
            return "No papers are currently in your library.", [], "library_meta"
        listing = "\n".join(f"- {name}" for name in paper_names)
        return f"Here are the papers currently in your library:\n\n{listing}", [], "library_meta"

    if category == "single_paper" and target_papers:
        matched_paper = target_papers[0]
        results = retrieve_from_paper(standalone_question, matched_paper, top_k=8)
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        route = f"filtered to paper: {matched_paper}"

    else:
        # "general" category - use the research agent, which checks coverage and
        # autonomously fetches new papers from arXiv if the existing library is thin
        chunks, metadatas_list, agent_log = run_research_agent(standalone_question)
        documents = chunks
        metadatas = metadatas_list
        route = f"agent: {' | '.join(agent_log)}"

    context = "\n\n".join(documents)
    prompt = build_prompt(context, standalone_question)

    llm = get_llm()
    response = llm.invoke(prompt)

    sources = sorted(set(m["source"] for m in metadatas))
    return response.content, sources, route