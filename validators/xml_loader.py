"""Shared ARXML parsing helpers with optional streaming path."""

from __future__ import annotations

import copy
import os
import xml.etree.ElementTree as ET
from functools import lru_cache


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def parse_arxml_root(file_path: str, prefer_streaming: bool | None = None):
    """
    Parse ARXML file and return root element.

    Streaming path is enabled when:
    - prefer_streaming is True, or
    - ARXFORGE_USE_STREAMING_PARSE=true and file size >= ARXFORGE_STREAMING_PARSE_MIN_BYTES
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(file_path)

    use_streaming = False
    if prefer_streaming is True:
        use_streaming = True
    elif prefer_streaming is False:
        use_streaming = False
    else:
        streaming_enabled = _env_bool("ARXFORGE_USE_STREAMING_PARSE", default=False)
        min_bytes = int(os.getenv("ARXFORGE_STREAMING_PARSE_MIN_BYTES", str(5 * 1024 * 1024)))
        file_size = os.path.getsize(file_path)
        use_streaming = streaming_enabled and file_size >= min_bytes

    stat = os.stat(file_path)
    root = _parse_with_cache(
        os.path.abspath(file_path),
        stat.st_mtime_ns,
        stat.st_size,
        use_streaming,
    )
    # Return a safe copy so callers can traverse/modify without mutating cache.
    return copy.deepcopy(root)


@lru_cache(maxsize=32)
def _parse_with_cache(abs_path: str, mtime_ns: int, size: int, use_streaming: bool):
    if use_streaming:
        try:
            from lxml import etree as LET

            parser = LET.iterparse(
                abs_path,
                events=("end",),
                recover=False,
                huge_tree=False,
                resolve_entities=False,
                no_network=True,
            )
            for _event, _elem in parser:
                pass
            return parser.root
        except Exception:
            # Fall back to stdlib parser if iterparse fails for any reason.
            pass

    tree = ET.parse(abs_path)
    return tree.getroot()

