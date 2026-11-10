"""chunk_sections(): the shared chunker for structured documents (PDF, DOCX, PPTX and Markdown).

1. Blocks are grouped into sections: a heading, or a change of section_key, starts a new section.
2. A block longer than MAX_CHUNK_TOKENS is cut first (split_to_fit): between sentences, code lines or table rows.
3. Each section's blocks are packed, in order, into chunks of up to `target` tokens. A block is never cut to fill
   a chunk: one that does not fit starts the next chunk.
4. A last chunk under `minimum` tokens joins the chunk before it in the same section, if the two fit the limit.
With join_intros=True (books), a short introduction joins what it introduces, as a chunk of its own it is too small
to answer anything:
- a whole section under `minimum` tokens that is followed by its first subsection joins that subsection, under the
  subsection's heading path ("This chapter covers ..." and the chapter's first section);
- a chunk under `minimum` tokens joins the next chunk of its section, if the two fit the limit ("Here's the
  listing:" and the listing that did not fit next to it).
Headings add no text: the heading path already travels with every chunk and is embedded with it.
Every chunk lists the figures of its blocks (figure_ids), so a figure is never lost between blocks and chunks.
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
                   count: TokenCounter = count_tokens, join_intros: bool = False) -> list[Draft]:
    if doc.quality.status == "failed":
        raise ValueError("a failed document has no blocks to chunk")
    sections = list(_sections(doc.blocks, section_key))
    if join_intros:
        sections = _join_intros(sections, minimum, count)
    drafts: list[Draft] = []
    for section in sections:
        pieces = [(block, part) for block in section for part in _fit(block, target, count)]
        section_drafts = _pack(pieces, target, count)
        if join_intros:
            _join_small_leads(section_drafts, minimum, count)
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


def _join_intros(sections: list[list[Block]], minimum: int, count: TokenCounter) -> list[list[Block]]:
    """Each section under `minimum` tokens joins the next section when that one is its subsection (its heading path
    goes on from this one's); the joined blocks take the subsection's heading path, which holds both headings.
    Joined sections can join again: a short chapter introduction, then a short section introduction."""
    joined: list[list[Block]] = []
    carried: list[Block] = []
    for section, following in zip(sections, sections[1:] + [[]]):
        path = section[0].heading_path
        section = [block.model_copy(update={"heading_path": path}) for block in carried] + section
        carried = []
        if following and _goes_on(following[0].heading_path, path) \
                and count(SEPARATOR.join(block.text for block in section)) < minimum:
            carried = section
        else:
            joined.append(section)
    return joined


def _goes_on(path: list[str], parent: list[str]) -> bool:
    return len(path) > len(parent) and path[:len(parent)] == parent


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
        figure_ids=list(dict.fromkeys(b.figure_id for b in blocks if b.figure_id)),
    )


def _join_small_leads(drafts: list[Draft], minimum: int, count: TokenCounter) -> None:
    """Each chunk under `minimum` tokens, but the last, joins the chunk after it, if the two fit the limit."""
    n = 0
    while n < len(drafts) - 1:
        if count(drafts[n].text) < minimum:
            joined = _merged(drafts[n], drafts[n + 1])
            if count(joined.text) <= MAX_CHUNK_TOKENS:
                drafts[n:n + 2] = [joined]
                continue
        n += 1


def _join_small_tail(drafts: list[Draft], minimum: int, count: TokenCounter) -> None:
    if len(drafts) < 2 or count(drafts[-1].text) >= minimum:
        return
    joined = _merged(drafts[-2], drafts[-1])
    if count(joined.text) <= MAX_CHUNK_TOKENS:
        drafts[-2:] = [joined]


def _merged(before: Draft, after: Draft) -> Draft:
    return Draft(text=before.text + SEPARATOR + after.text, heading_path=before.heading_path,
                 loc=merge_locations([before.loc, after.loc]),
                 kinds=list(dict.fromkeys(before.kinds + after.kinds)),
                 block_seqs=list(dict.fromkeys(before.block_seqs + after.block_seqs)),
                 figure_ids=list(dict.fromkeys(before.figure_ids + after.figure_ids)))
