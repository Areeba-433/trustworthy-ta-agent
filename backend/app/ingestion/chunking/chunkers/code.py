"""C++ files: one chunk per function, class, struct or enum (owner: Fareeha).

The code loader (loaders/code.py) already used Tree-sitter to cut the file into blocks:
  * "unit" blocks: one function / class / struct / enum each (heading_path ends with its name)
  * "glue" blocks: the lines in between (#include, using, globals, "namespace x {", "}", "#endif")

Rules of this chunker:
  1. Every unit becomes its own chunk, so a chunk is always a whole function or class.
  2. A small glue block (under MIN_TOKENS) is not worth a chunk of its own ("#endif" is 1 token):
     glue that closes something ("}  // namespace util", "#endif") joins the chunk before it;
     other glue ("#include", "namespace util {") joins the next unit.
  3. A big glue block (many globals or macros) stays a chunk of its own.
  4. Anything over MAX_CHUNK_TOKENS is cut between lines by the shared split_to_fit(), and each
     piece keeps its own exact line numbers for the citation.
  5. Code is copied exactly: blocks are joined with "" because each block already ends with its newline.
"""
from app.ingestion.chunking.base import Draft, TokenCounter, finish, merge_locations
from app.ingestion.chunking.registry import register_chunker
from app.ingestion.chunking.sections import MIN_TOKENS, TARGET_TOKENS
from app.ingestion.chunking.split import split_to_fit
from app.ingestion.chunking.tokens import count_tokens
from app.ingestion.contract import MAX_CHUNK_TOKENS, Block, ChunkedDocument, Location, ParsedDocument

NAME = "code-units/1"     # saved with every chunk: raise the number whenever this chunker's output changes

_GLUE_PREFIXES = ("namespace ", 'extern "C"')
_CLOSERS = ("}", "#endif", "#else", "#elif")


def is_glue(block: Block) -> bool:
    """Glue = lines between units. Its heading path is only the title, or ends with a namespace."""
    return len(block.heading_path) == 1 or block.heading_path[-1].startswith(_GLUE_PREFIXES)


def _closes(block: Block) -> bool:
    """Glue that ends something opened earlier: it belongs with the chunk before it."""
    return block.text.lstrip().startswith(_CLOSERS)


@register_chunker("code")
def chunk(doc: ParsedDocument) -> ChunkedDocument:
    return finish(doc, code_drafts(doc), NAME)


def code_drafts(doc: ParsedDocument, count: TokenCounter = count_tokens) -> list[Draft]:
    if doc.quality.status == "failed":
        raise ValueError("a failed document has no blocks to chunk")

    groups = _group(doc.blocks, count)
    drafts: list[Draft] = []
    for group in groups:
        drafts.extend(_to_drafts(group, count))
    return drafts


def _group(blocks: list[Block], count: TokenCounter) -> list[list[Block]]:
    """Decide which blocks go together: each unit is a group; small glue joins a neighbouring unit."""
    groups: list[list[Block]] = []
    waiting: list[Block] = []          # small glue waiting for the next unit

    for block in blocks:
        if is_glue(block):
            if count(block.text) >= MIN_TOKENS:      # big glue: a chunk of its own
                groups.extend([[b] for b in waiting])
                groups.append([block])
                waiting = []
            elif not waiting and _closes(block) and _fits(groups, block, count):
                groups[-1].append(block)             # "}" / "#endif": back to the chunk it closes
            else:
                waiting.append(block)
            continue
        group = [*waiting, block]                    # small glue goes in front of the unit
        if waiting and count(_join(group)) > MAX_CHUNK_TOKENS:
            groups.extend([[b] for b in waiting])    # does not fit: glue stays alone
            group = [block]
        groups.append(group)
        waiting = []

    for glue in waiting:                             # glue at the end of the file
        if _fits(groups, glue, count):
            groups[-1].append(glue)
        else:
            groups.append([glue])
    return groups


def _fits(groups: list[list[Block]], block: Block, count: TokenCounter) -> bool:
    return bool(groups) and count(_join(groups[-1] + [block])) <= MAX_CHUNK_TOKENS


def _join(blocks: list[Block]) -> str:
    return "".join(b.text for b in blocks)


def _path(group: list[Block]) -> list[str]:
    """The chunk is named after its unit; a glue-only chunk keeps the glue's path."""
    units = [b for b in group if not is_glue(b)]
    return list((units[0] if units else group[0]).heading_path)


def _to_drafts(group: list[Block], count: TokenCounter) -> list[Draft]:
    text = _join(group)
    path = _path(group)
    seqs = [b.seq for b in group]
    if count(text) <= MAX_CHUNK_TOKENS:
        return [Draft(text=text, heading_path=path, loc=merge_locations([b.loc for b in group]),
                      kinds=["code"], block_seqs=seqs)]

    # Too long (a very big function or class): cut between lines, keep exact line numbers per piece.
    first_line = min(b.loc.line_start for b in group)
    drafts: list[Draft] = []
    cursor = 0
    for piece in split_to_fit(text, "code", TARGET_TOKENS, count):
        start, end, cursor = _find_lines(text, piece, cursor, first_line)
        drafts.append(Draft(text=piece, heading_path=path, loc=Location(line_start=start, line_end=end),
                            kinds=["code"], block_seqs=seqs))
    return drafts


def _find_lines(text: str, piece: str, cursor: int, first_line: int) -> tuple[int, int, int]:
    """Where `piece` sits inside `text`: (first line, last line, new cursor). Lines are 1-based."""
    lines = [line for line in piece.split("\n") if line.strip()]
    begin = text.find(lines[0], cursor)
    last = text.find(lines[-1], begin)
    finish_at = last + len(lines[-1])
    start = first_line + text.count("\n", 0, begin)
    end = first_line + text.count("\n", 0, finish_at)
    return start, end, finish_at