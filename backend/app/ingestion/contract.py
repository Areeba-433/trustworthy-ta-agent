"""The ingestion contract: what every loader returns, whatever the file type.

Owner: Minahil. FROZEN after day 0: change it only through one PR by Minahil,
approved by all four, merged the same day. Never change it inside a feature PR.

The chunker reads only these shapes, so it never needs to know whether a block
came from a PDF, a scan, a recording or a .cpp file.
"""

from __future__ import annotations

from typing import Literal, get_args

from pydantic import BaseModel, Field

BlockKind = Literal["heading", "paragraph", "list_item", "table", "caption",
                    "slide_notes", "code", "transcript", "ocr_text"]
SourceType = Literal["pdf", "docx", "pptx", "scanned_pdf", "image", "audio", "code", "text"]
Lang = Literal["en", "ur", "mixed", "code"]

SOURCE_TYPES: tuple[str, ...] = get_args(SourceType)


class Location(BaseModel):
    page: int | None = None          # PDF, scanned PDF, image (=1)
    slide: int | None = None         # PPTX
    line_start: int | None = None    # code, text
    line_end: int | None = None
    t_start: float | None = None     # audio, seconds
    t_end: float | None = None


class Block(BaseModel):
    seq: int                          # order in the document, 0, 1, 2 ...
    kind: BlockKind
    text: str                         # cleaned; tables as Markdown; code untouched
    heading_path: list[str]           # the context: ["Lecture 4", "Normalization", "3NF"]
    loc: Location
    lang: Lang = "en"
    confidence: float | None = None   # OCR or speech-to-text confidence, 0 to 1
    extra: dict = Field(default_factory=dict)   # track-specific, never read by the chunker


class QualityReport(BaseModel):
    status: Literal["ok", "degraded", "failed"]
    warnings: list[str] = []          # shown to the teacher in plain words
    units_total: int                  # pages, slides, seconds or lines
    units_ocr: int = 0
    chars_total: int                  # sum of len(block.text) over all blocks
    avg_confidence: float | None = None
    seconds_taken: dict[str, float] = {}   # per stage: precheck, parse, clean


class ParsedDocument(BaseModel):
    resource_id: str
    course_id: str
    file_name: str
    file_sha256: str
    source_type: SourceType
    title: str                        # becomes heading_path[0]
    parser: str                       # "docling", "docling+easyocr", "whisper", "tree-sitter"
    parser_version: str
    blocks: list[Block]
    quality: QualityReport


class ResourceMeta(BaseModel):
    """What the dispatcher passes to every loader, next to the file path."""
    resource_id: str
    course_id: str
    file_name: str | None = None      # the teacher's original name; the stored file may be renamed
    precheck: dict = Field(default_factory=dict)   # dispatcher's pre-check, e.g. {"large_image_pages": [3]}


# Every loader has this signature, and never raises on bad input:
#     def load(path: Path, meta: ResourceMeta) -> ParsedDocument


# ---------------------------------------------------------------------------
# Rules that come with the contract. tests/ingestion/test_contract.py runs
# contract_violations() on every loader's output; an empty list means "passes".
# ---------------------------------------------------------------------------

# Location is mandatory for the field(s) that match the source type, so a
# citation can be built from `loc` alone.
LOCATION_FIELDS: dict[str, tuple[str, ...]] = {
    "pdf": ("page",),
    "scanned_pdf": ("page",),
    "image": ("page",),
    "pptx": ("slide",),
    # DOCX has no page numbers (Word only paginates on screen). Open decision D1
    # in docs/ingestion-decisions.md: page stays None and the heading path
    # carries the citation ("Lab manual > Section 3.2").
    "docx": (),
    "code": ("line_start", "line_end"),
    "text": ("line_start", "line_end"),
    "audio": ("t_start", "t_end"),
}


def contract_violations(doc: ParsedDocument) -> list[str]:
    """Every way `doc` breaks the contract rules, in plain words. [] means it passes."""
    problems: list[str] = []
    quality = doc.quality

    if quality.status == "failed":
        if not quality.warnings:
            problems.append("a failed document needs a warning the teacher can read")
        return problems  # a failed document may have no blocks

    if not doc.blocks:
        problems.append(f"status is {quality.status!r} but there are no blocks")
    if not doc.title.strip():
        problems.append("title is empty")
    if quality.units_total < 1:
        problems.append("units_total must be at least 1 for a document that was read")
    chars = sum(len(b.text) for b in doc.blocks)
    if quality.chars_total != chars:
        problems.append(f"chars_total is {quality.chars_total} but the blocks hold {chars} characters")

    required = LOCATION_FIELDS[doc.source_type]
    for i, block in enumerate(doc.blocks):
        where = f"block {i} ({block.kind})"
        if block.seq != i:
            problems.append(f"{where}: seq is {block.seq}, expected {i} (0, 1, 2 ... without gaps)")
        if not block.text.strip():
            problems.append(f"{where}: text is empty")
        if not block.heading_path or block.heading_path[0] != doc.title:
            problems.append(f"{where}: heading_path must start with the title {doc.title!r}")
        for field in required:
            if getattr(block.loc, field) is None:
                problems.append(f"{where}: loc.{field} is required for {doc.source_type}")
        loc = block.loc
        if loc.line_start is not None and loc.line_end is not None and loc.line_start > loc.line_end:
            problems.append(f"{where}: line_start is after line_end")
        if loc.t_start is not None and loc.t_end is not None and loc.t_start > loc.t_end:
            problems.append(f"{where}: t_start is after t_end")
        if block.confidence is not None and not 0.0 <= block.confidence <= 1.0:
            problems.append(f"{where}: confidence must be between 0 and 1")
        if block.kind == "code" and block.lang != "code":
            problems.append(f"{where}: code blocks must have lang='code'")
    return problems
