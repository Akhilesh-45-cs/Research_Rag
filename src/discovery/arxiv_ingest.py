import os
import requests

from src.discovery.arxiv_search import search_arxiv
from src.ingestion.pipeline import process_single_pdf
from src.library.sessions import find_session_by_topic_name, create_session, add_paper_to_session

DOWNLOAD_DIR = "data/cache/arxiv_downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def download_pdf(pdf_url, arxiv_id):
    """Downloads a PDF from arXiv and saves it locally. Returns the local file path."""
    safe_name = arxiv_id.replace("/", "_").replace(".", "_")
    save_path = os.path.join(DOWNLOAD_DIR, f"{safe_name}.pdf")

    response = requests.get(pdf_url, timeout=30)
    response.raise_for_status()

    with open(save_path, "wb") as f:
        f.write(response.content)

    return save_path


def fetch_and_ingest_topic(query, max_results=3, existing_paper_names=None, caption_images=False):
    """
    Searches arXiv for a topic, downloads new papers, ingests them, and links them
    all to a research session for this topic (reusing an existing session if one
    already exists for this exact topic name).
    caption_images defaults False here since agent/topic-fetch happens live in chat -
    keep it fast. Pass True for a deliberate, user-initiated topic search where 
    waiting a bit longer for figure captions is acceptable.
    """
    existing_paper_names = existing_paper_names or set()

    session_id = find_session_by_topic_name(query)
    if not session_id:
        session_id = create_session(query, source="arxiv")

    results = search_arxiv(query, max_results=max_results)
    ingested = []

    for paper in results:
        source_name = paper["title"][:80].replace("/", "_").replace(":", "").strip()

        if source_name in existing_paper_names:
            ingested.append({"title": paper["title"], "status": "skipped (already in library)"})
            add_paper_to_session(session_id, source_name)
            continue

        try:
            pdf_path = download_pdf(paper["pdf_url"], paper["arxiv_id"])
            chunk_count, section_count = process_single_pdf(
                pdf_path, source_name,
                caption_images=caption_images,
                origin="arxiv",
                session_id=session_id
            )
            ingested.append({
                "title": paper["title"],
                "status": "added",
                "chunks": chunk_count,
                "sections": section_count
            })
        except Exception as e:
            ingested.append({"title": paper["title"], "status": f"failed: {str(e)}"})

    return ingested, session_id


if __name__ == "__main__":
    results, session_id = fetch_and_ingest_topic(
        "lithium-ion battery state of health estimation", max_results=2
    )
    for r in results:
        print(r)
    print(f"\nSession ID: {session_id}")