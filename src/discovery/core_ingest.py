import os
import requests

from src.discovery.core_search import search_core
from src.ingestion.pipeline import process_single_pdf
from src.library.sessions import find_session_by_topic_name, create_session, add_paper_to_session
from src.discovery.dead_link_cache import is_known_dead, mark_dead

DOWNLOAD_DIR = "data/cache/core_downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def download_pdf(pdf_url, core_id):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    safe_name = str(core_id).replace("/", "_")
    save_path = os.path.join(DOWNLOAD_DIR, f"{safe_name}.pdf")

    response = requests.get(pdf_url, headers=headers, timeout=45)
    response.raise_for_status()

    with open(save_path, "wb") as f:
        f.write(response.content)

    return save_path


def fetch_and_ingest_topic_core(query, max_results=3, existing_paper_names=None, caption_images=False):
    """
    Searches CORE for a topic, downloads new open-access papers, ingests them,
    and links them all to a research session for this topic.
    """
    existing_paper_names = existing_paper_names or set()

    session_id = find_session_by_topic_name(query)
    if not session_id:
        session_id = create_session(query, source="core")

    results = search_core(query, max_results=max_results)
    ingested = []

    for paper in results:
        source_name = paper["title"][:80].replace("/", "_").replace(":", "").replace("\n", " ").strip()

        if source_name in existing_paper_names:
            ingested.append({"title": paper["title"], "status": "skipped (already in library)"})
            add_paper_to_session(session_id, source_name)
            continue

        if is_known_dead(paper["core_id"]):
            ingested.append({"title": paper["title"], "status": "skipped (known broken link)"})
            continue

        try:
            urls_to_try = [paper["pdf_url"]] + paper.get("fallback_urls", [])
            pdf_path = None
            last_error = None

            for url in urls_to_try:
                try:
                    pdf_path = download_pdf(url, paper["core_id"])
                    break
                except Exception as e:
                    last_error = e
                    continue

            if pdf_path is None:
                mark_dead(paper["core_id"])
                raise last_error

            chunk_count, section_count = process_single_pdf(
                pdf_path, source_name,
                caption_images=caption_images,
                origin="core",
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
    results, session_id = fetch_and_ingest_topic_core(
        "lithium-ion battery state of health estimation", max_results=2
    )
    for r in results:
        print(r)
    print(f"\nSession ID: {session_id}")