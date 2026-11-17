"""A book's structure: which heading sits under which, chapter names, and code listings cut by a page break.

Docling gives every heading of a PDF the same level, so to_blocks() put all sections side by side under the book's
title: "Derived Class Constructors" was not under "Inheritance", and no chunk's heading path said which chapter it
came from. A book shows its structure in two ways that Docling does not use:

- size: the bigger the part, the bigger its heading. In the OOP book a chapter's title is 19.2 points tall, a
  section's 15.4, then 13.4 and 11.5 (the height of its capital letters, read from the PDF). set_heading_levels()
  gives each heading its level from its size.
- bookmarks: the PDF's own outline says where each chapter starts ("9 Inheritance", page 397). name_chapters()
  calls that chapter's heading "Chapter 9: Inheritance", so every chunk of the chapter carries the number a student
  asks about.

Two smaller fixes: list_headings() turns the "headings" that are really bullet points (book page 43) into list items,
and join_page_listings() makes one block of a code listing that a page break cut in two (278 in the OOP book).

The first three run on Docling's result before to_blocks(), which builds the heading paths from the levels;
join_page_listings() runs on the blocks, after order_by_position().
"""
import logging
import re
import statistics
import unicodedata
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

import pypdfium2 as pdfium
from docling_core.types.doc import ContentLayer, DocItemLabel, DoclingDocument, SectionHeaderItem, TextItem

from app.ingestion.contract import Block
from app.ingestion.pdf_code import _Page
from app.ingestion.pdf_headings import _found_lines

logger = logging.getLogger(__name__)

_SAME_SIZE = 0.5        # points: headings whose letters are this close in height are the same size
_CHAPTER_STEP = 2.5     # points: a heading this much taller than the biggest common size is a chapter's (level 1)
_COMMON_SHARE = 0.1     # a size is common when it has this share of the headings of the most used size ...
_COMMON_MIN = 3         # ... and at least this many headings
_BULLET = re.compile(r"^[·•▪◦‣●○■□►]\s*(\S.*)$")
_CHAPTER = re.compile(r"^(\d{1,3}|[A-Z])\s+(\S.*?)\s*$")            # a top-level bookmark: "9 Inheritance"
_LABEL = re.compile(r"(?i)^(?:chapter|appendix)(?:\s+(\d{1,3}|[A-Z]))?$")   # "CHAPTER 9", printed on its first page
_NEW_FILE = re.compile(r"^\s*(?://|#|/\*|--)\s*[\w.-]+\.\w{1,4}\b")   # "// parts.cpp": a listing starts with its name


# ======================================================================== bullet points Docling took for headings

def list_headings(doc: DoclingDocument) -> int:
    """Make a list item of each heading that starts with a bullet ("· Physical objects"); changes `doc` in place.
    Returns how many there were."""
    found = 0
    for item in list(doc.texts):
        if not isinstance(item, SectionHeaderItem) or item.content_layer != ContentLayer.BODY:
            continue
        match = _BULLET.match(item.text.strip())
        if match is None:
            continue
        group = doc.insert_list_group(sibling=item, after=False)
        doc.add_list_item(match[1], parent=group, prov=item.prov[0].model_copy() if item.prov else None)
        item.content_layer = ContentLayer.FURNITURE          # kept in the document, out of the blocks
        found += 1
    logger.info("%d bullet points Docling read as headings made list items", found)
    return found


# ======================================================================== heading levels from heading sizes

def set_heading_levels(doc: DoclingDocument, path: Path) -> int:
    """Give each heading of Docling's result for the PDF at `path` its level, from the height of its letters:
    level 1 for a chapter, 2 for the biggest common size, 3 for the next one, and so on. Changes `doc` in place.
    Returns how many headings were measured; with none, nothing changes."""
    headings = _headings(doc)
    if not headings:
        return 0
    pages: dict[int, _Page | None] = {}
    pdf = pdfium.PdfDocument(str(path))
    try:
        sizes = {item.self_ref: _size(item, pdf, pages) for item in headings}
    finally:
        pdf.close()
    common = _common_sizes([size for size in sizes.values() if size is not None])
    if not common:
        return 0
    for item in headings:
        item.level = _level(sizes[item.self_ref], common)
    measured = sum(size is not None for size in sizes.values())
    logger.info("heading levels from %d heading sizes (common sizes %s); %d headings not measured",
                measured, common, len(headings) - measured)
    return measured


def _headings(doc: DoclingDocument) -> list[SectionHeaderItem]:
    return [item for item in doc.texts if isinstance(item, SectionHeaderItem)
            and item.content_layer == ContentLayer.BODY and item.text.strip()]


def _size(item: SectionHeaderItem, pdf: pdfium.PdfDocument, pages: dict[int, _Page | None]) -> float | None:
    """The middle height of the heading's capital letters (of all its letters if it has no capital), in points;
    None when the PDF does not have exactly Docling's words in the heading's box."""
    found = _found_lines(item, pdf, pages) if len(item.prov) == 1 else None
    if found is None:
        return None
    letters = [c for line in found[0] for c in line if c.text.isalpha()]
    heights = [c.height for c in letters if c.text.isupper()] or [c.height for c in letters]
    return round(statistics.median(heights), 1) if heights else None


def _common_sizes(sizes: list[float]) -> list[float]:
    """The sizes many headings share, biggest first. Sizes within _SAME_SIZE of a more used one count as that one."""
    groups: dict[float, int] = {}
    for size, n in Counter(sizes).most_common():
        near = next((group for group in groups if abs(group - size) <= _SAME_SIZE), size)
        groups[near] = groups.get(near, 0) + n
    most = max(groups.values(), default=0)
    return sorted((size for size, n in groups.items() if n >= max(_COMMON_MIN, _COMMON_SHARE * most)), reverse=True)


def _level(size: float | None, common: list[float]) -> int:
    if size is None:
        return len(common) + 2           # not measured: the lowest level, so it cuts no section short
    if size >= common[0] + _CHAPTER_STEP:
        return 1                         # clearly bigger than every common size: a chapter, or the book's title
    return 2 + sum(size < c - _SAME_SIZE for c in common)


# ======================================================================== chapter names from the bookmarks

def name_chapters(doc: DoclingDocument, path: Path) -> int:
    """Call each chapter's heading after the PDF's top-level bookmark ("9 Inheritance" -> "Chapter 9: Inheritance",
    "A ASCII Chart" -> "Appendix A: ASCII Chart") and make it level 1; changes `doc` in place. Returns how many
    chapters were named.

    On the chapter's first page (where the bookmark points):
    - the heading with the bookmark's words is the chapter's heading. Where Docling made a paragraph of it, it
      becomes a heading; where Docling missed it, a heading is put before the page's first item.
    - the printed label ("CHAPTER 9", "APPENDIX") repeats the chapter's heading: the chapter's own text starts
      after it, below the "IN THIS CHAPTER" list, and must not be part of that list. A paragraph that is only the
      chapter's number ("9", "C", printed big) is left out.
    """
    pdf = pdfium.PdfDocument(str(path))
    try:
        chapters = _chapters(pdf)
    finally:
        pdf.close()
    if not chapters:
        return 0
    on_page: dict[int, list[TextItem]] = {}
    for item, _ in doc.iterate_items(included_content_layers={ContentLayer.BODY}):
        if isinstance(item, TextItem) and item.prov and item.text.strip():
            on_page.setdefault(item.prov[0].page_no, []).append(item)
    named = 0
    for page_no, (number, title) in chapters.items():
        items = on_page.get(page_no, [])
        name = f"{'Chapter' if number.isdigit() else 'Appendix'} {number}: {title}"
        heading = next((item for item in items if _words(item.text) == _words(title) and _convertible(item, doc)),
                       None)
        if heading is not None:
            _make_heading(doc, heading, name)
        else:
            first = next((item for item in items if _convertible(item, doc)), None)
            if first is None:
                continue
            doc.insert_heading(sibling=first, text=name, level=1, prov=first.prov[0].model_copy(), after=False)
        for item in items:
            label = _LABEL.match(item.text.strip())
            if label and (label[1] is None or label[1].upper() == number.upper()) and _convertible(item, doc):
                _make_heading(doc, item, name)
            elif item.text.strip().upper() == number.upper() and not isinstance(item, SectionHeaderItem):
                item.content_layer = ContentLayer.FURNITURE
        named += 1
    logger.info("%d chapters named from the PDF's bookmarks", named)
    return named


def _chapters(pdf: pdfium.PdfDocument) -> dict[int, tuple[str, str]]:
    """{page number: (chapter number or appendix letter, title)} of the top-level bookmarks named like chapters."""
    chapters: dict[int, tuple[str, str]] = {}
    for bookmark in pdf.get_toc():
        dest = bookmark.get_dest()
        match = _CHAPTER.match(bookmark.get_title() or "")
        if bookmark.level == 0 and match and dest is not None and dest.get_index() is not None:
            chapters.setdefault(dest.get_index() + 1, (match[1], match[2]))
    return chapters


def _words(text: str) -> str:
    """The letters and digits, in lower case: "C++ Programming Basics" and "C++  programming basics" are the same."""
    return "".join(c for c in unicodedata.normalize("NFKC", text).casefold() if c.isalnum())


def _convertible(item: TextItem, doc: DoclingDocument) -> bool:
    """A heading, or a paragraph standing on its own (not inside a list, a table or a figure)."""
    if isinstance(item, SectionHeaderItem):
        return True
    return item.label in (DocItemLabel.TEXT, DocItemLabel.PARAGRAPH) and item.parent is not None \
        and item.parent.cref == doc.body.self_ref


def _make_heading(doc: DoclingDocument, item: TextItem, name: str) -> None:
    if isinstance(item, SectionHeaderItem):
        item.text, item.level = name, 1
        return
    doc.insert_heading(sibling=item, text=name, orig=item.text, level=1, prov=item.prov[0].model_copy(), after=False)
    item.content_layer = ContentLayer.FURNITURE


# ======================================================================== listings cut by a page break

def join_page_listings(blocks: Sequence[Block]) -> list[Block]:
    """The same blocks, with each code listing that a page break cut in two made one block again; seq numbered
    again when anything was joined. The joined block keeps the first part's place and gets page_end, and
    extra["joined"] lists Docling's ids of the parts added to it.

    A code block that ends a page and one that starts the next page, in the same section, are one listing, unless
    the second starts with a comment naming its file ("// parts.cpp"): in the OOP book that held for 278 of 279.
    """
    out: list[Block] = []
    for block in blocks:
        before = out[-1] if out else None
        if before is not None and _continues(before, block):
            out[-1] = before.model_copy(update={
                "text": before.text + "\n" + block.text,
                "loc": before.loc.model_copy(update={"page_end": block.loc.page_end or block.loc.page}),
                "extra": {**before.extra, "joined": [*before.extra.get("joined", []), block.extra.get("ref")]},
            })
        else:
            out.append(block)
    if len(out) == len(blocks):
        return list(blocks)
    logger.info("%d code listings cut by a page break joined", len(blocks) - len(out))
    return [block.model_copy(update={"seq": n}) for n, block in enumerate(out)]


def _continues(before: Block, block: Block) -> bool:
    end = before.loc.page_end or before.loc.page
    return (before.kind == block.kind == "code" and end is not None and block.loc.page == end + 1
            and before.heading_path == block.heading_path and before.figure_id == block.figure_id
            and not _NEW_FILE.match(block.text))
