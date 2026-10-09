"""Track 3: lecture recordings through Whisper (Groq). Owner: Zuha.

DAY-0 STUB: returns one fake block. The real loader transcribes each recording
exactly once and keeps the raw Whisper JSON under storage.raw_dir().
"""

from __future__ import annotations

from pathlib import Path

from app.ingestion.contract import Location, ParsedDocument, ResourceMeta
from app.ingestion.loaders._stub import stub_document
from app.ingestion.registry import register


@register("audio")
def load(path: Path, meta: ResourceMeta) -> ParsedDocument:
    return stub_document(path, meta, "audio", kind="transcript",
                         loc=Location(t_start=0.0, t_end=1.0), parser="whisper", confidence=0.9)
