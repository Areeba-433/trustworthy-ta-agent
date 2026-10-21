"""remove_chapter_tabs(): the chapter tab on the edge of a book page is not course content.

Many textbooks print a tab on the outer edge of their pages: the chapter's number and title, turned on its side
("9 INHERITANCE"). Docling does not know it is decoration, so it turns up as a paragraph of its own, as an extra
last column of a table printed next to it, at the end of the cells of a table's last column, or at the end of a
code listing. In our OOP book that is 462 pages.

pdfium finds the tab: its letters are rotated and stand in the outer 15% of the page. The chapter's number or
letter is upright, just above or below them (on the OOP book's pages about 5 to 18 points). Then, in Docling's
result:
- an item made only of the tab's letters moves to the furniture layer (to_blocks() skips it, like page numbers);
- a table column made only of them is removed;
- cells of a table's last column that end with them, after their own text, lose them;
- a code listing that ends with them loses them.

Words are compared by their letters, not by their spelling: the tab is set in small capitals, and pdfium reads
"LOOPS AND DECISIONS" as "L D OOPS AND ECISIONS".
"""
import logging
from collections import Counter
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from docling_core.types.doc import ContentLayer, DocItemLabel, DoclingDocument, TableData, TableItem

logger = logging.getLogger(__name__)

_EDGE = 0.15            # the outer part of the page where a tab stands, as a share of the page's width
_MIN_ROTATED = 3        # fewer rotated letters than this is not a tab (a stray symbol)
_NUMBER_SIDE = 15.0     # points: how far beside the rotated letters the chapter's number can stand
_NUMBER_GAP = 25.0      # points: how far above or below them


def remove_chapter_tabs(doc: DoclingDocument, path: Path) -> int:
    """Take the chapter tabs out of Docling's result for the PDF at `path`; changes `doc` in place.
    Returns how many items were changed, for the log and the check scripts."""
    tabs = chapter_tabs(path)
    if not tabs:
        return 0
    changed = 0
    for item in doc.texts:
        tab = tabs.get(item.prov[0].page_no) if item.prov else None
        if tab is None or item.content_layer != ContentLayer.BODY:
            continue
        if item.label == DocItemLabel.CODE:
            kept = _without_tab_at_end(item.text, tab)
            if kept != item.text:
                item.text = kept
                changed += 1
        elif _only_tab(item.text, tab):
            item.content_layer = ContentLayer.FURNITURE
            changed += 1
    for table in doc.tables:
        tab = tabs.get(table.prov[0].page_no) if table.prov else None
        if tab is not None:
            changed += _remove_tab_columns(table, tab)
            changed += _remove_tab_words_in_cells(table, tab)
    logger.info("chapter tabs on %d pages, %d items changed", len(tabs), changed)
    return changed


def chapter_tabs(path: Path) -> dict[int, Counter]:
    """{page number: the letters of its chapter tab} for every page that has one."""
    tabs: dict[int, Counter] = {}
    pdf = pdfium.PdfDocument(str(path))
    try:
        for index in range(len(pdf)):
            page = pdf[index]
            textpage = page.get_textpage()
            try:
                letters = _tab_letters(page, textpage)
            finally:
                textpage.close()
                page.close()
            if letters:
                tabs[index + 1] = letters
    finally:
        pdf.close()
    return tabs


def _tab_letters(page: pdfium.PdfPage, textpage: pdfium.PdfTextPage) -> Counter:
    left, _, right, _ = page.get_cropbox()
    edge = _EDGE * (right - left)
    rotated, upright = [], []
    for i in range(textpage.count_chars()):
        box = textpage.get_charbox(i, loose=True)
        if left + edge <= box[0] and box[2] <= right - edge:
            continue                                                    # the page's own text column
        angle = pdfium_c.FPDFText_GetCharAngle(textpage.raw, i)         # radians; -1 when pdfium cannot tell
        (rotated if 0.01 < angle < 6.27 else upright).append((i, box))
    if len(rotated) < _MIN_ROTATED:
        return Counter()
    l, r = min(box[0] for _, box in rotated), max(box[2] for _, box in rotated)
    b, t = min(box[1] for _, box in rotated), max(box[3] for _, box in rotated)

    def is_number(box: tuple[float, float, float, float]) -> bool:
        x, y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        beside = l - _NUMBER_SIDE <= x <= r + _NUMBER_SIDE
        return beside and (t <= y <= t + _NUMBER_GAP or b - _NUMBER_GAP <= y <= b)

    chars = [i for i, _ in rotated] + [i for i, box in upright if is_number(box)]
    return _letters("".join(textpage.get_text_range(i, 1) for i in chars))


def _letters(text: str) -> Counter:
    return Counter(ch for ch in text if not ch.isspace())


def _looks_like_tab(words: list[str]) -> bool:
    """A tab is printed in capitals and numbers; course text and code are not only that."""
    return bool(words) and all(word == word.upper() for word in words)


def _only_tab(text: str, tab: Counter) -> bool:
    words = text.split()
    return _looks_like_tab(words) and not (_letters(text) - tab)


def _without_tab_at_end(text: str, tab: Counter) -> str:
    """The listing without the tab's words at its end, if they are there: at least half of the tab's letters."""
    words = text.split()
    cut = len(words)
    while cut and _looks_like_tab(words[cut - 1:]) and not (_letters(" ".join(words[cut - 1:])) - tab):
        cut -= 1
    found = _letters(" ".join(words[cut:]))
    if cut == len(words) or sum(found.values()) * 2 < sum(tab.values()):
        return text
    return " ".join(words[:cut])


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
