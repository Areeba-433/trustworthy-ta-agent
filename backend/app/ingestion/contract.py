# backend/app/ingestion/contract.py   (owner: Minahil; changes only by a PR all four approve)
"""The one shape every loader returns and the chunker reads."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTRACT_VERSION = "1.0"

BlockKind = Literal["heading", "paragraph", "list_item", "table", "caption",
                    "slide_notes", "code", "transcript", "ocr_text"]
SourceType = Literal["pdf", "docx", "pptx", "scanned_pdf", "image", "audio", "code", "text"]
Lang = Literal["en", "ur", "mixed", "code"]
Status = Literal["ok", "degraded", "failed"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")        # a misspelt field name fails immediately


class Location(_Strict):
    page: int | None = Field(None, ge=1)             # pdf, scanned_pdf, image (=1)
    slide: int | None = Field(None, ge=1)            # pptx
    line_start: int | None = Field(None, ge=1)       # code, text
    line_end: int | None = Field(None, ge=1)
    t_start: float | None = Field(None, ge=0)        # audio, seconds
    t_end: float | None = Field(None, ge=0)


class Block(_Strict):
    seq: int = Field(ge=0)
    kind: BlockKind
    text: str = Field(min_length=1)
    heading_path: list[str] = Field(min_length=1)   # the context; starts with the title
    loc: Location
    lang: Lang = "en"
    confidence: float | None = Field(None, ge=0, le=1)   # set only for OCR and speech-to-text
    extra: dict = Field(default_factory=dict)       # track-private; the chunker never reads it


class PrecheckResult(_Strict):
    source_type: SourceType                         # which loader gets the file
    ok: bool = True                                 # False: don't load, fail with `reason`
    reason: str = ""
    pages_total: int = 0
    scanned_pages: list[int] = Field(default_factory=list)
    garbage_pages: list[int] = Field(default_factory=list)
    large_image_pages: list[int] = Field(default_factory=list)
    seconds: float = 0.0


class ResourceMeta(_Strict):
    resource_id: str
    course_id: str
    file_name: str
    file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")   # hashed once by the dispatcher
    precheck: PrecheckResult


class QualityReport(_Strict):
    status: Status
    warnings: list[str] = Field(default_factory=list)      # plain words for the teacher
    units_total: int = Field(ge=0)                         # pages, slides, seconds or lines
    units_ocr: int = Field(0, ge=0)
    chars_total: int = Field(ge=0)
    avg_confidence: float | None = Field(None, ge=0, le=1)
    seconds_taken: dict[str, float] = Field(default_factory=dict)


# Which Location field is mandatory per source type. DOCX has no pages: its citation is the heading path.
LOCATION_FIELD: dict[str, str | None] = {
    "pdf": "page", "scanned_pdf": "page", "image": "page", "pptx": "slide",
    "audio": "t_start", "code": "line_start", "text": "line_start", "docx": None,
}


class ParsedDocument(_Strict):
    contract_version: str = CONTRACT_VERSION
    resource_id: str
    course_id: str
    file_name: str
    file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_type: SourceType
    title: str = Field(min_length=1)
    parser: str
    parser_version: str
    blocks: list[Block]
    quality: QualityReport

    @model_validator(mode="after")
    def _check_rules(self) -> "ParsedDocument":
        if self.quality.status == "failed":
            if self.blocks:
                raise ValueError("a failed document must have no blocks")
            if not self.quality.warnings:
                raise ValueError("a failed document needs a warning the teacher can read")
            return self
        if not self.blocks:
            raise ValueError("a document that didn't fail needs at least one block")
        needed = LOCATION_FIELD[self.source_type]
        for i, b in enumerate(self.blocks):
            if b.seq != i:
                raise ValueError(f"block {i}: seq must be {i}, got {b.seq}")
            if b.heading_path[0] != self.title:
                raise ValueError(f"block {i}: heading_path must start with the title")
            if needed and getattr(b.loc, needed) is None:
                raise ValueError(f"block {i}: loc.{needed} is required for {self.source_type}")
        return self