"""PDF blocks that look like structure but are not: run on our own blocks, after to_blocks().

theorem_labels(): a book sets "Proof", "Theorem 7.6" or "Lemma 7.2" in bold at the start of a paragraph, and Docling
reads the label as a section heading. Every statement and every proof then became a section of its own, so a theorem
and its proof landed in different chunks (DataStructures.pdf pages 343-344: "Lemma 7.2" and its proof, "Immediate
from the preceding lemma.", 20 and 10 tokens). 137 of the book's 517 headings were such labels, and they made 67 of its
76 chunks under 64 tokens. The label becomes a paragraph, and the blocks under it go back to the section around it.

drop_blank_page_notes(): "This page intentionally left blank" says nothing about the course (5 times in the same
book, once run together with the title page's "Fourth Edition"); the note is taken out, and a block left empty goes.
"""
import re
from collections.abc import Sequence

from app.ingestion.contract import Block

_LABEL = re.compile(r"(proof|theorem|lemma|corollary|proposition|definition|example|remark|claim|observation)"
                    r"(\s+\d+(\.\d+)*)?(\s*\([^()]*\))?\s*[.:]?",   # "Theorem 7.6", "Theorem 7.8 (restated)", "Example:"
                    re.IGNORECASE)
_BLANK = re.compile(r"\s*this\s+page\s+(is\s+)?intentionally\s+left\s+blank\.?\s*", re.IGNORECASE)
_TEXT_KINDS = {"paragraph", "list_item", "caption", "figure_text"}


def is_label(text: str) -> bool:
    """A theorem's label alone: "Proof", ". Proof" (a stray full stop before it), "Theorem 7.6", "Example:", with a
    note in brackets ("Theorem 10.10 (Fermat's Lesser Theorem)"). "Proof by Induction" is a real section's name."""
    return _LABEL.fullmatch(text.strip().lstrip(".:;,- ").strip()) is not None


def theorem_labels(blocks: Sequence[Block]) -> list[Block]:
    """The same blocks; a heading that is only a theorem's label becomes a paragraph (extra["from_heading"] = True),
    and the blocks in its section move up to the section around it, so the statement or proof stays in the section
    it belongs to. Nothing is added or taken away: seq numbers stay."""
    out: list[Block] = []
    inside: list[str] | None = None                      # the label's own heading path, as to_blocks() made it
    target: list[str] = []                               # where the blocks of its section go instead

    def moved(path: list[str]) -> list[str]:
        return target + path[len(inside):] if inside is not None and path[:len(inside)] == inside else path

    for block in blocks:
        path = moved(block.heading_path)
        if path is block.heading_path and block.kind == "heading":
            inside = None                                # a heading outside the label's section ends it
        if block.kind == "heading" and is_label(block.text):
            parent = moved(block.heading_path[:-1])      # two "Example:" in a row: the second has the same path
            inside, target = block.heading_path, parent
            block = block.model_copy(update={"kind": "paragraph", "heading_path": parent,
                                             "extra": {**block.extra, "from_heading": True}})
        elif path is not block.heading_path:
            block = block.model_copy(update={"heading_path": path})
        out.append(block)
    return out


def drop_blank_page_notes(blocks: Sequence[Block]) -> list[Block]:
    """The blocks without "This page intentionally left blank": the note is taken out of a text block, and a block
    with nothing else in it is left out. seq numbered again when anything was left out."""
    out: list[Block] = []
    for block in blocks:
        if block.kind in _TEXT_KINDS and _BLANK.search(block.text):
            text = " ".join(_BLANK.sub(" ", block.text).split())
            if not text:
                continue
            block = block.model_copy(update={"text": text})
        out.append(block)
    if len(out) == len(blocks):
        return out
    return [b if b.seq == n else b.model_copy(update={"seq": n}) for n, b in enumerate(out)]
