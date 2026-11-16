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

keep_line_breaks() gives a slide's lines back. A slide lists short points one per line, often without bullets, and
Docling makes one paragraph of a text box: DSA slide 3 read "Implementation of 20 DSA problems Individual testing
and dry runs Integration into a single menu-driven system", three points as one sentence. The PDF still has the
lines. Between two of them the text gets a line break, unless the second line only goes on with the first: it
starts with a small letter ("system", "concepts") and its first word would not have fitted at the end of the line
before, so PowerPoint moved it down. A word broken with a hyphen goes on too. Only paragraphs change, and only when
the PDF's lines in the paragraph's box have exactly Docling's letters (spaces and dashes aside); a line of another
item inside the box is left out (DSA slide 7: Docling made an item of "Min Stack — O(1) minimum retrieval", inside
the box of the three points around it). The words stay Docling's: only spaces become line breaks.
"""
import logging
from collections.abc import Sequence
from pathlib import Path

import pypdfium2 as pdfium
from docling_core.types.doc import DocItem, DoclingDocument

from app.ingestion.contract import Block
from app.ingestion.pdf_code import (_WORD_GAP, _ascii, _boxes, _Char, _inside, _lines, _Page, _page, _width,
                                    _words)

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


_SPACE = 0.5      # columns: the width of a space, in the line's usual letter width
_MARGIN = 1.0     # points: a word that ends this little past the widest line still fits


def keep_line_breaks(blocks: Sequence[Block], doc: DoclingDocument, path: Path) -> list[Block]:
    """The blocks of a PDF of slides, each paragraph with the line breaks between its points; how many breaks were
    given back is in the block's extra["line_breaks"]. Other PDFs' blocks come back unchanged."""
    if not is_slides(doc) or not any(b.kind == "paragraph" for b in blocks):
        return list(blocks)
    items = {item.self_ref: item for item in doc.texts}
    pages: dict[int, _Page | None] = {}
    pdf = pdfium.PdfDocument(str(path))
    try:
        out = [_with_breaks(b, items.get(b.extra.get("ref")), pdf, pages) if b.kind == "paragraph" else b
               for b in blocks]
    finally:
        pdf.close()
    logger.info("slides: line breaks given back to %d paragraphs", sum(a is not b for a, b in zip(out, blocks)))
    return out


def _with_breaks(block: Block, item: DocItem | None, pdf: pdfium.PdfDocument, pages: dict[int, _Page | None]) -> Block:
    text = block.text
    if item is None or len(item.prov) != 1 or " " not in text.strip():
        return block
    page = _page(pdf, pages, item.prov[0].page_no, None)
    if page is None:
        return block
    wanted = _squash(text)
    for box in _boxes(item.prov[0].bbox, page):
        chars = [c for c in page.chars if _inside(c, box)]
        lines, ends, at = [], [], 0          # the PDF's lines that give Docling's text, and where each one ends in it
        for line in _lines(chars):
            own = _squash("".join(c.text for c in line))
            if own and wanted.startswith(own, at):           # a line of another item inside the box is skipped
                at += len(own)
                lines.append(line)
                ends.append(at)
        if at != len(wanted) or len(lines) < 2:
            continue
        width, widest = _width(chars), max(line[-1].right for line in lines)
        breaks = {end for end, line, below in zip(ends, lines, lines[1:]) if _breaks(line, below, widest, width)}
        out, count = list(text), 0
        for n, ch in enumerate(text):
            if not ch.isspace():
                count += len(_squash(ch))
            elif count in breaks:            # the space between the two lines (a word broken in two has none)
                out[n] = "\n"
                breaks.discard(count)
        new = "".join(out)
        if new == text:
            return block
        return block.model_copy(update={"text": new, "extra": {**block.extra, "line_breaks": new.count("\n")}})
    return block


def _squash(text: str) -> str:
    """The letters, digits and signs of a text, to compare Docling's text with the PDF's: no spaces, no dashes
    (Docling read "only – O(n)" as "only -O(n)"; pdfium marks a word broken with a hyphen with U+FFFE)."""
    return "".join(ch for ch in _ascii(text).replace("\u2212", "-") if not ch.isspace() and ch not in "-\ufffe")


def _breaks(line: list[_Char], below: list[_Char], widest: float, width: float) -> bool:
    """True when the line below starts a new point: its first word would have fitted on `line`, or it starts with
    anything but a small letter. False when it goes on with `line`: a word broken at the line's end (pdfium marks
    the break with U+FFFE), or a small letter that PowerPoint moved down because the word did not fit."""
    ends, starts = _words(line, width)[-1:], _words(below, width)[:1]
    if ends and ends[0].endswith("\ufffe"):
        return False
    if not starts or not starts[0][:1].islower():
        return True
    end = below[0].right                                 # where the first word of the line below ends
    for previous, c in zip(below, below[1:]):
        if c.spaced or c.left - previous.right > width * _WORD_GAP:
            break
        end = c.right
    return line[-1].right + _SPACE * width + (end - below[0].left) <= widest + _MARGIN


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
