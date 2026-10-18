"""What every chunker shares: Draft (a chunk before numbering), merge_locations() and finish()."""
from collections.abc import Callable
from dataclasses import dataclass, field

from app.ingestion.chunking.tokens import count_tokens
from app.ingestion.contract import BlockKind, Chunk, ChunkedDocument, Location, ParsedDocument

TokenCounter = Callable[[str], int]


@dataclass
class Draft:
    """A chunk before numbering: a chunker may build, join or drop drafts freely; finish() numbers them."""
    text: str
    heading_path: list[str]
    loc: Location
    kinds: list[BlockKind] = field(default_factory=list)
    block_seqs: list[int] = field(default_factory=list)


def merge_locations(locs: list[Location]) -> Location:
    """One location covering all of them: the earliest start and the latest end of each kind."""
    def first(name: str):
        values = [getattr(loc, name) for loc in locs if getattr(loc, name) is not None]
        return min(values) if values else None

    def last(start: str, end: str):
        values = [getattr(loc, end) if getattr(loc, end) is not None else getattr(loc, start) for loc in locs]
        values = [v for v in values if v is not None]
        return max(values) if values else None

    page, page_end = first("page"), last("page", "page_end")
    return Location(
        page=page, page_end=page_end if page is not None and page_end is not None and page_end > page else None,
        slide=first("slide"),
        line_start=first("line_start"), line_end=last("line_start", "line_end"),
        t_start=first("t_start"), t_end=last("t_start", "t_end"),
    )


def finish(doc: ParsedDocument, drafts: list[Draft], chunker: str,
           count: TokenCounter = count_tokens) -> ChunkedDocument:
    """Number the drafts 0, 1, 2 ..., give each its chunk_id and token count, and validate the whole result."""
    chunks = [
        Chunk(seq=i, chunk_id=f"{doc.resource_id}:{i}", text=d.text, heading_path=d.heading_path, loc=d.loc,
              kinds=d.kinds, block_seqs=d.block_seqs, token_count=count(d.text))
        for i, d in enumerate(drafts)
    ]
    return ChunkedDocument(resource_id=doc.resource_id, course_id=doc.course_id, source_type=doc.source_type,
                           title=doc.title, chunker=chunker, chunks=chunks)