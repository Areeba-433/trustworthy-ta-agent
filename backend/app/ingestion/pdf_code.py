"""restore_code_lines(): PDF code listings get their line breaks and indentation back.

Docling finds code listings (label `code`) but builds their text like a paragraph's: it strips every line and joins
the lines with single spaces, so

    struct Node {
        int value;

comes back as "struct Node { int value;". The PDF itself still says where every character sits. This module reads
the characters inside each listing's box from the PDF text layer and puts each one back on its line (by its height
on the page) and in its column (by its distance from the listing's left edge).

It never changes what Docling says is in a listing, only how it is laid out: the rebuilt text must have Docling's
words in Docling's order, or Docling's text is kept. Two things make that check pass on real books:
- where the box is: Docling measures from the corner of the visible page, pdfium from the PDF's own origin. They
  are the same point in most PDFs, but one of our books has its pages start at (54, 55), so both are tried.
- Docling's boxes can overlap: a piece of a line inside this box that Docling gave to another item is left out.
- Docling's box can miss part of its own item: when it merges two overlapping regions it keeps one region's box.
  Then the whole page is searched, and the pieces closest to the box are taken.

Docling's code box often holds sentences too ("Here's the output:", "is better than"). Books print code in a
fixed-width font, where every letter is equally wide, and sentences in an ordinary one; the PDF names each
character's font, and the letters' widths tell which fonts are fixed-width. So a line of the listing in an ordinary
font leaves it as a paragraph of its own, in its place. A line that starts in the code font and ends in a note
("c1=0    <- counts are initially 0") stays code. Nothing is split unless the listing has characters in a font
known to be fixed-width: some books print code in an ordinary font, and a font with few letters cannot be told.
"""
import ctypes
import logging
import math
import statistics
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from docling_core.types.doc import BoundingBox, CoordOrigin, DocItem, DocItemLabel, DoclingDocument

from app.ingestion.cleaning.common import clean_text, detect_lang
from app.ingestion.contract import Block

logger = logging.getLogger(__name__)

_MARGIN = 2.0          # points: a character belongs to a box when its centre is inside the box plus this margin
_MAX_EMPTY_LINES = 2   # a bigger gap is where Docling's box skipped another item's lines, not real empty lines
_PIECE_GAP = 1.5       # columns: a gap this wide (two spaces or more) splits a line into pieces
_WORD_GAP = 0.3        # columns: a gap this wide is a space between two words
_FONT_PAGES = 60       # pages sampled, spread over the file, to tell the fixed-width fonts from the others
_FONT_LETTERS = 40     # letters a font needs on those pages before it is called either
_SAME_WIDTH = 0.15     # points: two letters this close in width are equally wide
# Docling turns these into plain ASCII in all text; we do the same so both versions can be compared word by word.
# In code they are wrong anyway: a student who copies “hello” into a compiler gets an error.
_ASCII = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "⁄": "/", "\x02": "-",
                        "—": "-", "–": "-"})               # long dashes: book page 168, "variable—dining—of"
_LIGATURES = range(0xFB00, 0xFB07)                      # ﬀ ﬁ ﬂ ﬃ ﬄ ﬅ ﬆ
_PRIVATE = range(0xE000, 0xF900)    # a font's own drawing pieces (the OOP book's long arrows): no character at all


@dataclass(frozen=True)
class _Char:
    text: str
    left: float        # where the character starts, in points
    right: float       # where the next character would start
    y: float           # vertical centre: every character on one line shares it
    height: float
    fixed: bool | None = None   # its font is fixed-width (True), ordinary (False), or not known (None)


@dataclass(frozen=True)
class _Page:
    height: float
    corner: tuple[float, float]     # bottom-left corner of the visible page (the crop box), in PDF points
    chars: list[_Char]


def restore_code_lines(blocks: Sequence[Block], doc: DoclingDocument, path: Path) -> list[Block]:
    """The same blocks, with each code block's text rebuilt from the PDF, and the sentences inside a listing taken
    out as paragraphs. Rebuilt code blocks get extra["lines_from"] = "pdf_text" and the paragraphs
    extra["split_from"] = "code", so a check script can count them; all keep Docling's id in extra["ref"]."""
    listings = {item.self_ref: item for item in doc.texts if item.label == DocItemLabel.CODE}
    if not any(b.kind == "code" and b.extra.get("ref") in listings for b in blocks):
        return list(blocks)                              # nothing to rebuild: don't even open the PDF
    pages: dict[int, _Page | None] = {}                  # each page's characters, read once
    out: list[Block] = []
    rebuilt = split = total = 0
    pdf = pdfium.PdfDocument(str(path))
    try:
        fonts = _font_kinds(pdf)
        for block in blocks:
            item = listings.get(block.extra.get("ref")) if block.kind == "code" else None
            found = _found(item, block.text, pdf, pages, fonts) if item is not None else None
            total += item is not None
            if found is None:
                if item is not None:
                    logger.debug("kept Docling's text for %s: the PDF does not have its words there", item.self_ref)
                out.append(block)
                continue
            parts = _parts(found)
            if len(parts) == 1:                          # the usual case: the whole box is code
                text = _ascii(_layout(found))
                if text != block.text:
                    block = block.model_copy(update={"text": text, "extra": {**block.extra, "lines_from": "pdf_text"}})
                    rebuilt += 1
                out.append(block)
                continue
            split += 1
            rebuilt += 1
            out += [_part_block(block, kind, chars, found) for kind, chars in parts]
    finally:
        pdf.close()
    logger.info("rebuilt %d of %d code listings from the PDF text layer, %d with sentences taken out",
                rebuilt, total, split)
    return [b.model_copy(update={"seq": n}) for n, b in enumerate(out)] if split else out


def _found(item: DocItem, docling_text: str, pdf: pdfium.PdfDocument, pages: dict[int, _Page | None],
           fonts: dict[str, bool] | None = None) -> list[_Char] | None:
    """The PDF's characters of Docling's listing, or None when the PDF does not have Docling's words in its box."""
    if len(item.prov) != 1:                              # Docling gives a code item one box, on one page
        return None
    prov = item.prov[0]
    if prov.page_no not in pages:
        pages[prov.page_no] = _read_page(pdf, prov.page_no, fonts) if 1 <= prov.page_no <= len(pdf) else None
    page = pages[prov.page_no]
    if page is None:
        return None
    wanted = _ascii(docling_text).split()
    if not wanted:
        return None
    boxes = _boxes(prov.bbox, page)
    for box in boxes:                                    # the usual case: all of Docling's words are in its box
        found = _matching(_pieces([c for c in page.chars if _inside(c, box)]), wanted)
        if found:
            return found[1]
    everywhere = _pieces(page.chars)                     # the box missed part of the item: look on the whole page
    choices = [_matching(everywhere, wanted, [_distance(piece, box) for piece, _ in everywhere]) for box in boxes]
    best = min((choice for choice in choices if choice), default=None, key=lambda choice: choice[0])
    return best[1] if best else None


def _rebuild(item: DocItem, docling_text: str, pdf: pdfium.PdfDocument, pages: dict[int, _Page | None]) -> str:
    """The listing laid out from the PDF, or "" when the PDF does not have Docling's words in its box."""
    found = _found(item, docling_text, pdf, pages)
    return _ascii(_layout(found)) if found else ""


def _font_kinds(pdf: pdfium.PdfDocument) -> dict[str, bool]:
    """{font name: True if it is fixed-width} for the fonts with enough letters on pages spread over the file.
    In a fixed-width font every letter of a line is equally wide; in an ordinary one "i" and "m" are not."""
    same, letters = Counter(), Counter()
    count = len(pdf)
    for index in sorted({n * count // _FONT_PAGES for n in range(min(count, _FONT_PAGES))}):
        page = pdf[index]
        textpage = page.get_textpage()
        try:
            runs: dict[tuple[str, int], list[float]] = defaultdict(list)     # (font, line) -> letter widths
            for i in range(textpage.count_chars()):
                if textpage.get_text_range(i, 1).isalpha():
                    left, bottom, right, top = textpage.get_charbox(i, loose=True)
                    runs[(_font_name(textpage, i), round((bottom + top) / 2))].append(right - left)
        finally:
            textpage.close()
            page.close()
        for (font, _), widths in runs.items():
            usual = Counter(round(w, 1) for w in widths).most_common(1)[0][0]
            same[font] += sum(abs(w - usual) <= _SAME_WIDTH for w in widths)
            letters[font] += len(widths)
    return {font: same[font] >= 0.9 * n for font, n in letters.items() if n >= _FONT_LETTERS}


def _font_name(textpage: pdfium.PdfTextPage, index: int) -> str:
    name = ctypes.create_string_buffer(128)
    flags = ctypes.c_int()
    if not pdfium_c.FPDFText_GetFontInfo(textpage.raw, index, name, len(name), ctypes.byref(flags)):
        return ""
    return name.value.decode("latin-1")


def _read_page(pdf: pdfium.PdfDocument, page_no: int, fonts: dict[str, bool] | None = None) -> _Page:
    page = pdf[page_no - 1]
    textpage = page.get_textpage()
    try:
        chars = []
        for i in range(textpage.count_chars()):
            text = textpage.get_text_range(i, 1)
            if text and not text.isspace():              # spaces are rebuilt from the positions
                # "loose" box: the character's full slot, so in a monospace font every box is exactly one column wide
                left, bottom, right, top = textpage.get_charbox(i, loose=True)
                fixed = fonts.get(_font_name(textpage, i)) if fonts else None
                chars.append(_Char(text, left, right, (bottom + top) / 2, top - bottom, fixed))
        left, bottom, _, _ = page.get_cropbox()
        return _Page(page.get_height(), (left, bottom), chars)
    finally:
        textpage.close()
        page.close()


def _parts(chars: list[_Char]) -> list[tuple[str, list[_Char]]]:
    """The listing as ("code", characters) and ("sentence", characters) parts, top to bottom: each line in an
    ordinary font is a sentence. Only a listing with characters in a font known to be fixed-width is split."""
    if not any(c.fixed for c in chars):                  # no character in a font known to be fixed-width
        return [("code", chars)]
    lines = _lines(chars)
    kinds = [_line_kind(line, _width(chars)) for line in lines]
    if "sentence" not in kinds:
        return [("code", chars)]
    parts: list[tuple[str, list[_Char]]] = []
    for kind, line in zip(kinds, lines):
        if parts and parts[-1][0] == kind:
            parts[-1][1].extend(line)
        else:
            parts.append((kind, list(line)))
    return parts


def _line_kind(line: list[_Char], width: float) -> str:
    """ "code" or "sentence". A line in the code font, or starting with a piece of it before a gap (a note beside a
    program's output), is code; a line mostly in an ordinary font is a sentence; a line of unknown fonts stays code."""
    fixed = sum(c.fixed is True for c in line)
    ordinary = sum(c.fixed is False for c in line)
    first = 1                                            # characters in the line's first piece
    while first < len(line) and line[first].left - line[first - 1].right <= width * _PIECE_GAP:
        first += 1
    if fixed + ordinary == 0 or (all(c.fixed for c in line[:first]) and first < len(line)):
        return "code"
    return "sentence" if ordinary > fixed else "code"


def _part_block(block: Block, kind: str, chars: list[_Char], listing: list[_Char]) -> Block:
    if kind == "code":                                   # columns counted from the listing's own left edge
        left = min((c.left for c in listing if c.fixed is not False), default=min(c.left for c in listing))
        text = _ascii(_layout(chars, left))
        return block.model_copy(update={"text": text, "extra": {**block.extra, "lines_from": "pdf_text"}})
    width = _width(listing)
    text = clean_text("\n".join(" ".join(_words(line, width)) for line in _lines(chars)))
    return block.model_copy(update={"kind": "paragraph", "text": text, "lang": detect_lang(text),
                                    "extra": {**block.extra, "split_from": "code"}})


def _boxes(bbox: BoundingBox, page: _Page) -> list[BoundingBox]:
    """Where Docling's box can be in pdfium's coordinates: as given (Docling's pypdfium2 reader), or measured from
    the visible page's corner (Docling's default reader, docling-parse). One box when the corner is (0, 0)."""
    box = bbox.to_bottom_left_origin(page.height)
    dx, dy = page.corner
    if (dx, dy) == (0, 0):
        return [box]
    return [box, BoundingBox(l=box.l + dx, r=box.r + dx, t=box.t + dy, b=box.b + dy,
                             coord_origin=CoordOrigin.BOTTOMLEFT)]


def _inside(c: _Char, box: BoundingBox) -> bool:
    x = (c.left + c.right) / 2
    return box.l - _MARGIN <= x <= box.r + _MARGIN and box.b - _MARGIN <= c.y <= box.t + _MARGIN


def _distance(piece: list[_Char], box: BoundingBox) -> float:
    """How far a piece of a line is from the box, in points: 0 when it is inside."""
    left, right, y = piece[0].left, piece[-1].right, piece[0].y
    across = max(0.0, box.l - right, left - box.r)
    down = max(0.0, box.b - y, y - box.t)
    return across + down


def _pieces(chars: list[_Char]) -> list[tuple[list[_Char], list[str]]]:
    """The characters as pieces of lines, each with its words. A piece ends at a gap of two spaces or more.
    Docling builds its items from whole text cells, which end at such gaps, so a piece is in a listing entirely or
    not at all."""
    if not chars:
        return []
    width = _width(chars)
    pieces: list[list[_Char]] = []
    for line in _lines(chars):
        pieces.append([line[0]])
        for previous, c in zip(line, line[1:]):
            if c.left - previous.right > width * _PIECE_GAP:
                pieces.append([c])
            else:
                pieces[-1].append(c)
    return [(piece, _words(piece, width)) for piece in pieces]


def _words(piece: list[_Char], width: float) -> list[str]:
    words = [piece[0].text]
    for previous, c in zip(piece, piece[1:]):
        if c.left - previous.right > width * _WORD_GAP:
            words.append(c.text)
        else:
            words[-1] += c.text
    return [word for word in map(_ascii, words) if word]          # a word of a font's drawing pieces is no word


def _matching(pieces: list[tuple[list[_Char], list[str]]], wanted: list[str],
              distances: list[float] | None = None) -> tuple[float, list[_Char]] | None:
    """The pieces whose words, one piece after another, are exactly Docling's words, as (cost, their characters);
    None if no choice of pieces gives them. Pieces that Docling gave to another item are left out. When several
    choices give the words (the same line can appear twice on a page), the cost decides: the sum of the chosen
    pieces' distances from Docling's box. Without distances every choice costs 0 and the earliest one is taken.

    Dynamic programming: cost[i][j] is the cheapest way for pieces i, i+1, ... to give exactly wanted[j:]
    (infinite: impossible). It is filled from the end, then read from the start, following the cheapest choice."""
    n, m = len(pieces), len(wanted)
    distances = distances or [0.0] * n
    cost = [[math.inf] * (m + 1) for _ in range(n + 1)]
    take = [[False] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        cost[i][m] = 0.0                                     # nothing left to find: done, for free
    for i in range(n - 1, -1, -1):
        words = pieces[i][1]
        for j in range(m - 1, -1, -1):
            leave = cost[i + 1][j]                           # leave piece i to another item
            took = distances[i] + cost[i + 1][j + len(words)] if wanted[j:j + len(words)] == words else math.inf
            take[i][j] = took <= leave and took < math.inf   # on a tie, take: the earliest choice wins
            cost[i][j] = min(took, leave)
    if cost[0][0] == math.inf:
        return None
    chosen, j = [], 0
    for i, (piece, words) in enumerate(pieces):
        if j < m and take[i][j]:
            chosen += piece
            j += len(words)
    return cost[0][0], chosen


def _layout(chars: list[_Char], left: float | None = None) -> str:
    """Characters back into lines (by height on the page) and columns (by distance from the left edge)."""
    if not chars:
        return ""
    width = _width(chars)                                                 # one column
    left = min(c.left for c in chars) if left is None else left           # column 0
    lines = _lines(chars)
    gaps = [above[0].y - below[0].y for above, below in zip(lines, lines[1:])]
    # the usual distance between two lines; never more than 1.5 character heights, or two lines with an empty
    # line between them would look like normal spacing
    pitch = min(statistics.median(gaps), 1.5 * statistics.median(c.height for c in chars)) if gaps else 0.0
    out: list[str] = []
    for n, line in enumerate(lines):
        if n and pitch:
            empty = round(gaps[n - 1] / pitch) - 1                        # a double distance was an empty line
            out += [""] * max(0, min(empty, _MAX_EMPTY_LINES))
        out.append(_line_text(line, left, width))
    return "\n".join(out)


def _width(chars: list[_Char]) -> float:
    return statistics.median(c.right - c.left for c in chars) or 1.0


def _lines(chars: list[_Char]) -> list[list[_Char]]:
    lines: list[list[_Char]] = []
    for c in sorted(chars, key=lambda c: -c.y):                           # top of the page first
        if lines and abs(lines[-1][0].y - c.y) <= c.height / 2:
            lines[-1].append(c)
        else:
            lines.append([c])
    return [sorted(line, key=lambda c: c.left) for line in lines]         # left to right


def _line_text(line: list[_Char], left: float, width: float) -> str:
    """One line. In code (a monospace font: every letter equally wide) each word starts in its column, so
    indentation and lined-up comments come back. A sentence that Docling put in the listing (Times-Roman: letters
    of different widths) has no columns: its words get single spaces. Inside a word the letters simply follow each
    other, or a wide letter would push the next one into another column and look like a space ("An d"). Each piece
    of such a line still starts in its column: program output with a note beside it keeps the gap before the note
    ("c1=0        <- counts are initially 0", book page 348)."""
    widths = [c.right - c.left for c in line]
    if max(widths) - min(widths) > 0.1 * width:
        pieces = [[line[0]]]
        for previous, c in zip(line, line[1:]):
            if c.left - previous.right > width * _PIECE_GAP:
                pieces.append([c])
            else:
                pieces[-1].append(c)
        text = ""
        for piece in pieces:
            column = max(0, round((piece[0].left - left) / width))
            text += " " * max(1 if text else 0, column - len(text)) + " ".join(_words(piece, width))
        return text
    text, previous = "", None
    for c in line:
        if previous is not None and c.left - previous.right <= width * _WORD_GAP:
            text += c.text                                                # the same word
            previous = c
            continue
        column = round((c.left - left) / width)
        if column > len(text):
            text += " " * (column - len(text))                            # indentation, or spaces inside the line
        elif previous is not None and not text.endswith(" "):
            text += " "                                                   # a narrow font: at least one space
        text += c.text
        previous = c
    return text


def _ascii(text: str) -> str:
    text = text.translate(_ASCII)
    return "".join(unicodedata.normalize("NFKC", ch) if ord(ch) in _LIGATURES else ch
                   for ch in text if ord(ch) not in _PRIVATE)
