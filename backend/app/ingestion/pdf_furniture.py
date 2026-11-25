"""remove_chapter_tabs(): the chapter tab on the edge of a book page is not course content.

Many textbooks print a tab on the outer edge of their pages: the chapter's number and title, turned on its side
("9 INHERITANCE"). Docling does not know it is decoration, so it turns up as a paragraph of its own, as an extra
last column of a table printed next to it, at the end of the cells of a table's last column, or at the end of a
code listing or a paragraph. In our OOP book that is 462 pages.

pdfium finds the tab: its letters are rotated and stand in the outer 15% of the page. The chapter's number or
letter is upright, just above or below them (on the OOP book's pages about 5 to 18 points). Then, in Docling's
result:
- an item made only of the tab's letters, standing where the tab stands, moves to the furniture layer (to_blocks()
  skips it, like page numbers);
- a table column made only of them is removed, if the table reaches the tab;
- cells of a table's last column that end with them, after their own text, lose them, if the table reaches the tab;
- a code listing or a paragraph that ends with them loses them, if its box reaches the tab: Docling merged the tab
  into it.
Where an item stands matters: capitals made of the tab's letters elsewhere on the page are content (book page 71:
the program output "A" and "B" on a page whose tab is "2 C++ PROGRAMMING BASICS").

Words are compared by their letters, not by their spelling: the tab is set in small capitals, and pdfium reads
"LOOPS AND DECISIONS" as "L D OOPS AND ECISIONS".
"""
import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from docling_core.types.doc import (BoundingBox, ContentLayer, CoordOrigin, DocItemLabel, DoclingDocument,
                                    ProvenanceItem, SectionHeaderItem, TableData, TableItem)

logger = logging.getLogger(__name__)

_EDGE = 0.15            # the outer part of the page where a tab stands, as a share of the page's width
_MIN_ROTATED = 3        # fewer rotated letters than this is not a tab (a stray symbol)
_NUMBER_SIDE = 15.0     # points: how far beside the rotated letters the chapter's number can stand
_NUMBER_GAP = 25.0      # points: how far above or below them
_NEAR = 6.0             # points: Docling's box of a piece of the tab can stick out of the tab's box this much
_ENTRY = re.compile(r"(?:^|\s)(?:\d{1,4}|[ivxlc]{1,7})$", re.IGNORECASE)   # a contents entry ends in its page: "Preface xv"
_ENTRY_SHARE = 0.6      # a page next to the contents with this share of its lines ending in a page number is contents
_MIN_ENTRIES = 3        # fewer lines than this is no contents page (a blank page's one note)
_ENTRY_WORDS = 20       # words: a longer line is no entry (DataStructures.pdf: entries up to 15, references median 20)
_RUNNING_HEAD = re.compile(r"[ivxlc]{1,7}\s+[A-Z].*")     # a front-matter running head: "xviii Preface"
_HEAD_ZONE = 0.1        # the top of the page where a running head stands, as a share of the page's height


@dataclass(frozen=True)
class Tab:
    """A page's chapter tab: its letters (the chapter's number too) and where it stands."""
    letters: Counter
    box: BoundingBox        # in points from the visible page's top-left corner, as Docling measures
    page_height: float      # the visible page's height: turns Docling's bottom-left boxes into top-left ones


def remove_chapter_tabs(doc: DoclingDocument, path: Path) -> int:
    """Take the chapter tabs out of Docling's result for the PDF at `path`; changes `doc` in place.
    Returns how many items were changed, for the log and the check scripts."""
    tabs = chapter_tabs(path)
    if not tabs:
        return 0
    changed = 0
    for item in doc.texts:
        if item.content_layer != ContentLayer.BODY:
            continue
        near = [(prov, tabs[prov.page_no]) for prov in item.prov if prov.page_no in tabs]   # its boxes on tab pages
        on_tab = len(item.prov) == 1 and bool(near) and _stands_on_tab(*near[0])
        if on_tab and item.label != DocItemLabel.CODE and _only_tab(item.text, near[0][1].letters):
            item.content_layer = ContentLayer.FURNITURE
            changed += 1
            continue
        for prov, tab in near:
            if _reaches_tab(prov, tab):
                kept = _without_tab_at_end(item.text, tab.letters)   # book page 887: "this C++ PRECEDENCE TABLE …"
                if kept != item.text:
                    item.text = kept
                    changed += 1
                break
    for table in doc.tables:
        for prov in table.prov:
            tab = tabs.get(prov.page_no)
            if tab is not None and _reaches_tab(prov, tab):
                changed += _remove_tab_columns(table, tab.letters)
                changed += _remove_tab_words_in_cells(table, tab.letters)
                break
    logger.info("chapter tabs on %d pages, %d items changed", len(tabs), changed)
    return changed


def remove_contents_and_index(doc: DoclingDocument) -> int:
    """Leave the book's contents pages and its index out: they list topics and page numbers, and a student's
    question would match their lists of topics instead of the pages that explain them. Changes `doc` in place;
    returns how many items it left out.

    Docling recognises a list of topics with page numbers as a "document index" and to_blocks() leaves that out,
    but the rest of such a page still came through: a title of the contents ("3 Loops and Decisions 75"), the book's
    running title, and on many index pages whole columns of entries as paragraphs ("containers, 415-419 data
    hiding, 218 …") or as a table. So every page with a document index is left out entirely, and so is everything
    from the index's own heading ("Index" on a page with a document index, in the last tenth of the book) to the
    end. The OOP book: 18 contents pages, 32 index pages. Docling can miss the document index on the first and the
    last contents page, whose entries then come through as list items (DataStructures.pdf pages 8 and 15, beside
    pages 9 to 14): a page next to those pages whose lines mostly end in a page number goes too."""
    index_pages = {prov.page_no for table in doc.tables if table.label == DocItemLabel.DOCUMENT_INDEX
                   for prov in table.prov}
    if not index_pages:
        return 0
    index_pages |= _entry_pages_beside(doc, index_pages)
    last = max(doc.pages, default=0)
    index_start = min((item.prov[0].page_no for item in doc.texts
                       if item.label == DocItemLabel.SECTION_HEADER and item.text.strip().casefold() == "index"
                       and item.prov and item.prov[0].page_no in index_pages
                       and item.prov[0].page_no >= 0.9 * last), default=last + 1)
    left_out = 0
    for item, _ in doc.iterate_items(traverse_pictures=True):
        pages = {prov.page_no for prov in getattr(item, "prov", [])}
        if pages and item.content_layer == ContentLayer.BODY and \
                all(page in index_pages or page >= index_start for page in pages):
            item.content_layer = ContentLayer.FURNITURE
            left_out += 1
    logger.info("contents and index: %d pages, %d items left out", len(index_pages | set(range(index_start, last + 1))),
                left_out)
    return left_out


def _entry_pages_beside(doc: DoclingDocument, pages: set[int]) -> set[int]:
    """The pages beside `pages`, and beside those in turn, made of contents or index entries: most of their lines
    end in a page number ("1.2 Mathematics Review 2", "Preface xv"). Running heads are Docling's page headers,
    already out of the body, so they do not count."""
    lines: dict[int, list[str]] = defaultdict(list)
    for item in doc.texts:
        if item.content_layer == ContentLayer.BODY and item.prov and item.text.strip():
            lines[item.prov[0].page_no].append(item.text.strip())
    found = set(pages)
    while True:
        more = {page for page in {p + step for p in found for step in (-1, 1)} - found
                if len(lines[page]) >= _MIN_ENTRIES
                and sum(_is_entry(line) for line in lines[page]) >= _ENTRY_SHARE * len(lines[page])}
        if not more:
            return found - pages
        found |= more


def _is_entry(line: str) -> bool:
    """A contents or index entry: a short line ending in a page number. A reference list's entries are longer."""
    return len(line.split()) <= _ENTRY_WORDS and _ENTRY.search(line) is not None


def remove_running_heads(doc: DoclingDocument) -> int:
    """Leave out a front-matter running head that Docling read as a heading: a heading at the top of its page that
    starts with the page's roman number ("xviii Preface", DataStructures.pdf page 19, 6% from the top). Docling
    usually marks a running head as a page header; read as a heading, it named a section of the preface. Changes
    `doc` in place; returns how many it left out."""
    found = 0
    for item in doc.texts:
        if not isinstance(item, SectionHeaderItem) or item.content_layer != ContentLayer.BODY or not item.prov:
            continue
        prov = item.prov[0]
        page = doc.pages.get(prov.page_no)
        if page is None or not _RUNNING_HEAD.fullmatch(item.text.strip()):
            continue
        if prov.bbox.to_top_left_origin(page.size.height).t <= _HEAD_ZONE * page.size.height:
            item.content_layer = ContentLayer.FURNITURE
            found += 1
    logger.info("%d running heads Docling read as headings left out", found)
    return found


def chapter_tabs(path: Path) -> dict[int, Tab]:
    """{page number: its chapter tab} for every page that has one."""
    tabs: dict[int, Tab] = {}
    pdf = pdfium.PdfDocument(str(path))
    try:
        for index in range(len(pdf)):
            page = pdf[index]
            textpage = page.get_textpage()
            try:
                tab = _find_tab(page, textpage)
            finally:
                textpage.close()
                page.close()
            if tab is not None:
                tabs[index + 1] = tab
    finally:
        pdf.close()
    return tabs


def tab_characters(page: pdfium.PdfPage, textpage: pdfium.PdfTextPage) -> set[int]:
    """The indices of the page's chapter tab characters in pdfium's text page (its turned letters and the chapter's
    number beside them); empty when the page has no tab. Code listings are matched against the PDF without them:
    a listing's box can reach the tab (book pages 537 and 543)."""
    return {i for i, _ in _tab_chars(page, textpage)}


def _find_tab(page: pdfium.PdfPage, textpage: pdfium.PdfTextPage) -> Tab | None:
    chars = _tab_chars(page, textpage)
    if not chars:
        return None
    left, bottom, _, top = page.get_cropbox()
    letters = _letters("".join(textpage.get_text_range(i, 1) for i, _ in chars))
    # pdfium measures from the PDF's origin; Docling from the visible page's top-left corner
    box = BoundingBox(l=min(c[0] for _, c in chars) - left, r=max(c[2] for _, c in chars) - left,
                      t=top - max(c[3] for _, c in chars), b=top - min(c[1] for _, c in chars),
                      coord_origin=CoordOrigin.TOPLEFT)
    return Tab(letters, box, top - bottom)


def _tab_chars(page: pdfium.PdfPage,
               textpage: pdfium.PdfTextPage) -> list[tuple[int, tuple[float, float, float, float]]]:
    """(index, loose box) of each character of the page's chapter tab: the turned letters in the page's outer
    part, and the upright number just above or below them. Empty when there are too few turned letters."""
    left, bottom, right, top = page.get_cropbox()
    edge = _EDGE * (right - left)
    rotated, upright = [], []
    for i in range(textpage.count_chars()):
        box = textpage.get_charbox(i, loose=True)
        if left + edge <= box[0] and box[2] <= right - edge:
            continue                                                    # the page's own text column
        angle = pdfium_c.FPDFText_GetCharAngle(textpage.raw, i)         # radians; -1 when pdfium cannot tell
        (rotated if 0.01 < angle < 6.27 else upright).append((i, box))
    if len(rotated) < _MIN_ROTATED:
        return []
    l, r = min(box[0] for _, box in rotated), max(box[2] for _, box in rotated)
    b, t = min(box[1] for _, box in rotated), max(box[3] for _, box in rotated)

    def is_number(box: tuple[float, float, float, float]) -> bool:
        x, y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        beside = l - _NUMBER_SIDE <= x <= r + _NUMBER_SIDE
        return beside and (t <= y <= t + _NUMBER_GAP or b - _NUMBER_GAP <= y <= b)

    return rotated + [(i, box) for i, box in upright if is_number(box)]


def _stands_on_tab(prov: ProvenanceItem, tab: Tab) -> bool:
    """Docling's item stands where the tab stands: the middle of its box is on the tab."""
    box = prov.bbox.to_top_left_origin(tab.page_height)
    x, y = (box.l + box.r) / 2, (box.t + box.b) / 2
    return tab.box.l - _NEAR <= x <= tab.box.r + _NEAR and tab.box.t - _NEAR <= y <= tab.box.b + _NEAR


def _reaches_tab(prov: ProvenanceItem, tab: Tab) -> bool:
    """Docling's box of the item overlaps the tab: the tab's words can have been merged into the item."""
    box = prov.bbox.to_top_left_origin(tab.page_height)
    return (box.l <= tab.box.r + _NEAR and tab.box.l - _NEAR <= box.r
            and box.t <= tab.box.b + _NEAR and tab.box.t - _NEAR <= box.b)


def _letters(text: str) -> Counter:
    return Counter(ch for ch in text if not ch.isspace())


def _looks_like_tab(words: list[str]) -> bool:
    """A tab is printed in capitals and numbers; course text and code are not only that."""
    return bool(words) and all(word == word.upper() for word in words)


def _only_tab(text: str, tab: Counter) -> bool:
    words = text.split()
    return _looks_like_tab(words) and not (_letters(text) - tab)


def _without_tab_at_end(text: str, tab: Counter) -> str:
    """The text without the tab's words at its end, if they are there: at least half of the tab's letters.
    What is left must have a small letter, or no letter at all: in text all in capitals, like the heading
    "MULTIPLE INHERITANCE" on a page whose tab is "9 INHERITANCE", the tab's words cannot be told from the text's
    own. A listing's separator line "////////" has no letters to mix up (book page 563)."""
    words = text.split()
    cut = len(words)
    while cut and _looks_like_tab(words[cut - 1:]) and not (_letters(" ".join(words[cut - 1:])) - tab):
        cut -= 1
    found = _letters(" ".join(words[cut:]))
    kept = " ".join(words[:cut])
    all_capitals = kept == kept.upper() and any(ch.isalpha() for ch in kept)
    if cut == len(words) or sum(found.values()) * 2 < sum(tab.values()) or all_capitals:
        return text
    return kept


def _remove_tab_columns(table: TableItem, tab: Counter) -> int:
    """Remove each column with an empty header whose other cells hold only the tab's letters. Returns how many."""
    removed = 0
    for col in reversed(range(table.data.num_cols)):
        own = [c for c in table.data.table_cells
               if c.start_col_offset_idx == col and c.end_col_offset_idx == col + 1]
        header = [c for c in own if c.column_header and c.text.strip()]
        body = " ".join(c.text for c in own if not c.column_header)
        if not header and body.strip() and _only_tab(body, tab):
            table.data = _without_column(table.data, col)
            removed += 1
    return removed


def _remove_tab_words_in_cells(table: TableItem, tab: Counter) -> int:
    """Take the tab's words off the end of the cells in the table's last column, the column next to the tab.
    Book page 925: Docling wrote "first, n, gen F" and "first, last, value STL AND". Only when the words taken hold
    at least half of the tab's letters together, and each of the tab's letters is taken once. A cell keeps at least
    its first word: a cell made only of capitals can be real data, like the letter C in an ASCII table.
    Returns how many cells changed."""
    cells = list(table.data.table_cells)
    last = [i for i, c in enumerate(cells) if c.end_col_offset_idx == table.data.num_cols and not c.column_header]
    left = tab.copy()                                     # the tab's letters not yet found
    kept: dict[int, str] = {}                             # cell -> its text without the tab's words
    for i in last:                                        # Docling lists cells row by row, top to bottom
        text = cells[i].text.rstrip()
        words = text.split()
        while len(words) > 1 and _looks_like_tab(words[-1:]) and not (_letters(words[-1]) - left):
            left -= _letters(words[-1])
            text = text[:len(text) - len(words.pop())].rstrip()
        if text != cells[i].text.rstrip():
            kept[i] = text
    found = sum(tab.values()) - sum(left.values())
    if not kept or found * 2 < sum(tab.values()):
        return 0
    for i, text in kept.items():
        cells[i] = cells[i].model_copy(update={"text": text})
    table.data = table.data.model_copy(update={"table_cells": cells})
    return len(kept)


def _without_column(data: TableData, col: int) -> TableData:
    cells = []
    for cell in data.table_cells:
        start, end = cell.start_col_offset_idx, cell.end_col_offset_idx
        if start == col and end == col + 1:
            continue                                      # the tab's own cell
        start -= start > col
        end -= end > col                                  # a cell across the removed column gets one narrower
        cells.append(cell.model_copy(update={"start_col_offset_idx": start, "end_col_offset_idx": end,
                                             "col_span": end - start}))
    return data.model_copy(update={"table_cells": cells, "num_cols": data.num_cols - 1})
