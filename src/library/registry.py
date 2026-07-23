import json
import os
from datetime import datetime

REGISTRY_PATH = "data/library_registry.json"


def _load_registry():
    if not os.path.exists(REGISTRY_PATH):
        return {}
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_registry(data):
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def register_paper(source_name, origin, chunk_count, section_count):
    """origin: 'manual_upload' or 'arxiv'"""
    registry = _load_registry()
    registry[source_name] = {
        "added_at": datetime.now().isoformat(),
        "origin": origin,
        "chunk_count": chunk_count,
        "section_count": section_count
    }
    _save_registry(registry)


def get_all_papers_sorted():
    """Returns list of (source_name, info) sorted newest-first."""
    registry = _load_registry()
    items = list(registry.items())
    items.sort(key=lambda x: x[1]["added_at"], reverse=True)
    return items


def get_latest_n_papers(n=3):
    return [name for name, _ in get_all_papers_sorted()[:n]]


def remove_paper(source_name):
    registry = _load_registry()
    if source_name in registry:
        del registry[source_name]
        _save_registry(registry)