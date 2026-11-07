"""split_long_headings(): a heading that Docling made of a whole region is cut back to the heading itself.

On book page 351 Docling labelled everything from the last line of a program's output to the bottom of the page as
one heading: 164 words, the COUNTPP3 listing among them. As a heading it would lose the listing's lines, and it would
also become the section name of every block up to the next heading. A real heading is short and printed in the
book's heading font, and Docling's other headings show which font that is. So the item keeps only the lines in the
heading font ("Nameless Temporary Objects"); the lines before and after them become paragraphs of their own, where
restore_code_lines() then finds the code. Without a line in the heading font the item's words all go to one
paragraph. Nothing changes unless the PDF has exactly Docling's words in the item's box.

Runs on Docling's result before to_blocks(), which builds the heading paths.
"""
import logging
from collections import Counter
from pathlib import Path

import pypdfium2 as pdfium
from docling_core.types.doc import (BoundingBox, ContentLayer, CoordOrigin, DocItemLabel, DoclingDocument,
                                    ProvenanceItem, SectionHeaderItem)

from app.ingestion.pdf_code import _Char, _Page, _ascii, _boxes, _inside, _line_words, _lines, _page, _width

logger = logging.getLogger(__name__)

_MAX_WORDS = 15         # a heading with more words than this is no heading
_SHORT = 8              # Docling's headings with at most this many words show the book's heading font
_SAMPLE = 40            # at most this many of them are read, spread over the book
_FONT_SHARE = 0.2       # a font with this share of the short headings' letters is a heading font
_LINE_SHARE = 0.9       # a line with this share of its letters in a heading font is a line of a heading


def split_long_headings(doc: DoclingDocument, path: Path) -> int:
    """Cut each too-long heading of Docling's result for the PDF at `path` back to its heading lines; changes
    `doc` in place. Returns how many headings were cut."""
    headings = [item for item in doc.texts if isinstance(item, SectionHeaderItem)
                and item.content_layer == ContentLayer.BODY and len(item.prov) == 1]
    long = [item for item in headings if len(item.text.split()) > _MAX_WORDS]
    if not long:
        return 0
    pages: dict[int, _Page | None] = {}
    pdf = pdfium.PdfDocument(str(path))
    try:
        short = [item for item in headings if 0 < len(item.text.split()) <= _SHORT]
        fonts = _heading_fonts(short[::max(1, len(short) // _SAMPLE)], pdf, pages)
        cut = sum(_cut(doc, item, pdf, pages, fonts) for item in long)
    finally:
        pdf.close()
    logger.info("%d too-long headings cut back to their heading lines", cut)
    return cut


def _heading_fonts(headings: list[SectionHeaderItem], pdf: pdfium.PdfDocument,
                   pages: dict[int, _Page | None]) -> set[str]:
    """The fonts that make up a fifth or more of the letters of Docling's short headings."""
    letters: Counter = Counter()
    for item in headings:
        found = _found_lines(item, pdf, pages)
        if found is not None:
            letters.update(c.font for line in found[0] for c in line if c.text.isalpha())
    total = sum(letters.values())
    return {font for font, n in letters.items() if total and n >= _FONT_SHARE * total}


def _found_lines(item: SectionHeaderItem, pdf: pdfium.PdfDocument, pages: dict[int, _Page | None]
                 ) -> tuple[list[list[_Char]], list[int], tuple[float, float], _Page] | None:
    """(the PDF's lines in the item's box, how many of Docling's words each holds, the shift from Docling's
    coordinates to pdfium's, the page), or None when the box does not hold exactly Docling's words."""
    prov = item.prov[0]
    page = _page(pdf, pages, prov.page_no, None)
    words = [_ascii(word) for word in item.text.split()]
    if page is None or not words:
        return None
    for shift, box in zip([(0.0, 0.0), page.corner], _boxes(prov.bbox, page)):
        chars = [c for c in page.chars if _inside(c, box)]
        if not chars:
            continue
        lines = _lines(chars)
        counts = _line_words(lines, _width(chars), words)
        if counts is not None:
            return lines, counts, shift, page
    return None


def _cut(doc: DoclingDocument, item: SectionHeaderItem, pdf: pdfium.PdfDocument, pages: dict[int, _Page | None],
         fonts: set[str]) -> int:
    found = _found_lines(item, pdf, pages)
    if found is None:
        return 0
    lines, counts, shift, page = found
    heading = [n for n, line in enumerate(lines) if _in_fonts(line, fonts)]
    first = heading[0] if heading else len(lines)
    last = first
    while last + 1 in heading:                           # the first lines in a row in the heading font
        last += 1
    words = item.text.split()
    starts = [sum(counts[:n]) for n in range(len(lines) + 1)]
    page_no = item.prov[0].page_no
    if first > 0:                                        # the lines above the heading
        text = " ".join(words[:starts[first]])
        doc.insert_text(sibling=item, label=DocItemLabel.TEXT, text=text, orig=text, after=False,
                        prov=_prov(page_no, lines[:first], shift, text))
    after = last + 1 if heading else first
    if after < len(lines):                               # the lines below it
        text = " ".join(words[starts[after]:])
        doc.insert_text(sibling=item, label=DocItemLabel.TEXT, text=text, orig=text,
                        prov=_prov(page_no, lines[after:], shift, text))
    text = " ".join(words[starts[first]:starts[last + 1]]) if heading else ""
    item.text, item.orig = text, text                    # an empty heading is left out by to_blocks()
    if heading:
        item.prov = [_prov(page_no, lines[first:last + 1], shift, text)]
    return 1


def _in_fonts(line: list[_Char], fonts: set[str]) -> bool:
    letters = [c for c in line if c.text.isalpha()]
    return bool(letters) and sum(c.font in fonts for c in letters) >= _LINE_SHARE * len(letters)


def _prov(page_no: int, lines: list[list[_Char]], shift: tuple[float, float], text: str) -> ProvenanceItem:
    """Docling's place for these lines: its box, measured as Docling measures (from the visible page's corner)."""
    chars = [c for line in lines for c in line]
    dx, dy = shift
    box = BoundingBox(l=min(c.left for c in chars) - dx, r=max(c.right for c in chars) - dx,
                      t=max(c.y + c.height / 2 for c in chars) - dy, b=min(c.y - c.height / 2 for c in chars) - dy,
                      coord_origin=CoordOrigin.BOTTOMLEFT)
    return ProvenanceItem(page_no=page_no, bbox=box, charspan=(0, len(text)))
