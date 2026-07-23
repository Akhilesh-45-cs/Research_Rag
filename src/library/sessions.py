import json
import os
import uuid
from datetime import datetime

SESSIONS_PATH = "data/sessions.json"


def _load_sessions():
    if not os.path.exists(SESSIONS_PATH):
        return {}
    with open(SESSIONS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_sessions(data):
    os.makedirs(os.path.dirname(SESSIONS_PATH), exist_ok=True)
    with open(SESSIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def create_session(topic_name, source="manual"):
    """Creates a new research session (topic). source: 'manual', 'arxiv', 'core', 'mixed'."""
    sessions = _load_sessions()
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "session_id": session_id,
        "topic_name": topic_name,
        "created_at": datetime.now().isoformat(),
        "source": source,
        "papers": [],       # list of source_name strings
        "reports": [],      # list of {report_id, title, created_at, filepath}
        "starred": False
    }
    _save_sessions(sessions)
    return session_id


def get_all_sessions_sorted():
    sessions = _load_sessions()
    items = list(sessions.values())
    items.sort(key=lambda s: s["created_at"], reverse=True)
    return items


def get_session(session_id):
    sessions = _load_sessions()
    return sessions.get(session_id)


def find_session_by_topic_name(topic_name):
    """Finds an existing session with this exact topic name (case-insensitive), if any."""
    sessions = _load_sessions()
    for s in sessions.values():
        if s["topic_name"].strip().lower() == topic_name.strip().lower():
            return s["session_id"]
    return None


def add_paper_to_session(session_id, source_name):
    sessions = _load_sessions()
    if session_id in sessions:
        if source_name not in sessions[session_id]["papers"]:
            sessions[session_id]["papers"].append(source_name)
        _save_sessions(sessions)


def remove_paper_from_session(session_id, source_name):
    sessions = _load_sessions()
    if session_id in sessions and source_name in sessions[session_id]["papers"]:
        sessions[session_id]["papers"].remove(source_name)
        _save_sessions(sessions)


def add_report_to_session(session_id, report_title, filepath):
    sessions = _load_sessions()
    if session_id in sessions:
        report_id = str(uuid.uuid4())
        sessions[session_id]["reports"].append({
            "report_id": report_id,
            "title": report_title,
            "created_at": datetime.now().isoformat(),
            "filepath": filepath
        })
        _save_sessions(sessions)
        return report_id
    return None


def toggle_star(session_id):
    sessions = _load_sessions()
    if session_id in sessions:
        sessions[session_id]["starred"] = not sessions[session_id]["starred"]
        _save_sessions(sessions)
        return sessions[session_id]["starred"]
    return None


def delete_session(session_id, delete_papers_too=False):
    """Deletes a session. If delete_papers_too, also removes its papers from 
    the vector DB and registry (caller must handle that separately for now)."""
    sessions = _load_sessions()
    papers = sessions.get(session_id, {}).get("papers", [])
    if session_id in sessions:
        del sessions[session_id]
        _save_sessions(sessions)
    return papers  # return paper list so caller can decide whether to delete them too

def remove_paper_from_all_sessions(source_name):
    """Removes a paper from every session that references it (used when a paper is deleted)."""
    sessions = _load_sessions()
    changed = False
    for session in sessions.values():
        if source_name in session["papers"]:
            session["papers"].remove(source_name)
            changed = True
    if changed:
        _save_sessions(sessions)
def remove_report_from_session(session_id, report_id):
    sessions = _load_sessions()
    if session_id in sessions:
        sessions[session_id]["reports"] = [
            r for r in sessions[session_id]["reports"] if r["report_id"] != report_id
        ]
        _save_sessions(sessions)


if __name__ == "__main__":
    sid = create_session("EV Battery Thermal Management", source="arxiv")
    add_paper_to_session(sid, "Some Test Paper Title")
    print(get_session(sid))
    print("\nAll sessions:")
    for s in get_all_sessions_sorted():
        print(f"- {s['topic_name']} ({len(s['papers'])} papers, {len(s['reports'])} reports, starred={s['starred']})")