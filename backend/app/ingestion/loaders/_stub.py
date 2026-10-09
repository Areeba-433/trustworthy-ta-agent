"""Day-0 helper: one fake block that passes the contract test.

Each track stops importing this when its real loader lands. Delete this file
once no loader uses it.
"""

from __future__ import annotations

from pathlib import Path

from app.ingestion.contract import (
    Block,
    BlockKind,
    Lang,
    Location,
    ParsedDocument,
    QualityReport,
    ResourceMeta,
    SourceType,
)
from app.ingestion.dispatcher import failed_document
from app.ingestion.storage import file_sha256


def stub_document(path: Path, meta: ResourceMeta, source_type: SourceType, *, kind: BlockKind,
                  loc: Location, parser: str, lang: Lang = "en",
                  confidence: float | None = None) -> ParsedDocument:
    path = Path(path)
    if path.stat().st_size == 0:
        return failed_document(path, meta, source_type, "This file is empty.",
                               parser=parser, parser_version="stub")
    name = meta.file_name or path.name
    title = Path(name).stem
    text = f"(stub) {parser} output for {name} goes here."
    block = Block(seq=0, kind=kind, text=text, heading_path=[title], loc=loc,
                  lang=lang, confidence=confidence)
    return ParsedDocument(
        resource_id=meta.resource_id, course_id=meta.course_id, file_name=name,
        file_sha256=file_sha256(path), source_type=source_type, title=title,
        parser=parser, parser_version="stub", blocks=[block],
        quality=QualityReport(status="ok", warnings=["(stub) This track isn't built yet."],
                              units_total=1, chars_total=len(text), avg_confidence=confidence),
    )
