"""chunk_sections(): the shared chunker for structured documents (PDF, DOCX, PPTX and Markdown).

1. Blocks are grouped into sections: a heading, or a change of section_key, starts a new section.
2. A block longer than MAX_CHUNK_TOKENS is cut first (split_to_fit): between sentences, code lines or table rows.
3. Each section's blocks are packed, in order, into chunks of up to `target` tokens. A block is never cut to fill
   a chunk: one that does not fit starts the next chunk.
4. A last chunk under `minimum` tokens joins the chunk before it in the same section, if the two fit the limit.
Headings add no text: the heading path already travels with every chunk and is embedded with it.
"""
from collections.abc import Callable, Hashable, Iterator

from app.ingestion.chunking.base import Draft, TokenCounter, merge_locations
from app.ingestion.chunking.split import split_to_fit
from app.ingestion.chunking.tokens import count_tokens
from app.ingestion.contract import MAX_CHUNK_TOKENS, Block, ParsedDocument

TARGET_TOKENS = 384         # starting values from the plan; the evaluation questions decide whether they move
MIN_TOKENS = 64
SEPARATOR = "\n\n"          # between the blocks of one chunk
_JOIN_ALLOWANCE = 2         # tokens a separator may add between joined blocks (finish() checks the exact count)


def by_heading_path(block: Block) -> Hashable:
    return tuple(block.heading_path)


def by_slide(block: Block) -> Hashable:
    return block.loc.slide


def chunk_sections(doc: ParsedDocument, *, section_key: Callable[[Block], Hashable] = by_heading_path,
                   target: int = TARGET_TOKENS, minimum: int = MIN_TOKENS,
                   count: TokenCounter = count_tokens) -> list[Draft]:
    if doc.quality.status == "failed":
        raise ValueError("a failed document has no blocks to chunk")
    drafts: list[Draft] = []
    for section in _sections(doc.blocks, section_key):
        pieces = [(block, part) for block in section for part in _fit(block, target, count)]
        section_drafts = _pack(pieces, target, count)
        _join_small_tail(section_drafts, minimum, count)
        drafts.extend(section_drafts)
    return drafts


def _sections(blocks: list[Block], key: Callable[[Block], Hashable]) -> Iterator[list[Block]]:
    section: list[Block] = []
    current: Hashable = object()                  # equal to no real key, so the first block opens a section
    for block in blocks:
        block_key = key(block)
        if block.kind == "heading" or block_key != current:
            if section:
                yield section
            section, current = [], block_key
        if block.kind != "heading":
            section.append(block)
    if section:
        yield section


def _fit(block: Block, target: int, count: TokenCounter) -> list[str]:
    if count(block.text) <= MAX_CHUNK_TOKENS:
        return [block.text]                       # up to the limit, a block stays whole
    return split_to_fit(block.text, block.kind, target, count)


def _pack(pieces: list[tuple[Block, str]], target: int, count: TokenCounter) -> list[Draft]:
    drafts: list[Draft] = []
    current: list[tuple[Block, str]] = []
    size = 0
    for block, text in pieces:
        tokens = count(text)
        if current and size + _JOIN_ALLOWANCE + tokens > target:
            drafts.append(_draft(current))
            current, size = [], 0
        size += tokens + (_JOIN_ALLOWANCE if current else 0)
        current.append((block, text))
    if current:
        drafts.append(_draft(current))
    return drafts


def _draft(pieces: list[tuple[Block, str]]) -> Draft:
    blocks = [block for block, _ in pieces]
    return Draft(
        text=SEPARATOR.join(text for _, text in pieces),
        heading_path=list(blocks[0].heading_path),
        loc=merge_locations([b.loc for b in blocks]),
        kinds=list(dict.fromkeys(b.kind for b in blocks)),        # in order, without repeats
        block_seqs=list(dict.fromkeys(b.seq for b in blocks)),
    )


def _join_small_tail(drafts: list[Draft], minimum: int, count: TokenCounter) -> None:
    if len(drafts) < 2 or count(drafts[-1].text) >= minimum:
        return
    before, tail = drafts[-2], drafts[-1]
    text = before.text + SEPARATOR + tail.text
    if count(text) <= MAX_CHUNK_TOKENS:
        drafts[-2:] = [Draft(text=text, heading_path=before.heading_path,
                             loc=merge_locations([before.loc, tail.loc]),
                             kinds=list(dict.fromkeys(before.kinds + tail.kinds)),
                             block_seqs=list(dict.fromkeys(before.block_seqs + tail.block_seqs)))]