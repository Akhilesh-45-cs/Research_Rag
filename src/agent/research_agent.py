import json
from src.llm.groq_client import get_fast_llm, get_llm
from src.retrieval.retriever import retrieve
from src.discovery.arxiv_ingest import fetch_and_ingest_topic
from src.retrieval.retriever import get_all_paper_names

COVERAGE_PROMPT = """You are judging whether a set of retrieved research paper excerpts 
is sufficient to answer a question well.

Question: {question}

Retrieved excerpts:
{context}

Judge whether these excerpts contain enough relevant, substantive information to give 
a good answer. Weak, empty, or purely bibliographic/citation-list context means 
NOT sufficient.

Respond with ONLY valid JSON:
{{"sufficient": true/false, "reason": "one short sentence explaining why"}}
"""


def filter_out_references(chunks, metadatas):
    """Removes chunks tagged as 'references' - these are citation lists, 
    not real content, and shouldn't count toward coverage or context."""
    filtered_chunks = []
    filtered_metas = []
    for doc, meta in zip(chunks, metadatas):
        if meta.get("section", "").lower() != "references":
            filtered_chunks.append(doc)
            filtered_metas.append(meta)
    return filtered_chunks, filtered_metas


def assess_coverage(question, retrieved_chunks):
    """Uses a fast LLM call to judge if retrieved context is enough to answer well."""
    if not retrieved_chunks:
        return False, "No relevant content was found in the library."

    context_preview = "\n\n".join(retrieved_chunks[:5])[:2000]

    llm = get_fast_llm()
    prompt = COVERAGE_PROMPT.format(question=question, context=context_preview)
    response = llm.invoke(prompt)

    raw = response.content.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        parsed = json.loads(raw)
        return parsed.get("sufficient", True), parsed.get("reason", "")
    except json.JSONDecodeError:
        return True, "Could not parse coverage judgment, assuming sufficient."


def run_research_agent(question, existing_top_k=8, max_new_papers=2):
    """
    Autonomous loop:
    1. Retrieve from existing library, filtering out reference/citation chunks
    2. Judge if coverage is sufficient
    3. If not, autonomously fetch new papers on the topic and retry
    4. Return final chunks + metadatas + a log of what the agent did
    """
    log = []

    results = retrieve(question, top_k=existing_top_k)
    chunks = results["documents"][0]
    metadatas = results["metadatas"][0]
    chunks, metadatas = filter_out_references(chunks, metadatas)

    sufficient, reason = assess_coverage(question, chunks)
    log.append(f"Checked existing library: {'sufficient' if sufficient else 'insufficient'} ({reason})")

    if sufficient:
        return chunks, metadatas, log

    log.append(f"Searching arXiv for new papers on: '{question}'")
    existing_names = set(get_all_paper_names())

    fetch_results, session_id = fetch_and_ingest_topic(
        question,
        max_results=max_new_papers,
        existing_paper_names=existing_names,
        caption_images=False  # keep this fast since it's happening live in chat
    )

    added_count = sum(1 for r in fetch_results if r["status"] == "added")
    log.append(f"Fetched and added {added_count} new paper(s) to the library.")

    if added_count == 0:
        log.append("No new papers were added. Answering with what's currently available.")
        return chunks, metadatas, log

    results = retrieve(question, top_k=existing_top_k)
    chunks = results["documents"][0]
    metadatas = results["metadatas"][0]
    chunks, metadatas = filter_out_references(chunks, metadatas)

    # Verify the fetch actually helped, rather than assuming it did
    sufficient_after_fetch, reason_after_fetch = assess_coverage(question, chunks)
    if sufficient_after_fetch:
        log.append(f"Re-searched library after adding new papers: now sufficient.")
    else:
        log.append(f"Re-searched after fetching, but still insufficient ({reason_after_fetch}). The fetched paper(s) may not have been a strong match for this specific topic.")

    return chunks, metadatas, log


def ask_with_agent(question, chat_history=None):
    """
    Full agent-backed answer: runs the research loop, then generates a grounded 
    answer from whatever content the agent ended up with.
    """
    chunks, metadatas, log = run_research_agent(question)

    if not chunks:
        return "No relevant content could be found, even after searching for new papers.", [], log

    from src.prompts.prompt_templates import build_prompt
    context = "\n\n".join(chunks)
    prompt = build_prompt(context, question)

    llm = get_llm()
    response = llm.invoke(prompt)

    sources = sorted(set(m["source"] for m in metadatas))
    return response.content, sources, log


if __name__ == "__main__":
    question = "What approaches exist for EV battery thermal management using phase change materials?"
    answer, sources, log = ask_with_agent(question)

    print("=== Agent Log ===")
    for entry in log:
        print(f"- {entry}")

    print(f"\n=== Answer ===\n{answer}")
    print(f"\n=== Sources ===")
    for s in sources:
        print(f"- {s}")