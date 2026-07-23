import os
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from src.library.sessions import remove_paper_from_all_sessions
from src.reports.report_generator import generate_report
from fastapi.responses import FileResponse
from src.library.sessions import remove_report_from_session

from src.core.chat_engine import ask_question
from src.chat.chat_manager import (
    create_new_chat, load_chat, save_messages, get_all_chats_sorted, delete_chat
)
from src.library.registry import get_all_papers_sorted, remove_paper
from src.library.sessions import (
    get_all_sessions_sorted, get_session, toggle_star, delete_session,
    create_session, find_session_by_topic_name
)
from src.vectordb.chroma_manager import delete_paper_from_db
from src.ingestion.pipeline import process_single_pdf
from src.discovery.arxiv_ingest import fetch_and_ingest_topic
from src.discovery.core_ingest import fetch_and_ingest_topic_core
from src.retrieval.retriever import get_all_paper_names

app = FastAPI(title="AI Research Assistant")
app.mount("/static", StaticFiles(directory="static"), name="static")
UPLOAD_DIR = "data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ---------- Request body models ----------

class MessageRequest(BaseModel):
    message: str


class FetchTopicRequest(BaseModel):
    topic: str
    source: str = "arxiv"  # 'arxiv', 'core', or 'both'
    num_papers: int = 3


# ---------- Frontend ----------

@app.get("/", response_class=HTMLResponse)
def index():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return f.read()


# ---------- Chat endpoints ----------

@app.get("/api/chats")
def list_chats():
    return get_all_chats_sorted()


@app.post("/api/chats")
def new_chat():
    chat_id = create_new_chat()
    return {"chat_id": chat_id}


@app.get("/api/chats/{chat_id}")
def get_chat(chat_id: str):
    chat = load_chat(chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


@app.delete("/api/chats/{chat_id}")
def remove_chat(chat_id: str):
    delete_chat(chat_id)
    return {"status": "deleted"}


@app.post("/api/chats/{chat_id}/message")
def send_message(chat_id: str, body: MessageRequest):
    user_query = body.message.strip()
    if not user_query:
        raise HTTPException(status_code=400, detail="Empty message")

    chat = load_chat(chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")

    chat_history = chat["messages"]
    answer, sources, route = ask_question(user_query, chat_history)

    chat_history.append({"role": "user", "content": user_query})
    chat_history.append({"role": "assistant", "content": answer, "sources": sources, "route": route})
    save_messages(chat_id, chat_history)

    return {"answer": answer, "sources": sources, "route": route}


# ---------- Paper library endpoints ----------

@app.get("/api/papers")
def list_papers():
    papers = get_all_papers_sorted()
    return [{"source_name": name, **info} for name, info in papers]


@app.delete("/api/papers")
def remove_paper_route(source_name: str):
    delete_paper_from_db(source_name)
    remove_paper(source_name)
    remove_paper_from_all_sessions(source_name)
    return {"status": "deleted", "source_name": source_name}


# ---------- Research session endpoints ----------

@app.get("/api/sessions")
def list_sessions():
    return get_all_sessions_sorted()


@app.get("/api/sessions/{session_id}")
def get_session_route(session_id: str):
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.post("/api/sessions/{session_id}/star")
def star_session(session_id: str):
    starred = toggle_star(session_id)
    if starred is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"starred": starred}


@app.delete("/api/sessions/{session_id}")
def remove_session(session_id: str):
    papers = delete_session(session_id)
    return {"status": "deleted", "papers_in_session": papers}

@app.post("/api/sessions/{session_id}/generate_report")
def generate_report_route(session_id: str):
    report_id, result = generate_report(session_id)
    if report_id is None:
        raise HTTPException(status_code=400, detail=result)
    return {"report_id": report_id, "filepath": result}

@app.delete("/api/sessions/{session_id}/reports/{report_id}")
def delete_report_route(session_id: str, report_id: str):
    session = get_session(session_id)
    if session:
        report = next((r for r in session["reports"] if r["report_id"] == report_id), None)
        if report and os.path.exists(report["filepath"]):
            os.remove(report["filepath"])
    remove_report_from_session(session_id, report_id)
    return {"status": "deleted"}
# ---------- Upload endpoint ----------

@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...), topic: str = Form(...)):
    topic_name = topic.strip()
    if not topic_name:
        raise HTTPException(status_code=400, detail="A topic/session name is required")

    save_path = os.path.join(UPLOAD_DIR, file.filename)
    contents = await file.read()
    with open(save_path, "wb") as f:
        f.write(contents)

    source_name = file.filename.replace(".pdf", "")

    session_id = find_session_by_topic_name(topic_name)
    if not session_id:
        session_id = create_session(topic_name, source="manual")

    chunk_count, section_count = process_single_pdf(
        save_path, source_name, origin="manual_upload", session_id=session_id
    )

    return {
        "status": "added",
        "chunks": chunk_count,
        "sections": section_count,
        "session_id": session_id
    }

@app.get("/api/reports/download")
def download_report(path: str):
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Report file not found")
    filename = os.path.basename(path)
    media_type = "application/pdf" if path.endswith(".pdf") else "text/markdown"
    return FileResponse(path, filename=filename, media_type=media_type)


# ---------- Topic fetch endpoint ----------

@app.post("/api/fetch_topic")
def fetch_topic(body: FetchTopicRequest):
    topic_query = body.topic.strip()
    if not topic_query:
        raise HTTPException(status_code=400, detail="Topic is required")

    existing_names = set(get_all_paper_names())
    all_results = []
    session_id = None

    if body.source in ("arxiv", "both"):
        arxiv_results, session_id = fetch_and_ingest_topic(
            topic_query, max_results=body.num_papers, existing_paper_names=existing_names, caption_images=True
        )
        all_results.extend(arxiv_results)
        existing_names.update(r["title"][:80] for r in arxiv_results if r["status"] == "added")

    if body.source in ("core", "both"):
        core_results, session_id = fetch_and_ingest_topic_core(
            topic_query, max_results=body.num_papers, existing_paper_names=existing_names, caption_images=True
        )
        all_results.extend(core_results)

    return {"results": all_results, "session_id": session_id}