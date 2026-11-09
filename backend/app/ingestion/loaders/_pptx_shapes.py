"""One python-pptx pass over a deck, for what Docling does not hand the PowerPoint loader.

- Which slides are hidden.
- Every shape on every slide, walked in the slide XML, groups and mc:AlternateContent included, with its own text,
  so the loader can audit where each shape's content went (audit() below).
- Text Docling never sees. python-pptx, and so Docling, skips every shape inside mc:AlternateContent, and PowerPoint
  wraps each text box holding an equation in one; those paragraphs are read here, equations as linear text. SmartArt
  text is read from the slide's diagram-data part.

The deck is opened once: python-pptx reads the zip once, and diagram parts come from the package already in memory.
Nothing here decides what becomes a block; loaders/pptx.py does.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lxml import etree

from app.ingestion.cleaning.common import clean_text

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "a14": "http://schemas.microsoft.com/office/drawing/2010/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "dgm": "http://schemas.openxmlformats.org/drawingml/2006/diagram",
}
FRAME_KINDS = {
    "http://schemas.openxmlformats.org/drawingml/2006/table": "table",
    "http://schemas.openxmlformats.org/drawingml/2006/chart": "chart",
    "http://schemas.openxmlformats.org/drawingml/2006/diagram": "smartart",
    "http://schemas.openxmlformats.org/presentationml/2006/ole": "embedded object",
}
FOOTER_PLACEHOLDERS = {"ftr": "footer", "sldNum": "slide number", "dt": "date"}
TITLE_PLACEHOLDERS = {"title", "ctrTitle"}
BOOKKEEPING = {"nvGrpSpPr", "grpSpPr", "extLst"}         # children of a group that are not shapes
WORDS = re.compile(r"\w+")


def _q(name: str) -> str:
    prefix, local = name.split(":")
    return f"{{{NS[prefix]}}}{local}"


def _local(element: Any) -> str:
    return etree.QName(element).localname if isinstance(element.tag, str) else ""


# ================================================================ what one pass collects

@dataclass(frozen=True)
class Paragraph:
    text: str
    math_only: bool = False      # the paragraph is one equation and nothing else


@dataclass(frozen=True)
class Shape:
    slide: int
    tag: str                     # for counts and logs, never text: "sp (text box)", "pic", "graphicFrame (chart)"
    kind: str                    # text, picture, connector, table, chart, smartart, embedded object, ink or unknown
    placeholder: str | None = None              # PowerPoint placeholder type: "title", "body", "ftr", ...
    paragraphs: tuple[Paragraph, ...] = ()      # text shapes: one per paragraph; tables: one per cell
    hidden_from_docling: bool = False           # inside mc:AlternateContent: python-pptx and Docling skip it
    has_equation: bool = False
    picture_fill: bool = False                  # a shape filled with a picture

    @property
    def lines(self) -> list[str]:
        return [p.text for p in self.paragraphs if p.text.strip()]


@dataclass
class Slide:
    number: int                                 # Docling's numbering: hidden slides count
    hidden: bool = False
    shapes: list[Shape] = field(default_factory=list)
    notes: tuple[str, ...] = ()
    smartart: list[tuple[tuple[int, str], ...]] = field(default_factory=list)   # per frame: (depth, text) lines


@dataclass
class Deck:
    slides: list[Slide]

    @property
    def hidden_slides(self) -> set[int]:
        return {s.number for s in self.slides if s.hidden}


def read_deck(path: Path) -> Deck:
    from pptx import Presentation                      # imported here, like the loader's other heavy imports

    presentation = Presentation(str(path))
    slides = []
    for number, slide in enumerate(presentation.slides, start=1):
        facts = Slide(number, hidden=slide._element.get("show") in ("0", "false"))
        for element, hidden_from_docling in _walk(slide.shapes._spTree):
            shape = _shape(number, element, hidden_from_docling)
            facts.shapes.append(shape)
            if shape.kind == "smartart":
                facts.smartart.append(_smartart_lines(slide.part, element))
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None:
            paragraphs = slide.notes_slide.notes_text_frame.paragraphs
            facts.notes = tuple(t for t in (p.text.replace("\v", " ").strip() for p in paragraphs) if t)
        slides.append(facts)
    return Deck(slides)


def _walk(container: Any, hidden_from_docling: bool = False):
    """Every shape element, groups opened. In mc:AlternateContent, the first mc:Choice is what PowerPoint shows."""
    for child in container:
        name = _local(child)
        if not name or name in BOOKKEEPING:
            continue
        if name == "grpSp":
            yield from _walk(child, hidden_from_docling)
        elif name == "AlternateContent":
            choice = child.find(_q("mc:Choice"))
            branch = choice if choice is not None else child.find(_q("mc:Fallback"))
            if branch is not None:
                yield from _walk(branch, True)
        else:
            yield child, hidden_from_docling


def _shape(slide: int, element: Any, hidden_from_docling: bool) -> Shape:
    name = _local(element)
    prefix = "alt:" if hidden_from_docling else ""
    if name == "sp":
        placeholder = element.find(f"{_q('p:nvSpPr')}/{_q('p:nvPr')}/{_q('p:ph')}")
        ph_type = placeholder.get("type", "obj") if placeholder is not None else None
        text_box = element.find(f"{_q('p:nvSpPr')}/{_q('p:cNvSpPr')}")
        detail = (f"placeholder {ph_type}" if ph_type else
                  "text box" if text_box is not None and text_box.get("txBox") in ("1", "true") else "shape")
        paragraphs = tuple(_paragraph(p) for p in element.iterfind(f"{_q('p:txBody')}/{_q('a:p')}"))
        return Shape(slide, f"{prefix}sp ({detail})", "text", ph_type, paragraphs, hidden_from_docling,
                     has_equation=element.find(f".//{_q('m:oMath')}") is not None,
                     picture_fill=element.find(f"{_q('p:spPr')}/{_q('a:blipFill')}") is not None)
    if name == "graphicFrame":
        data = element.find(f"{_q('a:graphic')}/{_q('a:graphicData')}")
        kind = FRAME_KINDS.get(data.get("uri") if data is not None else "", "unknown")
        cells = ()
        if kind == "table":
            cells = tuple(Paragraph(" ".join(_paragraph(p).text for p in cell.iterfind(f".//{_q('a:p')}")).strip())
                          for cell in element.iter(_q("a:tc")))
        return Shape(slide, f"{prefix}graphicFrame ({kind})", kind, paragraphs=cells,
                     hidden_from_docling=hidden_from_docling)
    kind = {"pic": "picture", "cxnSp": "connector", "contentPart": "ink"}.get(name, "unknown")
    return Shape(slide, f"{prefix}{name}", kind, hidden_from_docling=hidden_from_docling)


def _paragraph(p: Any) -> Paragraph:
    """A paragraph's text as Docling writes it (runs, fields, line breaks as spaces), equations written out."""
    parts, math, words = [], 0, 0
    for child in p:
        name = _local(child)
        if name in ("r", "fld"):
            text = "".join(t.text or "" for t in child.iter(_q("a:t")))
            parts.append(text)
            words += bool(text.strip())
        elif name == "br":
            parts.append(" ")
        elif child.tag == _q("a14:m"):                      # holds m:oMathPara or m:oMath
            parts.append(linear_math(child))
            math += 1
    text = "".join(parts).replace("\v", " ").strip()
    return Paragraph(text, math_only=math > 0 and words == 0)


# ================================================================ equations (OMML) as linear text

def linear_math(node: Any) -> str:
    """An equation as one line: x^2, (a+b)/c, sqrt(x), ∑_(i=1)^n i. Readable, not reversible."""
    if node.tag in (_q("a14:m"), _q("m:oMathPara")):
        return " ".join(linear_math(math) for math in node.iter(_q("m:oMath")))
    name = _local(node)
    if name == "t":
        return node.text or ""
    if name == "r":
        return "".join(t.text or "" for t in node.iter(_q("m:t")))
    part = {_local(child): child for child in node if _local(child)}
    get = lambda key: linear_math(part[key]) if key in part else ""        # noqa: E731
    if name == "f":
        return f"{_group(get('num'))}/{_group(get('den'))}"
    if name == "sSup":
        return f"{_group(get('e'))}^{_group(get('sup'))}"
    if name == "sSub":
        return f"{_group(get('e'))}_{_group(get('sub'))}"
    if name == "sSubSup":
        return f"{_group(get('e'))}_{_group(get('sub'))}^{_group(get('sup'))}"
    if name == "sPre":
        return f"_{_group(get('sub'))}^{_group(get('sup'))}{_group(get('e'))}"
    if name == "rad":
        degree = get("deg")
        return f"root({degree})({get('e')})" if degree else f"sqrt({get('e')})"
    if name == "nary":
        symbol = _value(node, "m:naryPr/m:chr", "∫")
        limits = (f"_{_group(get('sub'))}" if get("sub") else "") + (f"^{_group(get('sup'))}" if get("sup") else "")
        return f"{symbol}{limits} {get('e')}"
    if name == "d":
        begin, end = _value(node, "m:dPr/m:begChr", "("), _value(node, "m:dPr/m:endChr", ")")
        separator = _value(node, "m:dPr/m:sepChr", "|")
        return begin + separator.join(linear_math(e) for e in node.iterfind(_q("m:e"))) + end
    if name == "func":
        argument = get("e")
        return get("fName") + (argument if argument.startswith("(") else f"({argument})")
    if name == "limLow":
        return f"{get('e')}_{_group(get('lim'))}"
    if name == "limUpp":
        return f"{get('e')}^{_group(get('lim'))}"
    if name == "bar":
        return f"bar({get('e')})"
    if name == "acc":
        return f"{get('e')}{_value(node, 'm:accPr/m:chr', chr(0x302))}"
    if node.tag == _q("m:m"):                              # a matrix
        rows = [", ".join(linear_math(e) for e in row.iterfind(_q("m:e"))) for row in node.iterfind(_q("m:mr"))]
        return "[" + "; ".join(rows) + "]"
    if name == "eqArr":
        return "; ".join(linear_math(e) for e in node.iterfind(_q("m:e")))
    return "".join(linear_math(child) for child in node if not _local(child).endswith("Pr"))


def _group(text: str) -> str:
    return text if len(text) <= 1 or re.fullmatch(r"[\w.]+", text) else f"({text})"


def _value(node: Any, path: str, default: str) -> str:
    found = node.find("/".join(_q(step) for step in path.split("/")))
    return found.get(_q("m:val"), default) if found is not None else default


# ================================================================ SmartArt text

def _smartart_lines(slide_part: Any, frame: Any) -> tuple[tuple[int, str], ...]:
    """The text of one SmartArt graphic, in tree order: (depth, text), depth 1 for the top level."""
    relation = frame.find(f".//{_q('dgm:relIds')}")
    if relation is None or relation.get(_q("r:dm")) is None:
        return ()
    try:
        data = etree.fromstring(slide_part.related_part(relation.get(_q("r:dm"))).blob)
    except (KeyError, etree.XMLSyntaxError):
        return ()
    points = {pt.get("modelId"): pt for pt in data.iterfind(f"{_q('dgm:ptLst')}/{_q('dgm:pt')}")}
    children: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for link in data.iterfind(f"{_q('dgm:cxnLst')}/{_q('dgm:cxn')}"):
        if link.get("type", "parOf") == "parOf":
            children[link.get("srcId")].append((int(link.get("srcOrd", "0")), link.get("destId")))
    lines: list[tuple[int, str]] = []
    seen: set[str] = set()

    def visit(model_id: str, depth: int) -> None:
        if model_id in seen or model_id not in points:
            return
        seen.add(model_id)
        point = points[model_id]
        text = " ".join(_paragraph(p).text for p in point.iterfind(f"{_q('dgm:t')}/{_q('a:p')}")).strip()
        if text and point.get("type", "node") in ("node", "asst"):
            lines.append((max(depth, 1), text))
        for _, child in sorted(children[model_id]):
            visit(child, depth + 1)

    for model_id, point in points.items():
        if point.get("type") == "doc":
            visit(model_id, 0)
    for model_id in points:                               # text never reached from the root: keep it, flat
        visit(model_id, 1)
    return tuple(lines)


# ================================================================ the coverage audit

@dataclass(frozen=True)
class Entry:
    slide: int
    tag: str            # the shape type, never its text
    bucket: str         # "extracted", "skipped:<reason>" or "unknown"


def audit(deck: Deck, blocks: list, dropped: list[str], title: str) -> list[Entry]:
    """Put every shape (and each slide's notes) in exactly one bucket by comparing its text with the blocks."""
    text_on: dict[int, list[str]] = defaultdict(list)
    for b in blocks:
        text_on[b.loc.slide].append(norm(b.text))
    dropped_lines = {norm(t) for t in dropped}
    charts = Counter(b.loc.slide for b in blocks
                     if b.kind == "table" and b.extra.get("ref", "").startswith("#/pictures/"))
    smartart = Counter(b.loc.slide for b in blocks if b.extra.get("origin") == "smartart")
    entries = []
    for slide in deck.slides:
        here, seen = text_on.get(slide.number, []), Counter()
        for shape in slide.shapes:
            seen[shape.kind] += 1
            if shape.kind == "chart":
                bucket = "extracted" if charts[slide.number] >= seen["chart"] else "skipped:chart without data"
            elif shape.kind == "smartart":
                bucket = "extracted" if smartart[slide.number] >= seen["smartart"] else "skipped:smartart"
            else:
                bucket = _bucket(shape, here, dropped_lines, title)
            entries.append(Entry(slide.number, shape.tag, bucket))
        if slide.notes:
            wanted = [n for n in map(norm, slide.notes) if n]
            found = all(_found(n, here) for n in wanted)
            entries.append(Entry(slide.number, "notes", "extracted" if found else "unknown"))
    return entries


SKIPPED_KINDS = {"picture": "picture", "connector": "connector", "embedded object": "embedded object", "ink": "ink"}


def _found(line: str, blocks_here: list[str]) -> bool:
    return any(line in block for block in blocks_here)


def _bucket(shape: Shape, here: list[str], dropped: set[str], title: str) -> str:
    if shape.kind in SKIPPED_KINDS:
        return f"skipped:{SKIPPED_KINDS[shape.kind]}"
    if shape.kind not in ("text", "table"):
        return "unknown"
    if shape.placeholder in FOOTER_PLACEHOLDERS:
        return f"skipped:{FOOTER_PLACEHOLDERS[shape.placeholder]}"
    if not shape.lines:
        return "skipped:picture fill" if shape.picture_fill else "skipped:empty"
    wanted = [n for n in map(norm, shape.lines) if n]
    if not wanted:
        return "skipped:no words"                        # only digits or symbols, as clean_text() drops them
    missing = [n for n in wanted if not _found(n, here)]
    if not missing:
        return "extracted"
    if all(n in dropped for n in missing):
        return "skipped:repeated footer"
    if shape.placeholder in TITLE_PLACEHOLDERS and same_words(" ".join(shape.lines), title):
        return "skipped:deck title"
    if shape.hidden_from_docling:
        return "skipped:alternate content" + (" (equation)" if shape.has_equation else "")
    return "unknown"


def norm(text: str) -> str:
    """Text as compared by the audit: clean_text() (as to_blocks() applies it), spaces collapsed, case folded."""
    return " ".join(clean_text(text).split()).casefold()


def same_words(a: str, b: str) -> bool:
    return WORDS.findall(a.lower()) == WORDS.findall(b.lower())


def summary(entries: list[Entry]) -> list[str]:
    """Numbers only: counts by bucket, then by bucket and shape type, then every unknown by slide and type."""
    out = [f"shapes {len(entries)} | " + " | ".join(f"{bucket} {n}" for bucket, n in
                                                     sorted(Counter(e.bucket for e in entries).items()))]
    for (bucket, tag), n in sorted(Counter((e.bucket, e.tag) for e in entries).items()):
        out.append(f"  {bucket:<36} {tag:<36} {n}")
    out += [f"  UNKNOWN slide {e.slide}: {e.tag}" for e in entries if e.bucket == "unknown"]
    return out