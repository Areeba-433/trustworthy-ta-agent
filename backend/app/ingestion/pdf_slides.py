"""Slides saved as PDF: one slide, one topic.

In a book a heading starts a section of paragraphs. On a slide the slide itself is the unit: its title says what it
is about, and a bold "Advantages:" is only a label over two bullets. Docling reads such labels as headings, and the
chunker makes a section of each: a 19-slide PowerPoint deck (DSA) got 70 headings and 46 chunks with a median of
23 tokens, 43 of them under 64. A label is also left out of the chunk's text then, as headings add no text.

as_slides() keeps one heading per slide, its title, so a slide is one section:
- the title is the first heading on the slide that is not a label ending in ":" ("Name:" on a title slide is a label),
  the shallowest if there are several; a slide with only labels takes its first. It goes first on its slide;
- every other heading on the slide becomes a paragraph, so "Advantages:" stays in the chunk's text;
- a slide with the title of the slide before goes on with it (Pointers slides 8 to 12, "Accessing the Variable
  Pointed To"): its title heading is left out, so the chunker packs them as one section;
- a slide without a title goes on with the slide before it.

A PDF is slides when every page is wider than tall: PowerPoint, Google Slides and Canva export that way; books, notes
and assignments are taller than wide.
"""
import logging
from collections.abc import Sequence

from docling_core.types.doc import DoclingDocument

from app.ingestion.contract import Block

logger = logging.getLogger(__name__)


def is_slides(doc: DoclingDocument) -> bool:
    return bool(doc.pages) and all(page.size.width > page.size.height for page in doc.pages.values())


def as_slides(blocks: Sequence[Block], doc: DoclingDocument) -> list[Block]:
    """The blocks of a PDF of slides with one heading per slide, its title; seq numbered again. Other PDFs' blocks
    come back unchanged."""
    if not blocks or not is_slides(doc):
        return list(blocks)
    root = blocks[0].heading_path[0]
    out: list[Block] = []
    title: str | None = None                     # the title of the slide before
    for page in _pages(blocks):
        heading = _title([b for b in page if b.kind == "heading"])
        goes_on = heading is not None and title is not None and _same(heading.text, title)
        if heading is not None:
            title = heading.text
        path = [root, title] if title else [root]
        if heading is not None and not goes_on:
            out.append(heading.model_copy(update={"heading_path": path}))
        for block in page:
            if block is not heading:
                kind = "paragraph" if block.kind == "heading" else block.kind
                out.append(block.model_copy(update={"kind": kind, "heading_path": path}))
    logger.info("slides: %d headings kept of %d", sum(b.kind == "heading" for b in out),
                sum(b.kind == "heading" for b in blocks))
    return [block.model_copy(update={"seq": n}) for n, block in enumerate(out)]


def _pages(blocks: Sequence[Block]) -> list[list[Block]]:
    """The blocks of each page, pages in their order (blocks without a page go with the page before)."""
    pages: list[list[Block]] = []
    for block in blocks:
        if not pages or block.loc.page is not None and block.loc.page != pages[-1][0].loc.page:
            pages.append([])
        pages[-1].append(block)
    return pages


def _title(headings: list[Block]) -> Block | None:
    if not headings:
        return None
    titles = [h for h in headings if not h.text.rstrip().endswith(":")] or headings[:1]
    shallowest = min(len(h.heading_path) for h in titles)
    return next(h for h in titles if len(h.heading_path) == shallowest)


def _same(a: str, b: str) -> bool:
    return " ".join(a.split()).casefold() == " ".join(b.split()).casefold()
