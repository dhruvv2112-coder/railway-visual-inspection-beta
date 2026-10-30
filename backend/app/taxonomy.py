import json
from functools import lru_cache

from .config import settings


@lru_cache
def load() -> dict:
    with open(settings.taxonomy_path, encoding="utf-8") as f:
        data = json.load(f)
    data["by_id"] = {c["id"]: c for c in data["classes"]}
    return data


def get(class_id: str) -> dict | None:
    return load()["by_id"].get(class_id)
