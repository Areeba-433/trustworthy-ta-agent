"""Track 4: plain text and Markdown. Owner: Fariha.

DAY-0 STUB: returns one fake block. The real loader turns Markdown headings
into the heading path and splits plain text on blank lines.
"""

from __future__ import annotations

from pathlib import Path

from app.ingestion.contract import Location, ParsedDocument, ResourceMeta
from app.ingestion.loaders._stub import stub_document
from app.ingestion.registry import register


@register("text")
def load(path: Path, meta: ResourceMeta) -> ParsedDocument:
    return stub_document(path, meta, "text", kind="paragraph",
                         loc=Location(line_start=1, line_end=1), parser="text")
