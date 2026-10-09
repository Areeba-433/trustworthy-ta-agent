"""Where ingestion output lives on disk. Owner: Minahil.

    parsed/<resource_id>/parsed.json   the ParsedDocument (saved by the dispatcher)
    parsed/<resource_id>/raw/          each loader's raw extraction (Docling JSON, OCR, Whisper JSON)
    parsed/_cache/                     parse results keyed by file hash + parser version

Set INGEST_PARSED_DIR to move the root. Loaders use raw_dir() and cache_dir()
instead of building paths themselves, so tests can redirect everything at once.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from app.ingestion.contract import ParsedDocument

PARSED_ROOT = Path(os.environ.get("INGEST_PARSED_DIR", "parsed"))

_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")


def resource_dir(resource_id: str) -> Path:
    if not _SAFE_ID.fullmatch(resource_id) or ".." in resource_id:
        raise ValueError(f"unsafe resource_id: {resource_id!r}")
    return PARSED_ROOT / resource_id


def raw_dir(resource_id: str) -> Path:
    path = resource_dir(resource_id) / "raw"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    path = PARSED_ROOT / "_cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_parsed(doc: ParsedDocument) -> Path:
    folder = resource_dir(doc.resource_id)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "parsed.json"
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
    tmp.replace(target)  # atomic: a reader never sees half a file
    return target


def load_parsed(resource_id: str) -> ParsedDocument:
    path = resource_dir(resource_id) / "parsed.json"
    return ParsedDocument.model_validate_json(path.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):  # 1 MB at a time
            digest.update(chunk)
    return digest.hexdigest()
