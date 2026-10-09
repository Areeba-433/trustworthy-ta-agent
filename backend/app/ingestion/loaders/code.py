"""Track 4: source code (.cpp and friends) through tree-sitter. Owner: Fariha.

DAY-0 STUB: returns one fake block. The real loader never runs clean_text() on
code: indentation, blank lines and symbols are meaning.
"""

from __future__ import annotations

from pathlib import Path

from app.ingestion.contract import Location, ParsedDocument, ResourceMeta
from app.ingestion.loaders._stub import stub_document
from app.ingestion.registry import register


@register("code")
def load(path: Path, meta: ResourceMeta) -> ParsedDocument:
    return stub_document(path, meta, "code", kind="code", lang="code",
                         loc=Location(line_start=1, line_end=1), parser="tree-sitter")
