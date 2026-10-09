"""Track 1: digital PDF, DOCX, PPTX through Docling. Owner: Areeba.

DAY-0 STUB: returns one fake block so the dispatcher and contract test work end
to end. Replace the body with the real loader from the Track 1 build guide;
keep the function name `load` and the @register line.
"""

from __future__ import annotations

from pathlib import Path

from app.ingestion.contract import Location, ParsedDocument, ResourceMeta
from app.ingestion.loaders._stub import stub_document
from app.ingestion.registry import register


@register("pdf", "docx", "pptx")
def load(path: Path, meta: ResourceMeta) -> ParsedDocument:
    source_type = Path(path).suffix.lower().lstrip(".")
    loc = {"pdf": Location(page=1), "pptx": Location(slide=1), "docx": Location()}[source_type]
    return stub_document(path, meta, source_type, kind="paragraph", loc=loc, parser="docling")
