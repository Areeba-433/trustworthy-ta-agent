"""Fast path for long digital PDFs. Owner: Areeba.

Docling's layout model looks at every page as a picture, which costs about 2 seconds a page on a
laptop. Most pages of a textbook are plain text, and a digital PDF already stores that text, so:

  1. scan every page with pypdfium2 (milliseconds a page): text lines with their fonts, ruling
     lines, pictures
  2. route each page: plain pages are read here; pages Docling is needed for (two columns, tables
     without a full grid of lines, drawings, anything unusual) go to Docling, 50 at a time
  3. join both into one DoclingDocument in page order, so docs.py walks it exactly as before

Nothing on a routed page is guessed: when a page looks unusual it goes to Docling.
"""
from __future__ import annotations

import ctypes
import hashlib
import io
import logging
import os
import re
import statistics
import uuid
import warnings
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from docling_core.types.doc import DoclingDocument

logger = logging.getLogger("tta.ingestion.fast_pdf")

VERSION = 6                      # raise it whenever the fast path's output changes, so saved results are redone
BATCH_PAGES = 50                 # pages per Docling run: each finished batch is saved, so a crash loses at most one
ROUTE_ALL_ABOVE = 0.7            # when more than this share of pages needs Docling, Docling reads the whole file
MIN_PAGES = 20                   # shorter files go straight to Docling; the fast path only pays off on long ones

_BULLETS = "•●▪◦‣⁃∙·■□–—-*→▸►"
_MARKER = re.compile(r"^(?:\(?\d{1,3}[.)]|\(?[a-z][.)]|\(?[ivx]{1,4}[.)]|[" + re.escape(_BULLETS) + r"])$")
_MARKER_PREFIX = re.compile(r"^(\d{1,3}[.)]|[a-z][.)]|[" + re.escape(_BULLETS) + r"])\s+(?=\S)")
_NUMBERED = re.compile(r"^(?:chapter|part|unit|lecture|module)\s+\d+\b|^(\d+(?:\.\d+)*)\.?\s+\S", re.IGNORECASE)
_CAPTION = re.compile(r"^(?:figure|fig\.|table|tab\.|listing|algorithm|chart|diagram)\s*\d+(?:[.\-]\d+)*(?![.\-]?\d)"
                      r"(?:\s*[:.\u2013\u2014-]\s|\s+[A-Z])", re.IGNORECASE)
_SENTENCE_END = re.compile(r"[.!?:;”\"')\]]$")
_DIGITS = re.compile(r"\d+")
_PAGE_NUMBER = re.compile(r"(?:page\s*)?(?:\d{1,4}|(?=[ivxlc])c{0,3}(?:xc|xl|l?x{0,3})(?:ix|iv|v?i{0,3}))"
                          r"(?:\s*(?:of|/)\s*\d{1,4})?", re.IGNORECASE)
_NOT_WORD = re.compile(r"[^\w]+")
_ARABIC = re.compile("[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFC]")


# ---------------------------------------------------------------------------
# 1. Scan: what is on each page
# ---------------------------------------------------------------------------

@dataclass
class Frag:
    """A run of text on one line, as pdfium reports it."""
    text: str
    l: float
    b: float
    r: float
    t: float
    size: float              # the height of the font's box: font size in points times about 1.2
    bold: bool
    mono: bool
    italic: bool
    i0: int = -1             # pdfium's index of the first and last character, to tell where words break
    i1: int = -1
    space_before: bool = False
    space_after: bool = False
    font: str = ""
    x0: float = 0.0          # code: where the pen starts the first letter, and the width of one character, both
    pitch: float = 0.0       # from the PDF's own letter widths (letter shapes differ with the font the computer uses)

    @property
    def char_width(self) -> float:
        return (self.r - self.l) / max(1, len(self.text))


@dataclass
class Line:
    frags: list[Frag]
    col: int = -1            # on a two-column page: 0 left, 1 right; -1 runs across the page

    @property
    def l(self): return min(f.l for f in self.frags)
    @property
    def r(self): return max(f.r for f in self.frags)
    @property
    def t(self): return max(f.t for f in self.frags)
    @property
    def b(self): return min(f.b for f in self.frags)
    @property
    def text(self):
        out = self.frags[0].text
        for a, b in zip(self.frags, self.frags[1:]):
            if a.space_after or b.space_before:
                joint = " "
            elif a.i1 >= 0 and b.i0 == a.i1 + 1:
                joint = ""                        # one word cut in two runs, as pdfium stores it
            else:
                joint = "" if b.l - a.r < 0.15 * max(a.size, b.size) else " "   # a superscript sits on its word
            out += joint + b.text
        return out
    @property
    def size(self):
        """The size most of the line's letters have: one tall bracket or bar in a formula doesn't count."""
        if len(self.frags) == 1:
            return self.frags[0].size
        letters: dict[float, int] = {}
        for f in self.frags:
            letters[f.size] = letters.get(f.size, 0) + len(f.text)
        return max(letters, key=lambda k: (letters[k], k))
    @property
    def bold(self): return all(f.bold for f in self.frags if len(f.text) > 1) and any(f.bold for f in self.frags)
    @property
    def mono(self): return all(f.mono for f in self.frags)
    @property
    def italic(self): return all(f.italic for f in self.frags)


@dataclass
class Grid:
    """A table drawn with a full grid of lines: every row and column boundary is a drawn line."""
    xs: list[float]
    ys: list[float]          # top to bottom
    cells: list[list[str]] = field(default_factory=list)

    @property
    def box(self): return self.xs[0], self.ys[-1], self.xs[-1], self.ys[0]


@dataclass
class PageScan:
    number: int              # 1-based
    width: float
    height: float
    lines: list[Line]
    grids: list[Grid]
    pictures: list[tuple[float, float, float, float]]
    route: str = "fast"      # "fast" or "docling"
    reason: str = ""
    y0: float = 0.0          # bottom of the visible page (its crop box), as text positions count from there

    def low(self, ln: Line) -> bool:
        return ln.b - self.y0 < 0.12 * self.height

    def high(self, ln: Line) -> bool:
        return ln.t - self.y0 > 0.88 * self.height


_FIXED_PITCH, _ITALIC, _FORCE_BOLD = 0x1, 0x40, 0x40000
_MONO_NAMES = ("courier", "mono", "consol", "menlo", "code", "typewriter", "lucidaconsole", "inconsolata")


def _font(textpage, index: int) -> tuple[float, bool, bool, bool, str, int]:
    import pypdfium2.raw as pdfium_c

    box = pdfium_c.FS_RECTF()                     # many PDFs say size 1 and scale the text instead, so measure it
    pdfium_c.FPDFText_GetLooseCharBox(textpage, index, ctypes.byref(box))
    size = abs(box.top - box.bottom) or pdfium_c.FPDFText_GetFontSize(textpage, index)
    weight = pdfium_c.FPDFText_GetFontWeight(textpage, index)
    flags = ctypes.c_int(0)
    buf = ctypes.create_string_buffer(128)
    pdfium_c.FPDFText_GetFontInfo(textpage, index, buf, 128, ctypes.byref(flags))
    name = buf.value.decode("latin-1", "ignore").lower()
    # the name or the ForceBold flag; the weight alone is only a guess (Times-Roman can report 695), so it
    # counts later, and only against the weight of the page's ordinary text
    bold = any(w in name for w in ("bold", "black", "heavy", "demi")) or bool(flags.value & _FORCE_BOLD)
    mono = bool(flags.value & _FIXED_PITCH) or any(m in name for m in _MONO_NAMES)
    italic = bool(flags.value & _ITALIC) or "italic" in name or "oblique" in name
    return round(size, 1), bold, mono, italic, name, weight


def _even_spacing(textpage, start: int) -> bool:
    """Monospaced text: every letter takes the same width (i as wide as m)."""
    import pypdfium2.raw as pdfium_c

    x, y = ctypes.c_double(), ctypes.c_double()
    origins, letters = [], set()
    for i in range(start, start + 12):
        ch = pdfium_c.FPDFText_GetUnicode(textpage, i)
        if not chr(ch).isalpha() or not pdfium_c.FPDFText_GetCharOrigin(textpage, i, ctypes.byref(x), ctypes.byref(y)):
            break
        origins.append(x.value)
        letters.add(chr(ch).lower())
    steps = [b - a for a, b in zip(origins, origins[1:])]
    if len(steps) < 4 or len(letters) < 4 or min(steps) <= 0:
        return False
    return (max(steps) - min(steps)) / (sum(steps) / len(steps)) < 0.06


def _char_at(textpage, xs: list[float], y: float) -> int:
    """pdfium's index of the character at one of these spots (some spots fall between letters)."""
    import pypdfium2.raw as pdfium_c

    for x in xs:
        index = pdfium_c.FPDFText_GetCharIndexAtPos(textpage, x, y, 2, 2)
        if index >= 0:
            return index
    return -1


def _segments(obj) -> list[tuple[float, float, float, float]]:
    """The straight pieces of a drawn path, in page coordinates."""
    import pypdfium2.raw as pdfium_c

    m = pdfium_c.FS_MATRIX()
    pdfium_c.FPDFPageObj_GetMatrix(obj.raw, ctypes.byref(m))
    points, out = [], []
    x, y = ctypes.c_float(), ctypes.c_float()
    for i in range(pdfium_c.FPDFPath_CountSegments(obj.raw)):
        seg = pdfium_c.FPDFPath_GetPathSegment(obj.raw, i)
        pdfium_c.FPDFPathSegment_GetPoint(seg, ctypes.byref(x), ctypes.byref(y))
        px, py = _to_page(obj, [(m.a * x.value + m.c * y.value + m.e, m.b * x.value + m.d * y.value + m.f)])[0]
        kind = pdfium_c.FPDFPathSegment_GetType(seg)
        if kind == pdfium_c.FPDF_SEGMENT_MOVETO:
            points = [(px, py)]
        else:
            if points and kind == pdfium_c.FPDF_SEGMENT_LINETO:
                out.append((*points[-1], px, py))
            points.append((px, py))
            if pdfium_c.FPDFPathSegment_GetClose(seg) and len(points) > 2:
                out.append((px, py, *points[0]))
    return out


def _runs(textpage) -> tuple[list[Frag], list[tuple[str, float, float, float, float]], bool]:
    """pdfium's characters, in its own order, cut into runs: one text object, one baseline, no wide gap.

    Reading characters one by one (not text boxes) means a letter that pokes into the next box is never
    read twice, and pdfium's own spaces decide where words break. Returns the runs, every character with
    its box (for table cells), and whether any text is turned (upright or slanted).
    """
    import pypdfium2.raw as pdfium_c

    raw = textpage.raw
    l, r, b, t = (ctypes.c_double() for _ in range(4))
    chars: list[tuple[str, float, float, float, float]] = []
    runs: list[dict] = []
    cur = None
    turned = False
    count = pdfium_c.FPDFText_CountChars(raw)
    pair = -1
    for i in range(count):
        if i == pair:
            continue                              # the second half of a letter stored as two (see below)
        code = pdfium_c.FPDFText_GetUnicode(raw, i)
        if 0xD800 <= code <= 0xDBFF and i + 1 < count:
            low = pdfium_c.FPDFText_GetUnicode(raw, i + 1)
            if 0xDC00 <= low <= 0xDFFF:          # a letter beyond U+FFFF (math italics, emoji) comes in two halves
                code, pair = 0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00), i + 1
        ch = chr(code) if code and not 0xD800 <= code <= 0xDFFF else ""
        if ch in ("\r", "\n", ""):
            cur = None                            # pdfium's line break
            continue
        pdfium_c.FPDFText_GetCharBox(raw, i, ctypes.byref(l), ctypes.byref(r), ctypes.byref(b), ctypes.byref(t))
        box = (l.value, b.value, r.value, t.value)
        chars.append((ch, *box))
        if ch.isspace():
            if cur is not None:
                cur["text"] += " "
            continue
        obj = pdfium_c.FPDFText_GetTextObject(raw, i)
        obj = ctypes.cast(obj, ctypes.c_void_p).value if obj else None
        height = max(box[3] - box[1], 1.0)
        tall = max(height, cur["t"] - cur["b"]) if cur is not None else height     # "_" or "." is flat
        if cur is not None and obj == cur["obj"] and abs(box[1] - cur["b"]) < 0.5 * tall \
                and -0.5 * height < box[0] - cur["r"] < 1.2 * max(height, cur["t"] - cur["b"]):
            cur["text"] += ch
            cur["r"], cur["t"], cur["i1"] = max(cur["r"], box[2]), max(cur["t"], box[3]), max(i, pair)
            cur["l"], cur["b"] = min(cur["l"], box[0]), min(cur["b"], box[1])
        else:
            before = cur is not None and cur["text"].endswith(" ")
            cur = {"text": ch, "l": box[0], "b": box[1], "r": box[2], "t": box[3], "obj": obj, "i0": i, "i1": max(i, pair),
                   "space_before": before or (i > 0 and chr(pdfium_c.FPDFText_GetUnicode(raw, i - 1) or 32).isspace())}
            runs.append(cur)
        if not turned and abs(pdfium_c.FPDFText_GetCharAngle(raw, i)) > 0.01 and cur["i0"] == i:
            turned = True
    frags: list[Frag] = []
    weights: list[int] = []
    mono_fonts: set[str] = set()
    x, y = ctypes.c_double(), ctypes.c_double()
    for run in runs:
        text = run["text"].strip()
        if not text:
            continue
        size, bold, mono, italic, font, weight = _font(raw, run["i0"])
        if run["i1"] > run["i0"] + 3:            # a second sample, so one bold or code word doesn't decide
            _, bold2, mono2, italic2, _, weight2 = _font(raw, (run["i0"] + run["i1"]) // 2)
            bold, mono, italic, weight = bold and bold2, mono and mono2, italic and italic2, min(weight, weight2)
        if not mono and len(text) >= 6 and font not in mono_fonts:
            mono = _even_spacing(raw, run["i0"])  # a code font whose name doesn't say so
        if mono and font:
            mono_fonts.add(font)
        frags.append(Frag(text, run["l"], run["b"], run["r"], run["t"], size, bold, mono, italic, run["i0"],
                          run["i1"], run["space_before"], run["text"].endswith(" "), font))
        weights.append(weight)
    usual: Counter = Counter()
    for f, w in zip(frags, weights):
        usual[w] += len(f.text)
    base = usual.most_common(1)[0][0] if usual else 400
    for f, w in zip(frags, weights):             # heavier than the page's ordinary text, by a clear margin
        f.bold = f.bold or (w >= 600 and w - base >= 150)
    for f in frags:                              # every run in a font found to be monospaced is code
        f.mono = f.mono or f.font in mono_fonts
        if f.mono:
            pen = {}
            for i in range(f.i0, f.i1 + 1):
                if pdfium_c.FPDFText_GetCharOrigin(raw, i, ctypes.byref(x), ctypes.byref(y)):
                    pen[i] = x.value
            steps = sorted(pen[i + 1] - pen[i] for i in pen if i + 1 in pen and pen[i + 1] > pen[i])
            f.x0 = pen.get(f.i0, f.l)
            f.pitch = steps[len(steps) // 2] if steps else 0.0
    return frags, chars, turned


def _to_page(obj, points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Points inside an embedded figure (a form) are relative to it: move them to the page."""
    container = obj.container
    while container is not None:
        a, b, c, d, e, f = container.get_matrix().get()
        points = [(a * x + c * y + e, b * x + d * y + f) for x, y in points]
        container = container.container
    return points


def _bounds(obj) -> tuple[float, float, float, float]:
    l, b, r, t = obj.get_bounds()
    corners = _to_page(obj, [(l, b), (l, t), (r, b), (r, t)])
    xs, ys = [x for x, _ in corners], [y for _, y in corners]
    return min(xs), min(ys), max(xs), max(ys)


def scan_page(pdf, index: int) -> PageScan:
    import pypdfium2.raw as pdfium_c

    page = pdf[index]
    x0, y0, x1, y1 = page.get_cropbox()
    width, height = abs(x1 - x0) or 1.0, abs(y1 - y0) or 1.0
    textpage = page.get_textpage()
    frags, chars, turned = _runs(textpage)
    rotated = turned
    upright = [f for f in frags if len(f.text) > 2 and f.t - f.b > 2 * (f.r - f.l)]
    if upright:
        rotated = True                            # upright text, like the arXiv stamp down the margin

    h_lines, v_lines, pictures, drawn, shaded = [], [], [], [], []
    paths = []
    for obj in page.get_objects(filter=(pdfium_c.FPDF_PAGEOBJ_PATH, pdfium_c.FPDF_PAGEOBJ_IMAGE), max_depth=3):
        l, b, r, t = _bounds(obj)
        if obj.type == pdfium_c.FPDF_PAGEOBJ_IMAGE:
            if (r - l) * (t - b) > 0.004 * width * height:
                pictures.append((l, b, r, t))
            continue
        paths.append((obj, (l, b, r, t)))
    frames = _frames(paths, frags)
    for obj, (l, b, r, t) in paths:
        if id(obj) in frames:
            continue                              # a box around text (a code cell, a note, a highlight)
        fill, stroke = ctypes.c_int(), ctypes.c_int()
        pdfium_c.FPDFPath_GetDrawMode(obj.raw, ctypes.byref(fill), ctypes.byref(stroke))
        thin = min(r - l, t - b) < 3
        segments = _segments(obj)
        straight = all(abs(a - c) < 0.6 or abs(b_ - d) < 0.6 for a, b_, c, d in segments)
        curved = pdfium_c.FPDFPath_CountSegments(obj.raw) > len(segments) + 1    # Bezier pieces
        if not stroke.value and not thin:
            if straight and not curved and len(segments) <= 5:
                if not any(_overlaps(f, (l, b, r, t)) for f in frags):
                    shaded.append((l, b, r, t))  # a filled box with no text on it: a bar of a chart
            else:
                drawn.append((l, b, r, t))
            continue
        for a, b_, c, d in segments:
            if abs(b_ - d) < 0.6 and abs(c - a) > 4:
                h_lines.append((min(a, c), max(a, c), (b_ + d) / 2))
            elif abs(a - c) < 0.6 and abs(d - b_) > 4:
                v_lines.append((min(b_, d), max(b_, d), (a + c) / 2))
        if not straight or curved or len(segments) > 64:
            drawn.append((l, b, r, t))           # curves or slanted lines: a drawing
        if thin and not stroke.value:            # a thin filled bar works as a rule
            if r - l > t - b:
                h_lines.append((l, r, (b + t) / 2))
            else:
                v_lines.append((b, t, (l + r) / 2))

    lines = _group_lines(frags)
    gutter = _gutter(lines, x0, width)
    if gutter:
        lines = _column_lines(frags, gutter)
    scan = PageScan(index + 1, width, height, lines, [], pictures, y0=min(y0, y1))
    if len(shaded) >= 3:
        drawn += shaded                           # many filled boxes: striped table rows or a bar chart
    _route(scan, h_lines, v_lines, drawn, rotated or page.get_rotation() != 0)
    for grid in scan.grids:
        _fill_grid(grid, chars)
    return scan


def _overlaps(f: Frag, box) -> bool:
    l, b, r, t = box
    return f.l < r and f.r > l and f.b < t and f.t > b


def _frames(paths, frags: list[Frag]) -> set[int]:
    """Boxes drawn around text: a code cell, a note, a highlighted line, a box with rounded corners.

    A frame's every point lies on its own edge (nothing drawn across it), the text it touches lies wholly
    inside it, and nothing else is drawn inside it. Boxes side by side are the cells of a table, and a box
    with lines inside is a table's border: neither is a frame. The text in a frame is read as usual.
    """
    import pypdfium2.raw as pdfium_c

    x, y = ctypes.c_float(), ctypes.c_float()
    found = []
    for obj, (l, b, r, t) in paths:
        w, h = r - l, t - b
        n = pdfium_c.FPDFPath_CountSegments(obj.raw)
        if w < 12 or h < 5 or n < 4 or n > 40:
            continue
        inside = [f for f in frags if _overlaps(f, (l, b, r, t))]
        if not inside or not all(f.l >= l - 2 and f.r <= r + 2 and f.b >= b - 2 and f.t <= t + 2 for f in inside):
            continue
        m = pdfium_c.FS_MATRIX()
        pdfium_c.FPDFPageObj_GetMatrix(obj.raw, ctypes.byref(m))
        points = []
        for i in range(n):
            seg = pdfium_c.FPDFPath_GetPathSegment(obj.raw, i)
            pdfium_c.FPDFPathSegment_GetPoint(seg, ctypes.byref(x), ctypes.byref(y))
            points.append((m.a * x.value + m.c * y.value + m.e, m.b * x.value + m.d * y.value + m.f))
        tol = max(1.5, min(8.0, 0.3 * min(w, h)))
        if all(min(abs(px - l), abs(px - r), abs(py - b), abs(py - t)) <= tol for px, py in _to_page(obj, points)):
            found.append((obj, (l, b, r, t)))
    frames = {id(obj) for obj, _ in found}
    for obj, (l, b, r, t) in found:
        # boxes in a row (table cells, or the boxes of a diagram)
        side = any(o is not obj and abs((bb + tt) / 2 - (b + t) / 2) < 0.5 * min(t - b, tt - bb)
                   and (rr <= l + 2 or ll >= r - 2) for o, (ll, bb, rr, tt) in found)
        # lines drawn inside it (a table), or a line or arrow that ends at its edge (a diagram)
        within = touch = False
        for o, (ll, bb, rr, tt) in paths:
            if id(o) in frames:
                continue
            if ll > l + 2 and rr < r - 2 and bb > b + 2 and tt < t - 2:
                within = True
            elif (min(rr - ll, tt - bb) < 3 and ll <= r + 3 and rr >= l - 3 and bb <= t + 3 and tt >= b - 3
                  and not (ll >= l - 1 and rr <= r + 1 and bb >= b - 1 and tt <= t + 1)):
                touch = True
        if side or within or touch:
            frames.discard(id(obj))
    return frames


def _group_lines(frags: list[Frag]) -> list[Line]:
    """Runs on the same baseline become one line; lines are sorted top to bottom."""
    frags.sort(key=lambda f: (-(f.b + f.t) / 2, f.l))
    lines: list[Line] = []
    for f in frags:
        for line in lines[-3:]:
            overlap = min(line.t, f.t) - max(line.b, f.b)
            small = f.size < 0.85 * line.size and line.b <= f.b <= line.t      # a superscript or footnote mark
            if overlap > 0.5 * min(line.t - line.b, f.t - f.b) or small:
                line.frags.append(f)
                line.frags.sort(key=lambda g: g.l)
                break
        else:
            lines.append(Line([f]))
    lines.sort(key=lambda ln: (-ln.t, ln.l))
    # a superscript or subscript met before its own line: put it into the line it sits on
    out: list[Line] = []
    for i, ln in enumerate(lines):
        host = None
        for other in lines[max(0, i - 2):i + 3]:
            if other is not ln and ln.size < 0.85 * other.size and len(ln.text) <= 3 and (
                    other.b <= ln.b <= other.t or other.b <= ln.t <= other.t):
                host = other
                break
        if host is not None:
            host.frags = sorted(host.frags + ln.frags, key=lambda g: g.l)
        else:
            out.append(ln)
    return out


def _gutter(lines: list[Line], x0: float, width: float) -> float | None:
    """The gap between two columns of text, if the page has them: an upright band that no line crosses.

    A line crosses where a run of text covers the spot, or where its gap there is only a space between
    words; so a page whose every word is its own run is never mistaken for two columns.
    """
    if len(lines) < 8:
        return None
    best = None
    for step in range(0, 61, 2):
        x = x0 + width * (0.35 + step / 200)
        crossing = left = right = both = 0
        for ln in lines:
            if any(f.l < x - 2 and f.r > x + 2 for f in ln.frags):
                crossing += 1
                continue
            lefts = [f for f in ln.frags if f.r <= x + 2]
            rights = [f for f in ln.frags if f.l >= x - 2]
            if lefts and rights:
                if min(f.l for f in rights) - max(f.r for f in lefts) < 1.0 * ln.size:
                    crossing += 1
                else:
                    both += 1
            elif lefts:
                left += 1
            else:
                right += 1
        n = len(lines)
        if crossing <= 0.1 * n and both + left >= 0.25 * n and both + right >= 0.25 * n:
            if best is None or crossing < best[0]:
                best = (crossing, x)
    return best[1] if best else None


def _column_lines(frags: list[Frag], gutter: float) -> list[Line]:
    """Two columns: in each band between full-width lines, the left column first, then the right."""
    def middle(f: Frag) -> float:
        return (f.b + f.t) / 2

    across = [f for f in frags if f.l < gutter - 2 and f.r > gutter + 2]
    rest = [f for f in frags if not (f.l < gutter - 2 and f.r > gutter + 2)]
    full = _group_lines(across)
    out: list[Line] = []
    placed: set[int] = {id(f) for f in across}
    above = float("inf")
    for stop in full + [None]:
        below = stop.t if stop else float("-inf")
        band = [f for f in rest if below < middle(f) <= above and id(f) not in placed]
        for col, side in ((0, [f for f in band if f.r <= gutter + 2]), (1, [f for f in band if f.r > gutter + 2])):
            for ln in _group_lines(side):
                ln.col = col
                out.append(ln)
        placed.update(id(f) for f in band)
        if stop:
            same = [f for f in rest if stop.b <= middle(f) <= stop.t and id(f) not in placed]
            stop.frags = sorted(stop.frags + same, key=lambda g: g.l)    # runs level with the full-width line
            placed.update(id(f) for f in same)
            out.append(stop)
            above = stop.b
    if len(placed) != len(frags) or sum(len(ln.frags) for ln in out) != len(frags):
        return _group_lines(frags)                # never lose a run: read the page as one column instead
    return out


def _cluster(values: list[float], tolerance: float) -> list[float]:
    out: list[float] = []
    for v in sorted(values):
        if out and v - out[-1] <= tolerance:
            continue
        out.append(v)
    return out


def _route(scan: PageScan, h_lines, v_lines, drawn, rotated: bool) -> None:
    """Decide fast or Docling for one page, and find the fully ruled tables the fast path can read."""
    def to_docling(reason: str) -> None:
        scan.route, scan.reason = "docling", reason

    lines, width = scan.lines, scan.width
    if rotated:
        return to_docling("rotated page or text")

    if any(ln.col >= 0 for ln in lines) and (h_lines or v_lines or scan.pictures):
        return to_docling("two columns with tables or pictures")

    # Ruled tables: group the drawn lines that touch each other.
    groups: list[dict] = []
    for kind, items in (("h", h_lines), ("v", v_lines)):
        for a0, a1, pos in items:
            box = (a0, pos, a1, pos) if kind == "h" else (pos, a0, pos, a1)
            hit = [g for g in groups if box[0] <= g["box"][2] + 3 and box[2] >= g["box"][0] - 3
                   and box[1] <= g["box"][3] + 3 and box[3] >= g["box"][1] - 3]
            merged = {"h": [], "v": [], "box": box}
            for g in hit:
                groups.remove(g)
                merged["h"] += g["h"]
                merged["v"] += g["v"]
                merged["box"] = (min(merged["box"][0], g["box"][0]), min(merged["box"][1], g["box"][1]),
                                 max(merged["box"][2], g["box"][2]), max(merged["box"][3], g["box"][3]))
            merged[kind].append((a0, a1, pos))
            groups.append(merged)
    rules: dict[tuple[int, int], list[float]] = {}
    for g in groups:
        x0, y0, x1, y1 = g["box"]
        if not g["v"]:
            if len(g["h"]) >= 2 and _text_inside(lines, x0, y0 - 2, x1, y1 + 2):
                return to_docling("table without vertical lines")
            for a0, a1, pos in g["h"]:
                rules.setdefault((round(a0 / 4), round(a1 / 4)), []).append(pos)
            continue                              # a lone rule: under a header, above footnotes
        if not g["h"]:
            continue                              # a lone vertical bar beside text
        if x1 - x0 < 30 or y1 - y0 < 10 or not _text_inside(lines, x0 - 1, y0 - 1, x1 + 1, y1 + 1):
            continue                              # a small mark or an icon with no text in it, not a table
        xs = _cluster([p for *_, p in g["v"]], 1.5)
        ys = sorted(_cluster([p for *_, p in g["h"]], 1.5), reverse=True)
        full = (all(a0 <= xs[0] + 2 and a1 >= xs[-1] - 2 for a0, a1, _ in g["h"])
                and all(a0 <= ys[-1] + 2 and a1 >= ys[0] - 2 for a0, a1, _ in g["v"]))
        if len(xs) == 2 and len(ys) == 2:
            continue                              # a box around text: the text is read as usual
        if len(xs) == 1:
            continue                              # one upright line with rules off it: a listing's bar, a bracket
        if not full or len(xs) < 3 or len(ys) < 3:
            return to_docling("table with merged cells, or a drawing")
        scan.grids.append(Grid(xs, ys))
    for (a0, a1), ys in rules.items():          # rules of the same width, above and below a table
        ys = sorted(ys)
        for low, high in zip(ys, ys[1:]):
            if high - low > 0.5 * scan.height:
                continue                          # a rule under the header and one over the footer
            between = [ln for ln in lines if low - 1 < (ln.b + ln.t) / 2 < high + 1
                       and a0 * 4 - 4 <= ln.l and ln.r <= a1 * 4 + 4]
            if sum(1 for ln in between if _row_like(ln, scan)) >= 2:
                return to_docling("table without vertical lines")
    letters = "".join(ln.text for ln in lines)
    if letters and len(_ARABIC.findall(letters)) > 0.2 * len(letters):
        return to_docling("Urdu or Arabic text")          # right-to-left lines need Docling's reading order
    for p in scan.pictures:
        if any(_wholly_inside(ln, p) for ln in lines):
            return to_docling("text on a picture")        # a slide background, a banner, a figure's labels
    for d in drawn:                               # big enough to be a figure (not a badge behind "2.2")
        if (d[2] - d[0]) * (d[3] - d[1]) > 0.003 * width * scan.height and min(d[2] - d[0], d[3] - d[1]) >= 50 \
                and _text_inside(lines, *d):
            return to_docling("drawing with text")
    gappy = sum(1 for ln in lines if _row_like(ln, scan) and not any(_inside_any(ln, g.box) for g in scan.grids))
    if gappy >= 3:
        return to_docling("columns of text (a table without lines)")


_LEADER = re.compile(r"\.{5,}|(?:\. ){4,}")                     # "Introduction ........ 1" in a contents page
_NOT_A_CELL = re.compile(r"^(?:\(\d+(?:\.\d+)*[a-z]?\)|//|/\*|#)")   # an equation's number, a code comment


def _row_like(ln: Line, scan: PageScan) -> bool:
    """A line that looks like a table row: a wide gap with a cell after it. Not a running header ("26  2 Data"),
    a contents line, an equation with its number at the right, or code with a comment lined up at the right."""
    if scan.high(ln) or scan.low(ln) or _LEADER.search(ln.text):
        return False
    numbered = re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){0,2}\.?", ln.frags[0].text.strip())    # "1.4  Describe the..."
    frags = ln.frags[1:] if _separate_marker(ln) or numbered else ln.frags
    return any(b.l - a.r > 1.8 * ln.size and not _NOT_A_CELL.match(b.text.strip()) and not b.mono
               for a, b in zip(frags, frags[1:]))    # code after a gap: a line number, or code lined up


def _columns_in(ln: Line) -> bool:
    """A line with a wide gap between runs of text: the cells of a table row, side by side."""
    gaps = [b.l - a.r for a, b in zip(ln.frags, ln.frags[1:])]
    if _separate_marker(ln):
        gaps = gaps[1:]                           # a list's bullet or number is not a column
    return any(gap > 1.8 * ln.size for gap in gaps)


def _text_inside(lines: list[Line], l, b, r, t) -> bool:
    return any(f.l >= l - 1 and f.r <= r + 1 and f.b >= b - 1 and f.t <= t + 1 for ln in lines for f in ln.frags)


def _wholly_inside(ln: Line, box) -> bool:
    """Text drawn on a picture: a slide background, a banner, the labels of a figure."""
    l, b, r, t = box
    return ln.l >= l - 1 and ln.r <= r + 1 and ln.b >= b - 1 and ln.t <= t + 1


def _run_in(f: Frag, box) -> bool:
    """A run that lies inside a table's grid: its characters were read into the table's cells."""
    l, b, r, t = box
    return f.l >= l - 1 and f.r <= r + 1 and f.b >= b - 1 and f.t <= t + 1


def _inside_any(ln: Line, box) -> bool:
    l, b, r, t = box
    cx, cy = (ln.l + ln.r) / 2, (ln.b + ln.t) / 2
    return l - 1 <= cx <= r + 1 and b - 1 <= cy <= t + 1


def _fill_grid(grid: Grid, chars: list[tuple[str, float, float, float, float]]) -> None:
    """Each cell's text: the characters whose middle is inside it, in pdfium's order."""
    cells = [["" for _ in grid.xs[1:]] for _ in grid.ys[1:]]
    for ch, l, b, r, t in chars:
        cx, cy = (l + r) / 2, (b + t) / 2
        col = next((k for k, (a, z) in enumerate(zip(grid.xs, grid.xs[1:])) if a <= cx <= z), None)
        row = next((k for k, (a, z) in enumerate(zip(grid.ys, grid.ys[1:])) if z <= cy <= a), None)
        if col is not None and row is not None:
            cells[row][col] += ch
    grid.cells = [[" ".join(value.split()) for value in row] for row in cells]


# ---------------------------------------------------------------------------
# 2. Read a plain page: lines -> headings, paragraphs, lists, code, captions, footnotes
# ---------------------------------------------------------------------------

@dataclass
class Item:
    kind: str                # title, heading, text, list_item, code, caption, footnote, table
    text: str
    page: int
    box: tuple[float, float, float, float]
    level: int = 1
    marker: str = ""
    left: float = 0.0        # code: its left margin; list item: where its text starts
    x0: float = 0.0          # code: where the pen starts its first line
    grid: Grid | None = None
    pages: list[int] = field(default_factory=list)


def _norm(text: str) -> str:
    return _NOT_WORD.sub(" ", text.casefold()).strip()


def _signature(text: str) -> str:
    return _DIGITS.sub("#", _norm(text))


class Book:
    """What the fast path needs to know about the whole book before reading any page."""

    def __init__(self, scans: list[PageScan], outline: list[tuple[int, str, int]]):
        sizes: Counter = Counter()
        for s in scans:
            for ln in s.lines:
                if not ln.mono:
                    sizes[round(ln.size)] += len(ln.text)
        self.body = float(sizes.most_common(1)[0][0]) if sizes else 10.0
        self.outline: dict[int, list[tuple[str, int]]] = {}
        for level, title, page in outline:
            self.outline.setdefault(page, []).append((_norm(title), level + 1))
        self.levels_by_size = sorted({round(ln.size) for s in scans for ln in s.lines if len(ln.text) < 120 and (
            ln.size >= 1.12 * self.body or ln.bold and ln.size >= 1.05 * self.body)}, reverse=True)
        self.furniture = self._running_lines(scans)
        texts = Counter(ln.text.strip() for s in scans for ln in _edge_lines(s))
        self._repeated_exactly = {t for t, n in texts.items() if n >= 3}

    def _running_lines(self, scans: list[PageScan]) -> set[str]:
        """Running headers and footers: lines at the very top or bottom, set apart, repeated on 3+ pages.

        Repeated means the same words; a number in it must be the page's own number ("Page 7"), so
        "Example 1.3" and "Example 2.4" at the tops of two pages are not mistaken for a header.
        """
        self.offsets = self._page_offsets(scans)
        exact: Counter = Counter()
        numbered: Counter = Counter()
        for s in scans:
            for ln in _edge_lines(s):
                text = ln.text.strip()
                exact[text] += 1
                if self._has_page_number(s, text):
                    numbered[_signature(text)] += 1
        return ({_signature(t) for t, n in exact.items() if n >= 3 and _signature(t)}
                | {sig for sig, n in numbered.items() if n >= 3 and sig})

    def _page_offsets(self, scans: list[PageScan]) -> set[int]:
        """How printed page numbers relate to page positions (printed 1 on the 5th page: offset -4).

        Only a line that is just a number ("7", "vii", "Page 7 of 90") or ends in "Page 7" counts, and an
        offset must hold on at least 3 pages and a third of the pages that print a number.
        """
        seen: Counter = Counter()
        pages = 0
        for s in scans:
            values = set()
            for ln in _edge_lines(s):
                text = ln.text.strip()
                if _PAGE_NUMBER.fullmatch(text):
                    values.update(_numbers_in(text)[:1])
                else:                             # "Page 7", or a number opening or closing the line
                    values.update(int(m) for m in re.findall(r"\bpage\s+(\d{1,4})\b", text, re.IGNORECASE))
                    values.update(int(m) for m in re.findall(r"^(\d{1,4})\b|\b(\d{1,4})$", text) for m in m if m)
            pages += bool(values)
            for value in values:
                seen[value - s.number] += 1
        return {offset for offset, n in seen.items() if n >= 3 and n >= pages / 3}

    def _has_page_number(self, scan: PageScan, text: str) -> bool:
        return any(value - scan.number in self.offsets for value in _numbers_in(text))

    def is_furniture(self, scan: PageScan, ln: Line) -> bool:
        edges = _edge_lines(scan)
        if ln not in edges or ln.size > 1.05 * self.body:
            return False
        text = ln.text.strip()
        if ln.bold and ln.size >= 0.95 * self.body and not _PAGE_NUMBER.fullmatch(text):
            return False                          # a bold line at the top is a heading ("Exercises"), keep it
        outermost = ln is max(scan.lines, key=lambda x: x.t) or ln is min(scan.lines, key=lambda x: x.b)
        if not outermost and not (ln.size < 0.95 * self.body or ln.italic or ln.bold):
            return False                          # one line in from the edge, looking like body text: keep it
        if _PAGE_NUMBER.fullmatch(text):
            return self._has_page_number(scan, text)  # only the page's own number, never "2024" or code output
        if _signature(text) not in self.furniture:
            return False
        return not _DIGITS.search(text) or self._has_page_number(scan, text) or text in self._repeated_exactly

    def outline_level(self, page: int, text: str) -> int | None:
        key = _norm(text)
        core = _CHAPTER.sub("", key)
        for title, level in self.outline.get(page, []) + self.outline.get(page - 1, []) + self.outline.get(page + 1, []):
            if key and (key == title or (len(key) > 8 and (title.startswith(key) or key.startswith(title)))):
                return level
            whole = _CHAPTER.sub("", title)            # "chapter 1 introduction to ..." on the bookmark
            if len(core) > 12 and (core == whole or (core in whole and len(core) > 0.6 * len(whole))):
                return level
        return None


_CHAPTER = re.compile(r"^(?:(?:chapter|part|unit|lecture|module|appendix)\s+[0-9a-z]{1,4}\s*)")
_ROMAN = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}


def _numbers_in(text: str) -> list[int]:
    """The numbers a header or footer could print as the page number: 7, "Page 7 of 90", "vii"."""
    values = [int(n) for n in re.findall(r"\b\d{1,4}\b", text)]
    word = text.strip().lower()
    if word and _PAGE_NUMBER.fullmatch(word) and not word[0].isdigit() and not word.startswith("page"):
        total = 0
        for a, b in zip(word, word[1:] + " "):
            total += -_ROMAN[a] if _ROMAN.get(b, 0) > _ROMAN[a] else _ROMAN[a]
        values.append(total)
    return values


def _edge_lines(scan: PageScan) -> list[Line]:
    """Lines in the page's top or bottom margin, set apart from the text by a gap (a page number need not be).

    Up to two at each end, outermost first. Being here doesn't make a line a header or footer: it must
    also repeat, or carry the page number.
    """
    lines = sorted(scan.lines, key=lambda ln: -ln.t)
    out: list[Line] = []
    for side in (lines, lines[::-1]):
        for k in range(min(2, len(side) - 1)):
            ln, inner = side[k], side[k + 1]
            in_margin = scan.high(ln) if side is lines else scan.low(ln)
            apart = (ln.b - inner.t if side is lines else inner.b - ln.t) > 0.8 * ln.size
            if not in_margin or not (apart or _PAGE_NUMBER.fullmatch(ln.text.strip())) or ln in out:
                break
            out.append(ln)
    return out


def read_page(scan: PageScan, book: Book, heading_state: list[int]) -> list[Item]:
    """One plain page -> items in reading order. heading_state carries the last outline level across pages."""
    body = book.body
    lines = []
    for ln in scan.lines:
        if book.is_furniture(scan, ln):
            continue
        outside = [f for f in ln.frags if not any(_run_in(f, g.box) for g in scan.grids)]
        if len(outside) == len(ln.frags):
            lines.append(ln)
        elif outside:                                  # a note beside a table, on the same baseline as a row
            lines.append(Line(outside, ln.col))
    shape = {col: _shape([ln for ln in lines if ln.col == col], body, scan)
             for col in {ln.col for ln in lines}}      # each column has its own left edge, right edge, spacing

    items: list[Item] = []
    pending_tables = sorted(scan.grids, key=lambda g: -g.ys[0])
    prev: Line | None = None
    for ln in lines:
        while pending_tables and pending_tables[0].ys[0] > ln.t:
            g = pending_tables.pop(0)
            items.append(Item("table", "", scan.number, g.box, grid=g))
            prev = None
        left, right, gap = shape[ln.col]
        text = ln.text.strip()
        kind, level, marker = _classify(ln, text, scan, book, left, heading_state)
        last = items[-1] if items else None
        if (kind == "heading" and level and last is not None and last.kind in ("text", "list_item") and prev is not None
                and prev.col == ln.col and prev.bold == ln.bold and abs(prev.size - ln.size) < 0.6
                and prev.b - ln.t < 1.6 * shape[ln.col][2] + 1.5 and not _SENTENCE_END.search(prev.text.strip())
                and book.outline_level(scan.number, text) is None):
            kind, level = "text", 0                # "...similar hardware devices and" carries on: not a heading
        if kind == "list_item":
            marker, text = _split_marker(ln, text)
        if (kind == "list_item" and not _separate_marker(ln) and last is not None and last.kind == "text"
                and prev is not None and prev.col == ln.col and prev.b - ln.t < 1.6 * gap + 1.5
                and not _SENTENCE_END.search(prev.text.strip())):
            kind, marker, text = "text", "", ln.text.strip()     # "...see Section\n2. The..." carries on the sentence
        if prev is not None and prev.col != ln.col:
            # the top of the next column: a paragraph carries on if the last one stopped mid-sentence
            joins = (last is not None and last.kind == "text" and kind == "text"
                     and not _SENTENCE_END.search(last.text.rstrip()))
        else:
            space = (prev.b - ln.t) if prev else 99
            joins = (last is not None and prev is not None and space < 2.2 * gap + 2
                     and _continues(last, kind, ln, prev, left, right, body, gap, space))
        if (not joins and last is not None and prev is not None and last.text.endswith(_SOFT_HYPHENS)
                and last.kind in ("text", "list_item", "caption", "footnote") and kind not in ("code", "title")):
            joins, text = True, ln.text.strip()  # the line above broke a word in two: this line finishes it
        if joins:
            if last.kind == "code":
                blank = prev.b - ln.t > 1.6 * (prev.t - prev.b)      # an empty line inside the listing
                last.text += "\n" * (2 if blank else 1) + _indent(ln, last) + text
            else:
                last.text = _join_lines(last.text, text)
            last.box = (min(last.box[0], ln.l), min(last.box[1], ln.b), max(last.box[2], ln.r), last.box[3])
        else:
            start = ln.frags[1].l if kind == "list_item" and _separate_marker(ln) else ln.l
            if kind == "list_item" and marker and not _separate_marker(ln):
                start = ln.l + (len(marker) + 1) * ln.frags[0].char_width   # "– Text": where the text starts
            items.append(Item(kind, text, scan.number, (ln.l, ln.b, ln.r, ln.t), level=level, marker=marker,
                              left=start, x0=min(ln.frags, key=lambda f: f.l).x0))
        prev = ln
    for g in pending_tables:
        items.append(Item("table", "", scan.number, g.box, grid=g))
    for item in items:
        if item.kind == "heading" and (len(item.text) > 200 or re.search(r"[.!?] [A-Z]", item.text)):
            item.kind, item.level = "text", 0       # two sentences, or several lines: a paragraph in bold
    return items


_SOFT_HYPHENS = ("\x02", "\u00ad", "\ufffe")


def _join_lines(above: str, below: str) -> str:
    """A word broken at the end of a line with a soft hyphen (pdfium shows it as \\x02) is put back together."""
    if above.endswith(_SOFT_HYPHENS):
        return above[:-1] + below
    return above + "\n" + below


def _shape(lines: list[Line], body: float, scan: PageScan) -> tuple[float, float, float]:
    """Left edge, right edge and usual gap between lines of ordinary text, for one column (or the page)."""
    plain = [ln for ln in lines if abs(ln.size - body) < 1 and not ln.mono] or lines
    if not plain:
        return 0.0, scan.width, 0.3 * body
    left = Counter(round(ln.l) for ln in plain).most_common(1)[0][0]
    spacing = [a.b - b.t for a, b in zip(plain, plain[1:]) if 0 < a.b - b.t < 2 * body]
    gap = statistics.median(spacing) if spacing else 0.3 * body
    return left, max(ln.r for ln in plain), gap


def _indent(ln: Line, block: Item) -> str:
    """Spaces for a code line, from how far right of the listing's margin it starts, in monospace characters.

    Measured with the PDF's own letter widths (where the pen starts, how far it moves per letter), not the
    letters' drawn shapes, which change with the font the computer substitutes (Courier New on Windows)."""
    first = min(ln.frags, key=lambda f: f.l)
    pitches = sorted(f.pitch for f in ln.frags if f.pitch > 0)
    if pitches and block.x0 and first.x0:
        return " " * max(0, round((first.x0 - block.x0) / pitches[len(pitches) // 2]))
    width = max(f.char_width for f in ln.frags if len(f.text) >= 3) if any(len(f.text) >= 3 for f in ln.frags) \
        else ln.frags[0].char_width
    return " " * max(0, round((ln.l - block.left) / width)) if width > 0 else ""


_LABEL = re.compile(r"^[A-Z][A-Z ]{2,15}:\s+\S")      # "CONCEPT: All computers...", "NOTE: C++ is..."


def _classify(ln: Line, text: str, scan: PageScan, book: Book, left: float, state: list[int]):
    body = book.body
    if scan.number <= 2 and ln.size >= 1.6 * body and len(text) < 150 and not state[1]:
        state[1] = 1
        return "title", 0, ""
    level = book.outline_level(scan.number, text) if ln.size >= 0.95 * body else None
    if level is not None:
        state[0] = level
        return "heading", level, ""
    if ln.mono and not _CAPTION.match(text):
        return "code", 0, ""
    if _CAPTION.match(text):
        return "caption", 0, ""
    if ln.size <= 0.85 * body and ln.b - scan.y0 < 0.25 * scan.height:
        return "footnote", 0, ""
    short = len(text) < 120 and not text.endswith((".", ",", ";")) and not _LABEL.match(text)
    bigger = ln.size >= 1.12 * body or ln.bold and ln.size >= 1.05 * body
    numbered_bold = ln.bold and bool(re.match(r"\d+(\.\d+)*\.?\s+[A-Z]", text))   # "1 Introduction" in bold
    if (_separate_marker(ln) or _MARKER_PREFIX.match(text)) and not (short and (bigger or numbered_bold)):
        return "list_item", 0, ""
    if short and bigger and len(text) > 1:
        if book.outline:
            return "heading", state[0] + 1 if state[0] else 1, ""
        numbered = _NUMBERED.match(text)
        if numbered and numbered.group(1):
            return "heading", numbered.group(1).count(".") + 1, ""
        if numbered:
            return "heading", 1, ""
        rank = book.levels_by_size.index(round(ln.size)) if round(ln.size) in book.levels_by_size else 0
        return "heading", rank + 1, ""
    if short and ln.bold and ln.size >= 0.95 * body and len(text) > 2:
        deepest = state[0] if book.outline else len(book.levels_by_size)
        return "heading", deepest + 1, ""
    return "text", 0, ""


def _separate_marker(ln: Line) -> bool:
    """A bullet or number drawn on its own, a little left of the item's text."""
    if len(ln.frags) < 2:
        return False
    first, second = ln.frags[0], ln.frags[1]
    if re.fullmatch(r"\d{1,3}", first.text.strip()) and (second.text[:1].isdigit() or second.text[:1] in ",.:;%"
                                                        or second.i0 == first.i1 + 1):
        return False                              # "1" and "982, a war...": one number, cut in two runs
    return bool(_MARKER.match(first.text.strip()) or re.fullmatch(r"\d{1,3}", first.text.strip())) \
        and second.l - first.r > 0.2 * second.size


def _split_marker(ln: Line, text: str) -> tuple[str, str]:
    if _separate_marker(ln):
        return ln.frags[0].text.strip(), Line(ln.frags[1:]).text.strip()
    m = _MARKER_PREFIX.match(text)
    return (m.group(1), text[m.end():]) if m else ("", text)


def _continues(last: Item, kind: str, ln: Line, prev: Line, left, right, body, gap, space) -> bool:
    """Does this line carry on the item above it?"""
    if last.kind == "code":
        return kind == "code"
    if kind in ("code", "title", "list_item", "table") or last.kind in ("title", "table"):
        return False
    if last.kind == "heading":
        return kind == "heading" and abs(ln.size - prev.size) < 0.6 and space < 0.8 * ln.size
    if kind == "heading":
        return False
    if last.kind in ("caption", "footnote"):
        return kind in ("text", last.kind) and abs(ln.size - prev.size) < 0.6 and space < 1.5 * gap + 1
    if abs(ln.size - prev.size) > 0.6:
        return False
    if space > 1.6 * gap + 1.5:
        return False                              # a gap between paragraphs
    ended = prev.r < right - 3 * body and _SENTENCE_END.search(prev.text.strip())
    if last.kind == "list_item":
        return abs(ln.l - last.left) < max(3, 0.6 * body) and not ended   # wrapped lines line up with its text
    if ln.l > left + 0.8 * body and ln.l > prev.l + 0.8 * body and _SENTENCE_END.search(prev.text.strip()):
        return False                              # first-line indent after a full stop: a new paragraph
    if ended:
        return False                              # the line above ended short, with a full stop
    return True


# ---------------------------------------------------------------------------
# 3. Build: items -> DoclingDocument, Docling for routed pages, one document in page order
# ---------------------------------------------------------------------------

def _to_document(name: str, scans: list[PageScan], items_by_page: dict[int, list[Item]]) -> DoclingDocument:
    from docling_core.types.doc import (BoundingBox, CoordOrigin, DocItemLabel, DoclingDocument, GroupLabel,
                                        ProvenanceItem, Size, TableCell, TableData)

    doc = DoclingDocument(name=name)
    for local, scan in enumerate(scans, 1):
        doc.add_page(page_no=local, size=Size(width=scan.width, height=scan.height))
    local_of = {scan.number: i for i, scan in enumerate(scans, 1)}
    for items in items_by_page.values():
        for item in items:                         # a word broken at a page's or a box's end: show the hyphen
            for mark in _SOFT_HYPHENS:
                item.text = item.text.replace(mark, "-")

    def prov(item: Item):
        l, b, r, t = item.box
        box = BoundingBox(l=l, t=t, r=r, b=b, coord_origin=CoordOrigin.BOTTOMLEFT)
        pages = item.pages or [item.page]
        return [ProvenanceItem(page_no=local_of[p], bbox=box, charspan=(0, len(item.text))) for p in pages]

    group = None
    for scan in scans:
        for item in items_by_page.get(scan.number, []):
            if item.kind != "list_item":
                group = None
            p = prov(item)
            if item.kind == "title":
                node = doc.add_title(text=item.text.replace("\n", " "), prov=p[0])
            elif item.kind == "heading":
                node = doc.add_heading(text=item.text.replace("\n", " "), level=max(1, min(item.level, 100)), prov=p[0])
            elif item.kind == "list_item":
                if group is None:
                    group = doc.add_group(label=GroupLabel.LIST)
                ordered = bool(re.match(r"\(?\w{1,3}[.)]$", item.marker))
                node = doc.add_list_item(text=item.text, enumerated=ordered, marker=item.marker, parent=group, prov=p[0])
            elif item.kind == "code":
                node = doc.add_code(text=item.text, prov=p[0])
            elif item.kind == "table":
                g = item.grid
                cells = [TableCell(text=value, start_row_offset_idx=r, end_row_offset_idx=r + 1,
                                   start_col_offset_idx=c, end_col_offset_idx=c + 1, column_header=r == 0)
                         for r, row in enumerate(g.cells) for c, value in enumerate(row)]
                node = doc.add_table(data=TableData(num_rows=len(g.cells), num_cols=len(g.cells[0]),
                                                    table_cells=cells), prov=p[0])
            else:
                label = {"caption": DocItemLabel.CAPTION, "footnote": DocItemLabel.FOOTNOTE}.get(item.kind,
                                                                                               DocItemLabel.TEXT)
                node = doc.add_text(label=label, text=item.text, prov=p[0])
            node.prov.extend(p[1:])
    return doc


def _join_across_pages(items_by_page: dict[int, list[Item]], fast_pages: list[int]) -> None:
    """A paragraph cut by a page break: the last one on the page stops mid-sentence."""
    fast = set(fast_pages)
    for page in fast_pages:
        if page + 1 not in fast:
            continue
        here, there = items_by_page.get(page), items_by_page.get(page + 1)
        if not here or not there:
            continue
        body = [it for it in here if it.kind != "footnote"]
        if not body:
            continue
        last, first = body[-1], there[0]
        if last.kind == "text" and first.kind == "text" and not _SENTENCE_END.search(last.text.rstrip()):
            last.text = _join_lines(last.text, first.text)
            last.pages = (last.pages or [last.page]) + [page + 1]
            there.pop(0)


def _join_at_seams(doc: DoclingDocument, route: dict[int, str]) -> None:
    """Where a fast page meets a Docling page, a paragraph cut by the page break is joined, as elsewhere.

    Only when the last thing on one page and the first thing on the next are both ordinary paragraphs,
    and the first stops mid-sentence. Pages are taken in order, and a paragraph already joined into the
    one before it is followed to where it went, so nothing is joined into an item that was removed.
    """
    from docling_core.types.doc import DocItemLabel, TextItem

    order = [item for item, _ in doc.iterate_items() if getattr(item, "prov", None)]
    last_on: dict[int, object] = {}
    first_on: dict[int, object] = {}
    for item in order:
        first_on.setdefault(item.prov[0].page_no, item)
        last_on[item.prov[-1].page_no] = item
    moved: dict[int, TextItem] = {}             # id of a removed paragraph -> the paragraph it went into
    gone = []
    for page in sorted(last_on):
        last, first = last_on[page], first_on.get(page + 1)
        last = moved.get(id(last), last)
        if (first is None or first is last or route.get(page) == route.get(page + 1)
                or not isinstance(last, TextItem) or not isinstance(first, TextItem)
                or last.label != DocItemLabel.TEXT or first.label != DocItemLabel.TEXT
                or _SENTENCE_END.search(last.text.rstrip())):
            continue
        last.orig = _join_lines(last.orig or last.text, first.orig or first.text)
        last.text = _join_lines(last.text, first.text)
        last.prov.extend(first.prov)
        moved[id(first)] = last
        gone.append(first)
    if gone:
        doc.delete_items(node_items=gone)


def _outline(pdf) -> list[tuple[int, str, int]]:
    out = []
    try:
        for bm in pdf.get_toc():
            dest = bm.get_dest()
            index = dest.get_index() if dest else None
            title = bm.get_title()
            if index is not None and title:
                out.append((bm.level, title, index + 1))
    except Exception:                       # a broken outline must never stop reading the text
        logger.info("could not read the PDF outline", exc_info=True)
    return out


def _level_headings(doc: DoclingDocument, book: Book) -> None:
    """Give Docling's headings the same levels as the fast path: from the outline, else one below it."""
    from docling_core.types.doc import SectionHeaderItem

    if not book.outline:
        return
    state = 0
    for item, _ in doc.iterate_items():
        if isinstance(item, SectionHeaderItem):
            page = item.prov[0].page_no if item.prov else 0
            level = book.outline_level(page, item.text)
            if level is not None:
                state = level
                item.level = level
            else:
                item.level = state + 1 if state else 1


def convert_pdf(path: Path, converter: Callable, saved_part: Callable[[str], Path], workers: int = 1,
                converter_name: str = "") -> tuple[DoclingDocument | None, bool, dict]:
    """Read a long PDF: the fast path for plain pages, Docling for the rest, in batches.

    converter() gives Docling's DocumentConverter; saved_part(key) is where a finished batch is kept.
    With workers > 1 and converter_name ("module:function", importable in a fresh process), that many
    Docling processes read batches side by side. Returns (document, whether every page was read, a short
    report). The document is None when the file is short or mostly unusual pages: then Docling should
    read the whole file as before.
    """
    import pypdfium2 as pdfium
    from docling_core.types.doc import DoclingDocument, ImageRefMode, Size

    pdf = pdfium.PdfDocument(str(path))
    try:
        total = len(pdf)
        report: dict = {"pages": total}
        if total < MIN_PAGES:
            report["mode"] = "Docling for the whole file (short file)"
            return None, False, report
        scans = [scan_page(pdf, i) for i in range(total)]
        routed = [s.number for s in scans if s.route == "docling"]
        report.update(docling_pages=len(routed),
                      reasons=dict(Counter(s.reason for s in scans if s.route == "docling")))
        if len(routed) > ROUTE_ALL_ABOVE * total:
            report["mode"] = "Docling for the whole file (most pages need it)"
            return None, False, report
        report["mode"] = "fast path, Docling for some pages" if routed else "fast path"

        fast = [s for s in scans if s.route == "fast"]
        book = Book(fast, _outline(pdf))
        state = [0, 0]                            # the last outline level, whether the title was seen
        items_by_page = {s.number: read_page(s, book, state) for s in fast}
        _join_across_pages(items_by_page, [s.number for s in fast])

        # Docling for the routed pages, BATCH_PAGES at a time; each finished batch is saved
        place: dict[int, tuple[DoclingDocument, int]] = {}      # page -> (batch document, its page number there)
        complete = True
        batches = [routed[k:k + BATCH_PAGES] for k in range(0, len(routed), BATCH_PAGES)]
        saved_of = [saved_part(hashlib.sha256(",".join(map(str, b)).encode()).hexdigest()[:16]) for b in batches]
        todo = [k for k, saved in enumerate(saved_of) if not saved.exists()]
        ready = _convert_side_by_side(path, [batches[k] for k in todo], workers, converter_name) \
            if workers > 1 and converter_name and len(todo) > 1 else {}
        ready = {todo[k]: value for k, value in ready.items()}
        report["docling_workers"] = workers if ready else 1
        for number, (batch, saved) in enumerate(zip(batches, saved_of)):
            start = number * BATCH_PAGES
            if saved.exists():
                part, done = DoclingDocument.load_from_json(saved), True
            else:
                part, done = ready[number] if number in ready else _convert_pages(pdf, batch, converter)
                if part is None:
                    part = DoclingDocument(name=path.stem)
                if done:
                    tmp = saved.with_name(f"{saved.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
                    part.save_as_json(tmp, image_mode=ImageRefMode.PLACEHOLDER)
                    tmp.replace(saved)            # all or nothing, and two workers never share a temporary file
            complete = complete and done
            _split_far_merges(part, batch)
            for local, page in enumerate(batch, 1):
                if local not in part.pages:       # a page Docling skipped still counts as a page
                    scan = scans[page - 1]
                    part.add_page(page_no=local, size=Size(width=scan.width, height=scan.height))
                place[page] = (part, local)
            logger.info("%s: Docling has read %d of the %d pages it is needed for", path.name,
                        start + len(batch), len(routed))

        # one document, page by page in the original order: runs of fast pages and runs from one batch
        runs: list[list[PageScan]] = []
        for scan in scans:
            source = "fast" if scan.route == "fast" else id(place[scan.number][0])
            if runs and (runs[-1][0].route == "fast" if source == "fast" else
                         runs[-1][0].route != "fast" and id(place[runs[-1][0].number][0]) == source):
                runs[-1].append(scan)
            else:
                runs.append([scan])
        parts = []
        for run in runs:
            if run[0].route == "fast":
                parts.append(_to_document(path.stem, run, items_by_page))
            else:
                part = place[run[0].number][0]
                with warnings.catch_warnings():     # "Parent #/pictures/1 not found": a picture on another page
                    warnings.simplefilter("ignore", UserWarning)
                    parts.append(part.filter(page_nrs={place[s.number][1] for s in run}))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            document = DoclingDocument.concatenate(parts) if len(parts) > 1 else parts[0]
        document.name = path.stem
        _join_at_seams(document, {s.number: s.route for s in scans})
        _level_headings(document, book)
        return document, complete, report
    finally:
        pdf.close()


def docling_workers() -> int:
    """How many Docling processes read batches side by side: INGESTION_DOCLING_WORKERS, else 2 on a
    computer with 8 or more cores (each process loads Docling's models: about 1.5 GB of memory)."""
    value = os.getenv("INGESTION_DOCLING_WORKERS", "")
    if value.isdigit() and int(value) > 0:
        return int(value)
    return 2 if (os.cpu_count() or 1) >= 8 else 1


def _worker_start(threads: int) -> None:
    """In each Docling process, before torch loads: share the cores out instead of each taking all."""
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "DOCLING_NUM_THREADS"):
        os.environ[name] = str(threads)


def _worker_convert(path: str, pages: list[int], converter_name: str) -> tuple[dict | None, bool]:
    """One batch in a Docling process. The document comes back as plain data."""
    import importlib

    import pypdfium2 as pdfium

    module, function = converter_name.split(":")
    converter = getattr(importlib.import_module(module), function)
    pdf = pdfium.PdfDocument(path)
    try:
        part, done = _convert_pages(pdf, pages, converter)
    finally:
        pdf.close()
    return (part.export_to_dict() if part is not None else None), done


def _convert_side_by_side(path: Path, batches: list[list[int]], workers: int,
                          converter_name: str) -> dict[int, tuple[DoclingDocument | None, bool]]:
    """Batches read by several Docling processes at once. Whatever goes wrong here (a process that can't
    start, runs out of memory or crashes), the batches it didn't finish are read one by one afterwards."""
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor, as_completed

    from docling_core.types.doc import DoclingDocument

    workers = min(workers, len(batches))
    threads = max(1, (os.cpu_count() or 2) // workers)
    out: dict[int, tuple[DoclingDocument | None, bool]] = {}
    try:
        with ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context("spawn"),
                                 initializer=_worker_start, initargs=(threads,)) as pool:
            jobs = {pool.submit(_worker_convert, str(path), batch, converter_name): k for k, batch in enumerate(batches)}
            for job in as_completed(jobs):
                k = jobs[job]
                try:
                    data, done = job.result()
                except Exception:
                    logger.exception("%s: a Docling process failed on pages %s", path.name, batches[k][:3])
                    continue
                out[k] = (DoclingDocument.model_validate(data) if data else None, done)
                logger.info("%s: %d of %d Docling batches done (%d processes)", path.name, len(out), len(batches), workers)
    except Exception:
        logger.exception("%s: Docling processes stopped; reading the remaining batches one by one", path.name)
    return out


def _split_far_merges(part: DoclingDocument, batch: list[int]) -> None:
    """Inside a batch, Docling sees routed pages side by side, say the book's pages 4 and 9, and may join a
    paragraph across them. Split such an item at the gap, using where each page's text starts and ends
    (charspan); if that isn't known, keep all the text with the first page and drop the far pages from it.
    """
    from docling_core.types.doc import TextItem

    for item, _ in list(part.iterate_items(with_groups=False)):
        provs = getattr(item, "prov", None) or []
        if len(provs) < 2:
            continue
        groups = [[provs[0]]]
        for prev, prov in zip(provs, provs[1:]):
            near = batch[prov.page_no - 1] - batch[prev.page_no - 1] in (0, 1)
            if near:
                groups[-1].append(prov)
            else:
                groups.append([prov])
        if len(groups) == 1:
            continue
        cuts = _cut_points(item, groups) if isinstance(item, TextItem) else None
        if cuts:
            bounds = [0, *cuts, len(item.text)]
            pieces = [item.text[a:b].strip() for a, b in zip(bounds, bounds[1:])]
            for group, text in reversed(list(zip(groups[1:], pieces[1:]))):
                new = part.insert_text(sibling=item, label=item.label, text=text, prov=group[0], after=True)
                new.prov.extend(group[1:])
            item.text = item.orig = pieces[0]
        item.prov = groups[0]


def _cut_points(item, groups) -> list[int] | None:
    """Where each later group's text starts: its first charspan, moved to the nearest space so no word
    is cut (Docling's spans can be a few characters off where it joined a hyphenated word)."""
    text, cuts = item.text, []
    for group in groups[1:]:
        start = group[0].charspan[0]
        if not 0 < start < len(text) + 3:
            return None
        spaces = [k for k in range(max(1, start - 12), min(len(text), start + 12)) if text[k].isspace()]
        if not spaces:
            return None
        cut = min(spaces, key=lambda k: abs(k - start))
        if cuts and cut <= cuts[-1]:
            return None
        cuts.append(cut)
    return cuts


def _convert_pages(pdf, pages: list[int], converter: Callable) -> tuple[DoclingDocument | None, bool]:
    """Docling on some pages only: they are copied into a small PDF of their own first."""
    import pypdfium2 as pdfium
    from docling.datamodel.base_models import ConversionStatus
    from docling_core.types.io import DocumentStream

    part = pdfium.PdfDocument.new()
    try:
        part.import_pages(pdf, [p - 1 for p in pages])
        buffer = io.BytesIO()
        part.save(buffer)
    finally:
        part.close()
    buffer.seek(0)
    result = converter().convert(DocumentStream(name="pages.pdf", stream=buffer), raises_on_error=False)
    if result.status not in (ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS):
        logger.warning("docling could not read pages %s: %s", pages[:5], result.errors)
        return None, False
    return result.document, result.status == ConversionStatus.SUCCESS
