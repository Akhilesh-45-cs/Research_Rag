import os
import streamlit as st

from src.retrieval.retriever import (
    retrieve,
    retrieve_from_paper,
    get_all_paper_names,
    get_chunks_by_section,
)
from src.chat.chat_manager import (
    create_new_chat, load_chat, save_messages, get_all_chats_sorted, delete_chat
)
from src.discovery.core_ingest import fetch_and_ingest_topic_core
from src.llm.groq_client import get_llm
from src.llm.router import route_query
from src.prompts.prompt_templates import build_prompt
from src.ingestion.pipeline import process_single_pdf
from src.discovery.arxiv_ingest import fetch_and_ingest_topic
from src.library.registry import get_latest_n_papers, get_all_papers_sorted, remove_paper
from src.vectordb.chroma_manager import delete_paper_from_db

st.set_page_config(page_title="Research Assistant", layout="wide")
st.title("AI Research Assistant")
st.caption("Ask questions about your uploaded papers")

# ---------- Upload sidebar ----------
UPLOAD_DIR = "data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

if "processed_files" not in st.session_state:
    st.session_state.processed_files = set()

with st.sidebar:
    st.header("Upload New Papers")
    uploaded_files = st.file_uploader(
        "Choose PDF(s)",
        type="pdf",
        accept_multiple_files=True
    )

    if uploaded_files:
        new_files = [f for f in uploaded_files if f.name not in st.session_state.processed_files]

        if new_files:
            progress_bar = st.progress(0, text="Starting...")

            for i, uploaded_file in enumerate(new_files):
                save_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
                with open(save_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                source_name = uploaded_file.name.replace(".pdf", "")

                progress_bar.progress(
                    i / len(new_files),
                    text=f"Processing '{uploaded_file.name}' ({i+1}/{len(new_files)})..."
                )

                chunk_count, section_count = process_single_pdf(save_path, source_name)
                st.session_state.processed_files.add(uploaded_file.name)
                st.success(f"'{uploaded_file.name}': {chunk_count} chunks, {section_count} sections")

            progress_bar.progress(1.0, text="All done!")
        else:
            st.info("All selected files already processed in this session.")

    st.divider()
    st.header("Fetch Papers by Topic")
    topic_query = st.text_input("Search topic (e.g. 'EV battery thermal management')")
    source_choice = st.radio("Source", ["arXiv", "CORE", "Both"], horizontal=True)
    num_papers = st.slider("Number of papers to fetch (per source)", 1, 5, 3)

    if st.button("Search & Add Papers"):
        if topic_query.strip():
            existing_names = set(get_all_paper_names())
            all_results = []

            if source_choice in ("arXiv", "Both"):
                with st.spinner(f"Searching arXiv for '{topic_query}'..."):
                    arxiv_results = fetch_and_ingest_topic(
                        topic_query, max_results=num_papers, existing_paper_names=existing_names
                    )
                    all_results.extend(arxiv_results)
                    existing_names.update(r["title"][:80] for r in arxiv_results if r["status"] == "added")

            if source_choice in ("CORE", "Both"):
                with st.spinner(f"Searching CORE for '{topic_query}'..."):
                    core_results = fetch_and_ingest_topic_core(
                        topic_query, max_results=num_papers, existing_paper_names=existing_names
                    )
                    all_results.extend(core_results)

            st.session_state.last_fetch_results = all_results  # persist across reruns
        else:
            st.warning("Enter a topic to search first.")

    # Always render the last fetch results, even after unrelated reruns
    if "last_fetch_results" in st.session_state:
        for r in st.session_state.last_fetch_results:
            if r["status"] == "added":
                st.success(f"Added: {r['title'][:60]}... ({r['chunks']} chunks)")
            elif "skipped" in r["status"]:
                st.info(f"Skipped (already have it): {r['title'][:60]}...")
            else:
                st.error(f"Failed: {r['title'][:60]}... - {r['status']}")

    st.divider()
    st.header("Your Papers")
    papers_list = get_all_papers_sorted()

    if not papers_list:
        st.caption("No papers registered yet. (Papers added before this feature won't appear here — see backfill note.)")
    else:
        st.caption(f"{len(papers_list)} paper(s) in library")
        for source_name, info in papers_list:
            with st.expander(f"{source_name[:45]}"):
                st.caption(f"Added: {info['added_at'][:16].replace('T', ' ')}")
                st.caption(f"Source: {info['origin']}")
                st.caption(f"Chunks: {info['chunk_count']} | Sections: {info['section_count']}")
                if st.button("Delete", key=f"delete_{source_name}"):
                    delete_paper_from_db(source_name)
                    remove_paper(source_name)
                    st.session_state.processed_files.discard(source_name)
                    st.rerun()

# ---------- Chat history ----------
# ---------- Chat session management ----------
if "current_chat_id" not in st.session_state:
    existing_chats = get_all_chats_sorted()
    if existing_chats:
        st.session_state.current_chat_id = existing_chats[0]["chat_id"]
    else:
        st.session_state.current_chat_id = create_new_chat()

current_chat = load_chat(st.session_state.current_chat_id)
if current_chat is None:
    st.session_state.current_chat_id = create_new_chat()
    current_chat = load_chat(st.session_state.current_chat_id)

st.session_state.messages = current_chat["messages"]

with st.sidebar:
    st.divider()
    st.header("Chats")

    if st.button("+ New Chat", use_container_width=True):
        new_id = create_new_chat()
        st.session_state.current_chat_id = new_id
        st.rerun()

    all_chats = get_all_chats_sorted()
    for chat in all_chats:
        col1, col2 = st.columns([4, 1])
        with col1:
            label = chat["title"] if chat["title"] != "New Chat" else "New Chat (empty)"
            is_current = chat["chat_id"] == st.session_state.current_chat_id
            if st.button(
                label[:35],
                key=f"chat_{chat['chat_id']}",
                use_container_width=True,
                type="primary" if is_current else "secondary"
            ):
                st.session_state.current_chat_id = chat["chat_id"]
                st.rerun()
        with col2:
            if st.button("🗑", key=f"del_{chat['chat_id']}"):
                delete_chat(chat["chat_id"])
                if chat["chat_id"] == st.session_state.current_chat_id:
                    remaining = get_all_chats_sorted()
                    if remaining:
                        st.session_state.current_chat_id = remaining[0]["chat_id"]
                    else:
                        st.session_state.current_chat_id = create_new_chat()
                st.rerun()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])


# ---------- Core logic ----------
def ask_comparison_question(query, target_papers=None):
    grouped = get_chunks_by_section("result", only_papers=target_papers)

    # Fallback: for any explicitly-named target paper with no section-tagged results,
    # semantically search within that paper for results-related content instead
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
    paper_names = get_all_paper_names()
    route_info = route_query(query, chat_history, paper_names)

    category = route_info.get("category", "general")
    from src.retrieval.retriever import resolve_paper_names
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

        # If the question is JUST asking which papers are recent, answer directly (no LLM needed)
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
        route = f"filtered to paper: {matched_paper}"
    else:
        results = retrieve(standalone_question, top_k=top_k)
        route = "general search"

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    context = "\n\n".join(documents)
    prompt = build_prompt(context, standalone_question)

    llm = get_llm()
    response = llm.invoke(prompt)

    sources = sorted(set(m["source"] for m in metadatas))
    return response.content, sources, route


# ---------- Chat input ----------
user_query = st.chat_input("Ask a question about your papers...")

if user_query:
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.write(user_query)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            answer, sources, route = ask_question(user_query, st.session_state.messages[:-1])
            st.caption(f"Route: {route}")
            st.write(answer)
            if sources:
                st.markdown("**Sources:**")
                for s in sources:
                    st.markdown(f"- {s}")

    full_response = answer
    if sources:
        full_response += "\n\n**Sources:**\n" + "\n".join(f"- {s}" for s in sources)
    st.session_state.messages.append({"role": "assistant", "content": full_response})

    # Persist this conversation to disk
    save_messages(st.session_state.current_chat_id, st.session_state.messages)