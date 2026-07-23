import json
import os

CACHE_PATH = "data/cache/dead_core_links.json"


def _load():
    if not os.path.exists(CACHE_PATH):
        return set()
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        return set(json.load(f))


def _save(dead_ids):
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(list(dead_ids), f)


def is_known_dead(core_id):
    return str(core_id) in _load()


def mark_dead(core_id):
    dead_ids = _load()
    dead_ids.add(str(core_id))
    _save(dead_ids)