import os
import chromadb
from langchain_text_splitter import RecursiveCharacterTextSplitter
from src.extraction.extractor import extract_text_from_pdf, extract_tables_from_pdf
from src.chunking.chunker import split_into_sections
from src.embeddings.embedding_model import get_embedding_model
from src.library.registry import register_paper
from src.extraction.image_captioner import extract_and_caption_images
from src.library.sessions import add_paper_to_session

DB_DIR = "data/vector_db"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def process_single_pdf(pdf_path, source_name, caption_images=True, session_id=None, origin="manual_upload"):
    """
    Runs the full pipeline (extract -> chunk -> embed -> store) on ONE pdf.
    source_name = the name used to identify this paper (usually filename without extension)
    caption_images = whether to run the vision model on embedded figures (slower, skip for fast agent fetches)
    session_id = if provided, links this paper to a research session/topic
    origin = 'manual_upload', 'arxiv', or 'core' - tracked in the registry
    """

    # Step 1: Extract text and tables together
    text = extract_text_from_pdf(pdf_path)
    table_text = extract_tables_from_pdf(pdf_path)
    text = text + "\n\n" + table_text

    # Step 2: Split into sections, then chunk within each section
    sections = split_into_sections(text)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    chunk_records = []
    chunk_count = 0
    for section_name, section_text in sections:
        if not section_text.strip():
            continue
        chunks = splitter.split_text(section_text)
        for chunk in chunks:
            chunk_records.append({
                "text": chunk,
                "chunk_id": str(chunk_count),
                "section": section_name
            })
            chunk_count += 1

    # Step 3: Caption images and add them as their own searchable chunks (optional)
    if caption_images:
        image_captions = extract_and_caption_images(pdf_path, max_images=15)
        for img in image_captions:
            chunk_records.append({
                "text": f"[Figure on page {img['page_num']}]: {img['caption']}",
                "chunk_id": str(chunk_count),
                "section": "figure"
            })
            chunk_count += 1

    # Step 4: Embed and store each chunk
    embedding_model = get_embedding_model()
    client = chromadb.PersistentClient(path=DB_DIR)
    collection = client.get_or_create_collection(
        name="research_papers",
        metadata={"hnsw:space": "cosine"}
    )

    for record in chunk_records:
        vector = embedding_model.embed_query(record["text"])
        collection.add(
            ids=[f"{source_name}_{record['chunk_id']}"],
            embeddings=[vector],
            documents=[record["text"]],
            metadatas=[{"source": source_name, "section": record["section"]}]
        )

    # Step 5: Register the paper and link it to a session/topic if provided
    register_paper(source_name, origin=origin, chunk_count=chunk_count, section_count=len(sections))

    if session_id:
        add_paper_to_session(session_id, source_name)

    return chunk_count, len(sections)
