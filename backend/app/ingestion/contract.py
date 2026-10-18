# backend/app/ingestion/contract.py   (owner: Minahil; changes only by a PR all four approve)
"""The shapes every loader and chunker return: ParsedDocument (blocks) and ChunkedDocument (chunks)."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTRACT_VERSION = "2.0"

BlockKind = Literal["heading", "paragraph", "list_item", "table", "caption",
                    "figure_text", "slide_notes", "code", "transcript", "formula"]
SourceType = Literal["pdf", "docx", "pptx", "audio", "code", "text"]
Lang = Literal["en", "ur", "mixed", "code"]
Status = Literal["ok", "degraded", "failed"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")        # a misspelt field name fails immediately


class Location(_Strict):
    page: int | None = Field(None, ge=1)             # pdf
    page_end: int | None = Field(None, ge=1)         # pdf: set only when the content runs onto later pages
    slide: int | None = Field(None, ge=1)            # pptx
    line_start: int | None = Field(None, ge=1)       # code, text
    line_end: int | None = Field(None, ge=1)
    t_start: float | None = Field(None, ge=0)        # audio, seconds
    t_end: float | None = Field(None, ge=0)

    @model_validator(mode="after")
    def _check_page_range(self) -> "Location":
        if self.page_end is not None and (self.page is None or self.page_end < self.page):
            raise ValueError("page_end needs a page and cannot come before it")
        return self


class Block(_Strict):
    seq: int = Field(ge=0)
    kind: BlockKind
    text: str = Field(min_length=1)
    heading_path: list[str] = Field(min_length=1)   # the context; starts with the title
    loc: Location
    lang: Lang = "en"
    confidence: float | None = Field(None, ge=0, le=1)   # set only for speech-to-text (audio)
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
    chars_total: int = Field(ge=0)
    avg_confidence: float | None = Field(None, ge=0, le=1)
    seconds_taken: dict[str, float] = Field(default_factory=dict)


# Which Location field is mandatory per source type. DOCX has no pages: its citation is the heading path.
LOCATION_FIELD: dict[str, str | None] = {
    "pdf": "page", "pptx": "slide",
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


MAX_CHUNK_TOKENS = 512      # a ceiling, not the cut rule: structure decides where chunks end (see the plan)


class Chunk(_Strict):
    seq: int = Field(ge=0)
    chunk_id: str                                    # f"{resource_id}:{seq}": a re-run overwrites, never duplicates
    text: str = Field(min_length=1)                  # what the student sees and the LLM reads
    heading_path: list[str] = Field(min_length=1)    # starts with the title: context, and the DOCX citation
    loc: Location
    kinds: list[BlockKind] = Field(min_length=1)     # the block kinds inside, e.g. ["paragraph", "code"]
    block_seqs: list[int] = Field(min_length=1)      # the blocks it came from: traceable to the source
    token_count: int = Field(ge=1, le=MAX_CHUNK_TOKENS)


class ChunkedDocument(_Strict):
    contract_version: str = CONTRACT_VERSION
    resource_id: str
    course_id: str
    source_type: SourceType
    title: str = Field(min_length=1)
    chunker: str                                     # e.g. "pdf-sections/1": goes into the cache key and the report
    chunks: list[Chunk] = Field(min_length=1)        # a failed ParsedDocument is never chunked

    @model_validator(mode="after")
    def _check_rules(self) -> "ChunkedDocument":
        needed = LOCATION_FIELD[self.source_type]
        for i, c in enumerate(self.chunks):
            if c.seq != i or c.chunk_id != f"{self.resource_id}:{i}":
                raise ValueError(f"chunk {i}: seq and chunk_id must follow the order")
            if c.heading_path[0] != self.title:
                raise ValueError(f"chunk {i}: heading_path must start with the title")
            if needed and getattr(c.loc, needed) is None:
                raise ValueError(f"chunk {i}: loc.{needed} is required for {self.source_type}")
        return self


def embedding_text(chunk: Chunk) -> str:
    """What gets embedded later: the heading path gives a short chunk its context."""
    return " > ".join(chunk.heading_path) + "\n" + chunk.text