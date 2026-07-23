import json
import os
import uuid
from datetime import datetime

CHATS_DIR = "data/chats"
os.makedirs(CHATS_DIR, exist_ok=True)


def _chat_path(chat_id):
    return os.path.join(CHATS_DIR, f"{chat_id}.json")


def create_new_chat():
    chat_id = str(uuid.uuid4())
    chat_data = {
        "chat_id": chat_id,
        "title": "New Chat",
        "created_at": datetime.now().isoformat(),
        "messages": []
    }
    _save_chat(chat_data)
    return chat_id


def _save_chat(chat_data):
    with open(_chat_path(chat_data["chat_id"]), "w", encoding="utf-8") as f:
        json.dump(chat_data, f, indent=2)


def load_chat(chat_id):
    path = _chat_path(chat_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_messages(chat_id, messages):
    chat_data = load_chat(chat_id)
    if chat_data is None:
        return
    chat_data["messages"] = messages

    # auto-title the chat using the first user message, once available
    if chat_data["title"] == "New Chat" and messages:
        first_user_msg = next((m["content"] for m in messages if m["role"] == "user"), None)
        if first_user_msg:
            chat_data["title"] = first_user_msg[:50]

    _save_chat(chat_data)


def get_all_chats_sorted():
    """Returns list of chat_data dicts, newest first."""
    chats = []
    for filename in os.listdir(CHATS_DIR):
        if filename.endswith(".json"):
            with open(os.path.join(CHATS_DIR, filename), "r", encoding="utf-8") as f:
                chats.append(json.load(f))
    chats.sort(key=lambda c: c["created_at"], reverse=True)
    return chats


def delete_chat(chat_id):
    path = _chat_path(chat_id)
    if os.path.exists(path):
        os.remove(path)