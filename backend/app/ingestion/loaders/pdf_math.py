"""Formulas in digital PDFs, for the fast path. Owner: Areeba.

Two things go wrong with formulas when a PDF's text is read line by line:

1. Symbols with no Unicode. Some math fonts give their symbols only a number: Mathematical Pi in the C++
   textbook gives "=" as \\x02 and "−" as \\x04, the MathTime extension font in the Data Science book gives
   "Σ" and "√" as \\x02. Read as they are, "x = −1" becomes "x 1". Such a symbol is drawn and compared with
   the symbols pdfium's own Symbol and Helvetica fonts draw, and the closest one is taken.
2. Layout. A formula set on its own lines is laid out in two dimensions: a fraction, a sum with limits
   above and below, sub- and superscripts. Line by line it comes out in pieces ("µ = 1 Σn xi", "n", "i=1").
   It is rebuilt from where each glyph sits, as LaTeX: "µ = \\frac{1}{n} \\sum_{i=1}^{n} x_{i}".

Nothing is guessed: every glyph of the formula is used once, or the formula keeps the PDF's own text.
"""
from __future__ import annotations

import ctypes
import re
import statistics
from dataclasses import dataclass

# fonts made for formulas (TeX's, MathTime, Cambria Math, STIX ...); "SymbolMT" is left out: Word uses it for bullets
MATH_FONT = re.compile(r"cmmi|cmsy|cmex|cmbsy|msam|msbm|mtmi|mtsy|mtex|mtms|eufm|euex|esint|stmary|rsfs|"
                       r"math|euclid|stix|xits|asana")
MATH_CHARS = set("∑∏∫∮√∞∂∇≤≥≠≈≡∝∈∉⊂⊃⊆⊇∪∩∀∃±∓×÷⇒⇔↦‖∥⌊⌋⌈⌉⟨⟩")
BIG_OPS = {"∑": "\\sum", "∏": "\\prod", "∫": "\\int", "∮": "\\oint", "⋃": "\\bigcup", "⋂": "\\bigcap"}
ACCENTS = {"¯": "\\bar", "ˉ": "\\bar", "̄": "\\bar", "ˆ": "\\hat", "̂": "\\hat", "˜": "\\tilde",
           "̃": "\\tilde", "˙": "\\dot", "̇": "\\dot", "¨": "\\ddot", "→": "\\vec", "⃗": "\\vec"}
PIECES = {"⎛": "(", "⎜": "(", "⎝": "(", "⎞": ")", "⎟": ")", "⎠": ")", "⎡": "[", "⎢": "[", "⎣": "[",
          "⎤": "]", "⎥": "]", "⎦": "]", "⎧": "{", "⎨": "{", "⎩": "{", "⎪": "|", "⎫": "}", "⎬": "}", "⎭": "}"}
FUNCTIONS = {"log", "ln", "exp", "max", "min", "sin", "cos", "tan", "arg", "lim", "sup", "inf", "det", "var",
             "cov", "mod", "sgn", "sign", "argmax", "argmin", "tr", "diag", "rank", "dim", "deg", "gcd", "cosh",
             "sinh", "tanh", "cot", "sec", "csc", "arcsin", "arccos", "arctan", "erf", "softmax"}
EQUATION_NUMBER = re.compile(r"^\(\d+(?:\.\d+)*[a-z]?\)$")


# ---------------------------------------------------------------------------
# 1. Symbols with no Unicode: recognised by their shape
# ---------------------------------------------------------------------------

# what such a symbol can be, drawn by pdfium's built-in fonts (the same on every computer). In a math font:
_SYMBOL_FONT = "=+−×÷±∓≠≈≡≤≥<>∑∏∫√∞∂∇∈∉⊂⊃⊆⊇∪∩∀∃→←↔⇒⇔⋅•∘°′″()[]{}|πθαβγδεσµλΔΩ∧∨¬∠⊥∝"
_HELVETICA = "*/½¼¾~^!:;,.#%&@"
_GRID = 20
_TALL = set("()[]{}|‖√∫⟨⟩")     # brackets, roots and integrals come in taller sizes in a formula
_MATH_NAME = re.compile(MATH_FONT.pattern + r"|symbol|pi-?(?:one|two|three|four|five|six)|universalpi")


@dataclass
class _Shape:
    char: str
    bits: list[float]
    aspect: float


_templates: dict[str, list[_Shape]] | None = None


def _ink(image) -> tuple[list[float], float] | None:
    """A drawing of one symbol -> its ink squeezed into a small grid, and its width over its height."""
    from PIL import ImageFilter

    gray = image.convert("L")
    w, h = gray.size
    px = gray.load()
    xs = [x for x in range(w) for y in range(h) if px[x, y] < 140]
    if not xs:
        return None
    ys = [y for y in range(h) for x in range(w) if px[x, y] < 140]
    l, r, t, b = min(xs), max(xs) + 1, min(ys), max(ys) + 1
    # blurred a little, so a thin stroke a pixel off still meets its template
    crop = gray.crop((l, t, r, b)).resize((_GRID, _GRID)).filter(ImageFilter.BoxBlur(1))
    cp = crop.load()
    bits = [1.0 - cp[x, y] / 255.0 for y in range(_GRID) for x in range(_GRID)]
    return bits, (r - l) / (b - t)


def _make_templates() -> dict[str, list[_Shape]]:
    import pypdfium2 as pdfium
    import pypdfium2.raw as pdfium_c
    from PIL import Image

    chars = ([("math", "Symbol", ch, ch) for ch in _SYMBOL_FONT] + [("math", "Helvetica", ch, ch) for ch in _HELVETICA]
             + [("math", "Helvetica", "||", "‖")])
    doc = pdfium.PdfDocument.new()
    cols = 20
    page = doc.new_page(cols * 60, (len(chars) // cols + 1) * 60)
    fonts = {}
    for k, (_, name, text, _) in enumerate(chars):
        font = fonts.setdefault(name, pdfium_c.FPDFText_LoadStandardFont(doc.raw, name.encode()))
        obj = pdfium_c.FPDFPageObj_CreateTextObj(doc.raw, font, ctypes.c_float(30))
        buf = ctypes.create_string_buffer((text + "\0").encode("utf-16-le"))
        pdfium_c.FPDFText_SetText(obj, ctypes.cast(buf, pdfium_c.FPDF_WIDESTRING))
        pdfium_c.FPDFPageObj_Transform(obj, 1, 0, 0, 1, 15 + (k % cols) * 60, 15 + (k // cols) * 60)
        pdfium_c.FPDFPage_InsertObject(page.raw, obj)
    pdfium_c.FPDFPage_GenerateContent(page.raw)
    image = page.render(scale=2).to_pil()
    height = image.size[1]
    out: dict[str, list[_Shape]] = {"math": []}
    for k, (group, _, text, name) in enumerate(chars):
        x, y = (k % cols) * 60 * 2, height - ((k // cols) * 60 + 60) * 2
        cell = image.crop((x, max(0, y), x + 120, y + 120))
        variants = [cell]
        if text == "∫":                          # a formula's integral sign leans like italic: add leaning ones
            variants += [cell.transform(cell.size, Image.AFFINE, (1, k_, -k_ * 60, 0, 1, 0), fillcolor="white")
                         for k_ in (0.25, 0.4)]
        for v in variants:
            found = _ink(v)
            if found:
                out[group].append(_Shape(name, *found))
    page.close()
    doc.close()
    return out


def recognise(page, box: tuple[float, float, float, float], origin: tuple[float, float], group: str = "math") -> str:
    """The symbol drawn in this box of the page (page coordinates), or "" unless one template is clearly
    closest."""
    import math

    global _templates
    if _templates is None:
        _templates = _make_templates()
    l, b, r, t = box
    x0, y1 = origin
    w, h = max(r - l, 0.3), max(t - b, 0.3)
    scale = max(2.0, min(40.0, 48.0 / max(w, h)))
    pad = 0.15                                   # a little: the next letter often starts right at the edge
    crop = (int((l - pad - x0) * scale), int((y1 - t - pad) * scale), int((r + pad - x0) * scale), int((y1 - b + pad) * scale))
    image = _render_box(page, crop, scale)
    found = _ink(image) if image is not None else None
    if not found:
        return ""
    bits, aspect = found
    scores: dict[str, float] = {}
    for shape in _templates[group]:
        both = sum(min(a, c) for a, c in zip(bits, shape.bits))
        either = sum(max(a, c) for a, c in zip(bits, shape.bits)) or 1.0
        ratio = math.log(max(aspect, 0.02) / max(shape.aspect, 0.02))
        if shape.char in _TALL:
            ratio = max(ratio, 0.0)              # a taller, narrower one is the same symbol
        s = both / either - 0.2 * abs(ratio) - 0.3 * max(0.0, abs(ratio) - 0.4)
        scores[shape.char] = max(scores.get(shape.char, -9.0), s)
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    best, score = ranked[0]
    runner = ranked[1][1] if len(ranked) > 1 else -9.0
    return best if score >= 0.35 and score - runner >= 0.04 else ""


def _render_box(page, crop: tuple[int, int, int, int], scale: float):
    """Draw only a small box of the page: pdfium renders the page into a bitmap the size of the box."""
    w, h = page.get_size()
    l, t, r, b = crop
    if r <= l or b <= t:
        return None
    left, top = max(0, l), max(0, t)
    right, bottom = min(int(w * scale), r), min(int(h * scale), b)
    if right <= left or bottom <= top:
        return None
    return page.render(scale=scale, crop=(left / scale, (h * scale - bottom) / scale,
                                          (w * scale - right) / scale, top / scale)).to_pil()


class Symbols:
    """Recognises a document's unnamed symbols, each (font, code) once: in one font a code stays one symbol."""

    def __init__(self):
        self.seen: dict[tuple[str, int], str] = {}

    def __call__(self, page, textpage, index: int, code: int, box, origin) -> str:
        import pypdfium2.raw as pdfium_c

        buf = ctypes.create_string_buffer(256)
        flags = ctypes.c_int(0)
        pdfium_c.FPDFText_GetFontInfo(textpage, index, buf, 256, ctypes.byref(flags))
        name = buf.value.decode("latin-1", "ignore")
        key = (name, code)
        if key not in self.seen:
            # only a math font's symbols: in a text font such a code is mostly a ligature ("de\x02ne" for
            # "define"), and "fi", "fl" and "ff" are too alike at this size to tell apart safely
            self.seen[key] = recognise(page, box, origin) if _MATH_NAME.search(name.lower()) else ""
        return self.seen[key]


# ---------------------------------------------------------------------------
# 2. Formulas set on their own lines: rebuilt from where each glyph sits
# ---------------------------------------------------------------------------

@dataclass
class Glyph:
    ch: str
    l: float
    b: float
    r: float
    t: float
    base: float              # the baseline the glyph stands on
    size: float              # the font's size
    font: str = ""
    space: bool = False      # pdfium puts a space before it: a word apart

    @property
    def cx(self): return (self.l + self.r) / 2
    @property
    def cy(self): return (self.b + self.t) / 2
    @property
    def h(self): return self.t - self.b


@dataclass
class Bar:
    x0: float
    x1: float
    y: float


def glyphs_of(textpage, ranges: list[tuple[int, int]], symbol=None) -> list[Glyph]:
    """Every visible character in these ranges of pdfium's character indices, with its box and baseline."""
    import pypdfium2.raw as pdfium_c

    out = []
    l, r, b, t = (ctypes.c_double() for _ in range(4))
    loose = pdfium_c.FS_RECTF()
    x, y = ctypes.c_double(), ctypes.c_double()
    buf = ctypes.create_string_buffer(128)
    flags = ctypes.c_int(0)
    gap = False
    for i0, i1 in ranges:
        i = i0
        gap = True
        while i <= i1:
            code = pdfium_c.FPDFText_GetUnicode(textpage, i)
            step = 1
            if 0xD800 <= code <= 0xDBFF:
                low = pdfium_c.FPDFText_GetUnicode(textpage, i + 1)
                if 0xDC00 <= low <= 0xDFFF:
                    code, step = 0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00), 2
            ch = chr(code) if code else ""
            generated = code in (10, 13) and pdfium_c.FPDFText_IsGenerated(textpage, i)
            if not ch or generated or pdfium_c.FPDFText_IsHyphen(textpage, i):
                i += step
                gap = True
                continue
            pdfium_c.FPDFText_GetCharBox(textpage, i, ctypes.byref(l), ctypes.byref(r), ctypes.byref(b), ctypes.byref(t))
            if code < 0x20:                      # a font's symbol number: "‖" as 9, "(" as 10 ...
                ch = (symbol(i, code, (l.value, b.value, r.value, t.value)) if symbol is not None else "") or "?"
            if ch.isspace():
                i += step
                gap = True
                continue
            pdfium_c.FPDFText_GetLooseCharBox(textpage, i, ctypes.byref(loose))
            if not pdfium_c.FPDFText_GetCharOrigin(textpage, i, ctypes.byref(x), ctypes.byref(y)):
                y.value = b.value
            pdfium_c.FPDFText_GetFontInfo(textpage, i, buf, 128, ctypes.byref(flags))
            # the font's own size (a script's is smaller); its box's height differs from font to font
            size = pdfium_c.FPDFText_GetFontSize(textpage, i)
            if size < 2:                         # text drawn at size 1 and scaled: measure it
                size = abs(loose.top - loose.bottom) or (t.value - b.value)
            out.append(Glyph(ch, l.value, b.value, r.value, t.value, y.value, size,
                             buf.value.decode("latin-1", "ignore").lower(), gap))
            gap = False
            i += step
    return out


def is_math(text: str, font: str) -> bool:
    return bool(MATH_FONT.search(font)) or any(ch in MATH_CHARS for ch in text)


def prose_words(frags) -> int:
    """Words of running text on a line: 3 letters or more, not in a math font, not a function name ("log")."""
    n = 0
    for f in frags:
        if MATH_FONT.search(f.font) or getattr(f, "italic", False):
            continue                                 # a math font, or italic: names in a formula ("loan − funded")
        n += sum(1 for w in re.findall(r"[A-Za-z]{3,}", f.text) if w.lower() not in FUNCTIONS)
    return n


@dataclass
class _El:
    """A piece of a formula on its way to LaTeX: one glyph, or a fraction, a root, a sum, a bracketed group."""
    l: float
    b: float
    r: float
    t: float
    base: float              # the baseline it stands on
    size: float
    text: str
    ch: str = ""             # the glyph, while it is one glyph
    delim: str = ""          # a tall bracket, not yet paired
    n: int = 1               # how many of the formula's glyphs it holds
    space: bool = False      # pdfium put a space before it
    roman: bool = False      # a glyph of an upright text font: "minimize", "if", not a variable

    @property
    def cx(self): return (self.l + self.r) / 2
    @property
    def cy(self): return (self.b + self.t) / 2
    @property
    def h(self): return self.t - self.b


class _Unsure(Exception):
    """The layout is not one this reader knows: the formula keeps the PDF's own text."""


_OPEN, _CLOSE = "([{|‖⟨", ")]}|‖⟩"
_SIGNS = set("=+−<>≤≥≈≠≡×÷±∓→⇒⇔∈∉⊂⊆∪∩")
_ESCAPE = {"_": "\\_", "%": "\\%", "#": "\\#", "&": "\\&", "$": "\\$", "{": "\\{", "}": "\\}"}   # LaTeX's own


def to_latex(glyphs: list[Glyph], bars: list[Bar]) -> str | None:
    """A formula's glyphs and the bars drawn in it -> LaTeX. None when a glyph would be left out, a symbol
    is not recognised, or the layout is not one it knows: then the formula keeps the PDF's own text."""
    if not glyphs:
        return None
    els = [_El(g.l, g.b, g.r, g.t, g.base, g.size, _ESCAPE.get(g.ch, g.ch), ch=g.ch, space=g.space,
               roman=not MATH_FONT.search(g.font) and not re.search(r"italic|oblique", g.font)) for g in glyphs]
    for e in els:                                # a math font draws "=" or "−" in a tall box: it takes the size
        if e.ch in _SIGNS:                       # of the letters beside it, so a "−" in a subscript is small
            near = [o for o in els if o.ch not in _SIGNS and o.n == 1 and abs(o.base - e.base) < 0.1 * o.size]
            if near:
                e.size = min(near, key=lambda o: min(abs(o.l - e.r), abs(e.l - o.r))).size
    try:
        els = _compose(els, list(bars))
        text = _line(els, 0)
    except _Unsure:
        return None
    if sum(e.n for e in els) != len(glyphs) or "?" in text:
        return None
    return re.sub(r"\s+", " ", text).strip()


def _size_of(els: list[_El]) -> float:
    plain = [e.size for e in els if e.n == 1 and e.ch not in BIG_OPS and e.ch not in PIECES and e.h < 2.5 * e.size]
    return statistics.median(plain or [e.size for e in els]) if els else 10.0


def _baseline(els: list[_El]) -> float:
    """The baseline most of the full-size pieces stand on."""
    ref = _full_size(els)
    counts: dict[int, list[float]] = {}
    for e in [e for e in els if e.size >= 0.85 * ref] or els:
        counts.setdefault(round(e.base / (0.3 * ref)), []).append(e.base)
    return statistics.median(max(counts.values(), key=len))


def _full_size(els: list[_El]) -> float:
    """The size of the line's own letters, not its scripts': the largest letter or digit."""
    letters = [e.size for e in els if e.n == 1 and e.ch.isalnum()]
    return max(letters) if letters else _size_of(els)


def _merge(parts: list[_El], text: str, own: int = 0, base: float | None = None, size: float | None = None) -> _El:
    return _El(min(p.l for p in parts), min(p.b for p in parts), max(p.r for p in parts), max(p.t for p in parts),
               statistics.median(p.base for p in parts) if base is None else base,
               _size_of(parts) if size is None else size, text, n=sum(p.n for p in parts) + own)


def _grow(cands: list[_El], start: float, up: bool, size: float, small: bool = False) -> list[_El]:
    """The pieces stacked on one side of a line (a fraction bar, a sum sign), touching each other. A sum's
    limits are small (small=True): a piece of full size below it is the next line of the formula."""
    out, edge = [], start
    for e in sorted(cands, key=lambda e: e.b if up else -e.t):
        near = (e.b - edge if up else edge - e.t) < 0.7 * max(e.size, 0.6 * size) + 1.5
        if not near or (small and e.size > 0.9 * size and e.ch not in ("+", "−", "-", "=", "<", ">")):
            break
        out.append(e)
        edge = max(edge, e.t) if up else min(edge, e.b)
    return out


def _words(els: list[_El], size: float) -> list[list[_El]]:
    """Pieces side by side on one baseline, close together: "i=1", "x∈c_j"."""
    words: list[list[_El]] = []
    for e in sorted(els, key=lambda e: (round(e.base), e.l)):
        if words and abs(words[-1][-1].base - e.base) < 0.3 * size and e.l - words[-1][-1].r < 0.3 * min(e.size, size):
            words[-1].append(e)
        else:
            words.append([e])
    return words


def _centred(parts: list[_El], bar: Bar) -> bool:
    """A numerator or denominator is one expression centred on its bar, not cells spread along a rule."""
    middle, half = (bar.x0 + bar.x1) / 2, (bar.x1 - bar.x0) / 2
    if abs((min(e.l for e in parts) + max(e.r for e in parts)) / 2 - middle) > 0.25 * half + 1.5:
        return False
    row = sorted(parts, key=lambda e: e.l)
    return all(b.l - a.r < 1.5 * max(a.size, b.size) for a, b in zip(row, row[1:]))


def _nearest(word: list[_El], ops: list[_El]) -> _El:
    cx = (min(e.l for e in word) + max(e.r for e in word)) / 2
    return min(ops, key=lambda o: abs(o.cx - cx))


def _compose(els: list[_El], bars: list[Bar], depth: int = 0) -> list[_El]:
    """Glyphs -> pieces: dots, accents, sums with their limits, then roots and fractions from the narrowest
    bar out (an inner fraction is whole before the one around it). Tall brackets are marked for _pairs."""
    size = _size_of(els)
    rest = list(els)

    def take(chosen) -> None:
        ids = {id(e) for e in chosen}
        rest[:] = [e for e in rest if id(e) not in ids]

    for vertical, least in ((True, 2), (False, 3)):                       # ⋮ and ⋱ set as separate dots
        dots = [e for e in rest if e.ch and e.ch in ".·⋅"]
        dots = sorted([d for d in dots if not any(o is not d and abs(o.cy - d.cy) < 0.2 * size and abs(o.cx - d.cx) < size
                                                  for o in dots)], key=lambda e: -e.t)    # not the dots of "..."
        while dots:
            chain = [dots.pop(0)]
            for d in list(dots):
                dx, dy = d.cx - chain[-1].cx, chain[-1].cy - d.cy
                if 0.2 * size < dy < 1.2 * size and (abs(dx) < 0.3 * size if vertical else 0.2 * size < dx < 1.2 * size):
                    chain.append(d)
                    dots.remove(d)
            if len(chain) >= least:
                take(chain)
                el = _merge(chain, "\\vdots" if vertical else "\\ddots", size=size)
                el.base = el.cy - 0.3 * size
                rest.append(el)

    pieces = sorted([e for e in rest if e.ch in PIECES], key=lambda e: e.l)  # tall brackets drawn in pieces
    while pieces:
        first = pieces.pop(0)
        column = [first] + [p for p in pieces if p.l < first.r and p.r > first.l and PIECES[p.ch] == PIECES[first.ch]]
        pieces = [p for p in pieces if not any(p is c for c in column)]
        take(column)
        el = _merge(column, _ESCAPE.get(PIECES[first.ch], PIECES[first.ch]), size=size)
        el.delim, el.base = PIECES[first.ch], el.cy - 0.3 * size
        rest.append(el)

    for a in [e for e in rest if e.ch in ACCENTS]:                          # x̄ is \bar{x}
        under = [e for e in rest if e is not a and e.ch not in ACCENTS and e.l < a.r and e.r > a.l
                 and e.t <= a.b + 0.6 * a.h + 1 and a.b - e.t < 0.5 * size]
        if under:
            target = max(under, key=lambda e: e.t)
            target.text, target.n, target.ch = ACCENTS[a.ch] + "{" + target.text + "}", target.n + 1, ""
            take([a])

    big = [e for e in rest if e.ch in BIG_OPS or (e.ch in ("Σ", "Π") and e.h > 1.2 * size)]
    for g in sorted(big, key=lambda e: e.l):                                  # sums, products, integrals
        w = g.r - g.l
        span = [e for e in rest if e is not g and g.l - 0.35 * w <= e.cx <= g.r + 0.35 * w
                and not any(b.x0 < g.r and b.x1 > g.l and min(e.cy, g.cy) < b.y < max(e.cy, g.cy) for b in bars)]
        span = [e for word in _words(span, size) if _nearest(word, big) is g for e in word]   # "x∈c" to its own sum
        upper = _grow([e for e in span if e.b >= g.t - 0.25 * g.h], g.t - 0.25 * g.h, True, size, small=True)
        lower = _grow([e for e in span if e.t <= g.b + 0.25 * g.h], g.b + 0.25 * g.h, False, size, small=True)
        take(upper + lower + [g])
        text = BIG_OPS.get(g.ch, {"Σ": "\\sum", "Π": "\\prod"}.get(g.ch, g.ch))
        if lower:
            text += "_{" + _line(lower, depth + 1) + "}"
        if upper:
            text += "^{" + _line(upper, depth + 1) + "}"
        rest.append(_El(g.l, g.b, g.r, g.t, g.cy - 0.3 * size, size, text, n=1 + sum(e.n for e in upper + lower)))

    for e in rest:
        if e.ch and e.ch in _OPEN + _CLOSE and e.h > 1.12 * size:
            e.delim, e.base = e.ch, e.cy - 0.3 * size   # a tall bracket: its partner is found in _pairs

    for bar in sorted(bars, key=lambda b: b.x1 - b.x0):                    # roots and fractions, narrowest first
        root = next((e for e in rest if e.ch in ("√", "?") and e.h > 0.8 * size and abs(bar.x0 - e.r) < 0.3 * e.h + 1.5
                     and abs(bar.y - e.t) < 0.25 * e.h + 1.5), None)     # a sign whose top runs into a bar is a root
        if root is not None:
            under = [e for e in rest if e is not root and bar.x0 - 1 <= e.cx <= bar.x1 + 1
                     and e.t <= bar.y + 1.5 and e.b >= root.b - 1.5]
            take(under + [root])
            el = _El(root.l, min([root.b] + [e.b for e in under]), bar.x1, bar.y,
                     _baseline(under) if under else root.base, _full_size(under) if under else size,
                     "\\sqrt{" + _line(under, depth + 1) + "}", n=1 + sum(e.n for e in under))
            rest.append(el)
            continue
        span = [e for e in rest if bar.x0 - 1.5 <= e.cx <= bar.x1 + 1.5]
        above = _grow([e for e in span if e.cy > bar.y], bar.y, True, size)
        below = _grow([e for e in span if e.cy < bar.y], bar.y, False, size)
        if not above or not below:
            if above or below:
                raise _Unsure                         # half a fraction: the other half is not in this formula
            continue
        if not (_centred(above, bar) and _centred(below, bar)):
            raise _Unsure                             # cells over and under a table's rule, not a fraction
        take(above + below)
        part = max(_size_of(above), _size_of(below))
        el = _merge(above + below, "\\frac{" + _line(above, depth + 1) + "}{" + _line(below, depth + 1) + "}",
                    base=bar.y - 0.3 * part, size=part)
        el.l, el.r = min(el.l, bar.x0), max(el.r, bar.x1)
        rest.append(el)
    if any(e.ch == "√" for e in rest):
        raise _Unsure                                 # a root sign with no bar over what is under it
    return rest


def _pairs(els: list[_El], depth: int) -> list[_El]:
    """A tall bracket and its partner enclose a group: a matrix or a binomial when stacked, else (...)."""
    if not any(e.delim for e in els):
        return els
    size = _size_of(els)
    els = sorted(els, key=lambda e: e.l)
    while True:
        pair = None
        for o in [e for e in els if e.delim and e.delim in _OPEN]:
            closes = [c for c in els if c.delim and c.delim in _CLOSE and c is not o and c.l > o.l
                      and min(o.t, c.t) - max(o.b, c.b) > 0.5 * min(o.h, c.h)]
            if closes:
                c = min(closes, key=lambda c: c.l)
                inside = [e for e in els if o.r - 1 <= e.cx <= c.l + 1 and e is not o and e is not c]
                if not any(e.delim for e in inside):
                    pair = (o, c, inside)
                    break
        if pair is None:
            break
        o, c, inside = pair
        rows = _rows(inside)
        if len(rows) >= 2:
            cells = [[_seq(cell, depth + 1) for cell in _cells(r, size)] for r in rows]
            if o.delim == "(" and c.delim == ")" and len(rows) == 2 and all(len(r) == 1 for r in cells):
                text = "\\binom{" + cells[0][0] + "}{" + cells[1][0] + "}"
            else:
                kind = {"(": "pmatrix", "[": "bmatrix", "|": "vmatrix", "‖": "Vmatrix"}.get(o.delim, "matrix")
                text = f"\\begin{{{kind}}} " + " \\\\ ".join(" & ".join(r) for r in cells) + f" \\end{{{kind}}}"
        else:
            text = _ESCAPE.get(o.delim, o.delim) + _seq(inside, depth + 1) + _ESCAPE.get(c.delim, c.delim)
        group = _merge([o, c] + inside, text, base=o.base, size=size)     # on the line the brackets centre on
        els = sorted([e for e in els if e is not o and e is not c and not any(e is i for i in inside)] + [group],
                     key=lambda e: e.l)
    for o in [e for e in els if e.delim == "{"]:                            # "{" with lines to its right: cases
        inside = [e for e in els if e.l >= o.r - 1 and o.b - 2 <= e.cy <= o.t + 2 and e is not o]
        rows = _rows(inside)
        if len(rows) >= 2:
            text = "\\begin{cases} " + " \\\\ ".join(_seq(r, depth + 1) for r in rows) + " \\end{cases}"
            group = _merge([o] + inside, text, base=o.base, size=size)
            els = sorted([e for e in els if e is not o and not any(e is i for i in inside)] + [group], key=lambda e: e.l)
    for e in els:
        e.delim = ""
    return els


def _rows(els: list[_El]) -> list[list[_El]]:
    """Pieces in lines, top to bottom, when they stand on two or more baselines of full size."""
    if not els:
        return []
    ref = _full_size(els)
    full = sorted([e for e in els if e.size >= 0.85 * ref], key=lambda e: -e.base)
    bases: list[float] = []
    for e in full:
        if not bases or bases[-1] - e.base > 0.9 * ref:
            bases.append(e.base)
    if len(bases) < 2:
        return [els]
    rows: list[list[_El]] = [[] for _ in bases]
    for e in els:
        rows[min(range(len(bases)), key=lambda i: abs(bases[i] - e.base))].append(e)
    return [r for r in rows if r]


def _cells(row: list[_El], size: float) -> list[list[_El]]:
    """A matrix row cut into cells at wide gaps."""
    row = sorted(row, key=lambda e: e.l)
    cells = [[row[0]]]
    for a, b in zip(row, row[1:]):
        if b.l - a.r > 1.2 * size:
            cells.append([])
        cells[-1].append(b)
    return cells


def _line(els: list[_El], depth: int) -> str:
    if depth > 10:
        raise _Unsure
    els = _pairs(els, depth)
    rows = _rows(els)
    if len(rows) >= 2:                           # lines of a formula set one under another
        return " \\\\ ".join(_seq(r, depth) for r in rows)
    return _seq(els, depth)


def _seq(els: list[_El], depth: int) -> str:
    """Pieces on one baseline, left to right; pieces set high or low (and smaller) are super- or subscripts."""
    if depth > 10:
        raise _Unsure
    if not els:
        return ""
    els = sorted(els, key=lambda e: (e.l, -e.r))
    ref = _full_size(els)
    base = _baseline(els)
    out: list[list] = []                         # [text, right edge, subscripts, superscripts, size]
    for e in els:
        if out:
            rise = (e.base - base) / ref
            smaller = e.size <= 0.88 * out[-1][4]
            if rise > 0.25 or (smaller and rise > 0.15):
                out[-1][3].append(e)
                continue
            if rise < -0.25 or (smaller and rise < -0.05):
                out[-1][2].append(e)
                continue
        elif abs(e.base - base) > 0.6 * ref:
            raise _Unsure                        # a script with nothing before it to belong to
        gap = e.l - out[-1][1] if out else 0.0
        sign = bool(out) and (out[-1][0][-1:] in _SIGNS or e.text[:1] in _SIGNS)
        a, b = (out[-1][0][-1:], e.text[:1]) if out else ("", "")
        words = bool(out) and a.isalnum() and b.isalnum() and (
            (a.isalpha() and b.isalpha() and e.space and gap > 0.15 * ref)            # pdfium's space: "loan funded"
            or ((e.roman or out[-1][6]) and gap > 0.25 * ref))                         # "subject to", "0 and", "log C"
        # words of text apart where pdfium puts a space ("subject to"), signs ("y = a"), a wide gap; not "x11"
        space = bool(out) and (gap > 0.6 * ref or words or ((sign or out[-1][0][-1:] in ",;") and gap > 0.15 * ref))
        out.append([e.text, e.r, [], [], e.size, space, e.roman])
    text = ""
    for k, (piece, _, subs, sups, _, space, _) in enumerate(out):
        if text and not text.endswith((" ", "(", "{")) and (
                space or (re.search(r"\\[A-Za-z]+$", text) and piece[:1].isalnum()) or piece[:1] == "\\"
                or (piece[:1].isalnum() and (out[k - 1][2] + out[k - 1][3] or out[k - 1][0][:1] == "\\"))):
            text += " "                          # a word apart, or "\sum x" (not "\sumx")
        text += piece
        for mark, group in (("_", subs), ("^", sups)):
            if group:
                inner = _seq(group, depth + 1)
                text += mark + (inner if len(inner) == 1 else "{" + inner + "}")
    return text
