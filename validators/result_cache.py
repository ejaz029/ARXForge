"""In-memory deterministic result cache for validator outputs."""

from __future__ import annotations

import copy
import hashlib
import os
from typing import Any

_CACHE: dict[str, Any] = {}


def file_sha256(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def cache_key(parts: list[str]) -> str:
    normalized = "|".join(parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_cached(key: str):
    value = _CACHE.get(key)
    if value is None:
        return None
    return copy.deepcopy(value)


def set_cached(key: str, value: Any):
    _CACHE[key] = copy.deepcopy(value)


def clear_cache():
    _CACHE.clear()


def xsd_fingerprint(xsd_path: str | None) -> str:
    if not xsd_path:
        return "none"
    if not os.path.exists(xsd_path):
        return f"missing:{xsd_path}"
    st = os.stat(xsd_path)
    return f"{os.path.abspath(xsd_path)}:{st.st_mtime_ns}:{st.st_size}"

