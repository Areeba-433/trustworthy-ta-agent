"""Flowcharts drawn with Word shapes: which box each arrow joins, written out as text.

Docling keeps the words inside each shape but drops the arrows, so a flowchart comes back as loose lines
("Records screened", "(n = 3007)", "Records excluded", ...) with nothing saying what leads to what.
Word stores every shape with its size and position, and every arrow as a line with an arrowhead, so the
flow can be read from the file itself, without drawing it:

1. Every shape: its box on the page (in points) and its text. Every line or connector: its two ends and
   which end has an arrowhead.
2. Most flowcharts are loose shapes, each placed relative to a (usually empty) paragraph, so where each
   paragraph starts is estimated from its font size and spacing. Word's exact line height depends on the
   font, so a small scale on it is tried and the one where the most arrow ends touch a box wins.
   Shapes in a group or a drawing canvas share one coordinate system and need no estimate.
3. Each arrow end is joined to the box it touches (or to the box Word glued it to).
4. Boxes joined by arrows are one flowchart. A rotated or tall label at the side ("Screening") is a stage,
   a small text box lying on an arrow ("Yes", "No") is that arrow's label.

Not covered: pictures of flowcharts (only their words, through OCR), SmartArt, and old VML-only drawings.
"""
import logging
import math
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

logger = logging.getLogger("tta.ingestion")

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "wpg": "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup",
    "wpc": "http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
}
W = "{%s}" % NS["w"]
EMU = 12700.0                       # Word's drawing unit: 12700 per point
HEADER = "Flowchart (drawn with shapes in Word; each arrow is written as from → to):"

_LINES = {"line", "straightConnector1"} | {f"{kind}Connector{n}" for kind in ("bent", "curved") for n in range(2, 6)}
# Block arrows: where the arrow starts and ends inside its box (fractions of width and height), and its heads.
_BLOCK_ARROWS = {
    "rightArrow": ((0, .5), (1, .5), (False, True)), "leftArrow": ((1, .5), (0, .5), (False, True)),
    "downArrow": ((.5, 0), (.5, 1), (False, True)), "upArrow": ((.5, 1), (.5, 0), (False, True)),
    "notchedRightArrow": ((0, .5), (1, .5), (False, True)), "stripedRightArrow": ((0, .5), (1, .5), (False, True)),
    "leftRightArrow": ((0, .5), (1, .5), (True, True)), "upDownArrow": ((.5, 0), (.5, 1), (True, True)),
}
# Line height of one line of text, as a share of the font size (the font's ascent + descent + gap).
_LINE_HEIGHT = {
    "calibri": 1.2207, "calibri light": 1.2207, "cambria": 1.1719, "times new roman": 1.1499, "arial": 1.1499,
    "aptos": 1.2, "segoe ui": 1.3301, "georgia": 1.1362, "verdana": 1.2153, "tahoma": 1.2075,
    "consolas": 1.1709, "courier new": 1.1328, "garamond": 1.1235, "century gothic": 1.2251,
    "trebuchet ms": 1.1626, "book antiqua": 1.1704, "helvetica": 1.1499,
}
_DEFAULT_LINE_HEIGHT = 1.17
_SCALES = [round(0.80 + i * 0.01, 2) for i in range(51)]    # line-height scales tried: 0.80 ... 1.30
_TOUCH = 15.0                       # points: an arrow end this close to a box edge joins that box
_LABEL_REACH = 25.0                 # points: a small text box this close to an arrow is its label
_LABEL_WORDS = 4                    # an arrow label is short ("Yes", "No", "if valid")
_SIDE = 30.0                        # points: a loose box this close to a flowchart belongs to it
_STAGE_RATIO = 2.5                  # a box this many times taller than wide is a side label (a stage)


@dataclass
class Shape:
    """One Word shape, placed on the page (points, y grows downward)."""
    key: str                        # unique within the file
    ids: set[str]                   # Word's ids for it (used by glued connectors)
    prst: str                       # Word's shape name: "rect", "flowChartDecision", "straightConnector1" ...
    texts: list[str]                # its paragraphs (text box), as Word has them
    box: tuple[float, float, float, float]   # x0, y0, x1, y1 as seen (after rotation)
    rotated: bool                   # turned on its side (90 or 270 degrees)
    ends: tuple[tuple[float, float], tuple[float, float]] | None = None   # a line's start and end
    heads: tuple[bool, bool] = (False, False)   # arrowhead at the start, at the end
    glue: tuple[str | None, str | None] = (None, None)   # ids of the shapes Word glued the ends to
    drawing: int = 0                # which Word drawing (a group or canvas holds several shapes)
    grouped: bool = False           # in a group or canvas

    @property
    def is_line(self) -> bool:
        return self.ends is not None

    @property
    def text(self) -> str:
        return _join(self.texts)


@dataclass
class Flowchart:
    """One flowchart: its boxes (in reading order), its arrows, and the text it becomes."""
    text: str
    texts: list[str] = field(default_factory=list)   # every paragraph of its shapes, to find Docling's copies
    boxes: int = 0
    arrows: int = 0
    loose_lines: int = 0            # lines with an end that touches no box


# ---------------------------------------------------------------------------------------------------
# Reading the Word file
# ---------------------------------------------------------------------------------------------------

def _join(paragraphs: list[str]) -> str:
    """A box's paragraphs as one line: "Records screened (n = 3007)", "Records: PubMed (n=2); EMBASE (n=1)"."""
    out = ""
    for text in (" ".join(p.split()) for p in paragraphs):
        if not text:
            continue
        if not out:
            out = text
        elif out.endswith(":") or text[0] in "([" or text[0].islower():
            out += " " + text
        else:
            out += "; " + text
    return out


def _attr(element, path: str, name: str, default=None):
    found = element.find(path, NS) if element is not None else None
    if found is None:
        return default
    return found.get(name if ":" not in name else "{%s}%s" % (NS[name.split(":")[0]], name.split(":")[1]), default)


def _twips(value, default: float = 0.0) -> float:
    try:
        return int(value) / 20.0
    except (TypeError, ValueError):
        return default


class _Styles:
    """Paragraph spacing, font size and font family, through the style chain and the document defaults."""

    def __init__(self, styles_xml: bytes | None, theme_xml: bytes | None):
        self.by_id: dict[str, etree._Element] = {}
        self.defaults_p = self.defaults_r = None
        self.default_style = None
        if styles_xml:
            root = etree.fromstring(styles_xml)
            for style in root.findall("w:style", NS):
                self.by_id[style.get(W + "styleId")] = style
                if style.get(W + "type") == "paragraph" and style.get(W + "default") in ("1", "true"):
                    self.default_style = style.get(W + "styleId")
            self.defaults_p = root.find("w:docDefaults/w:pPrDefault/w:pPr", NS)
            self.defaults_r = root.find("w:docDefaults/w:rPrDefault/w:rPr", NS)
        self.theme = {"minor": "calibri", "major": "calibri light"}
        if theme_xml:
            root = etree.fromstring(theme_xml)
            for kind in ("minor", "major"):
                face = root.find(f".//a:{kind}Font/a:latin", NS)
                if face is not None and face.get("typeface"):
                    self.theme[kind] = face.get("typeface").casefold()

    def _chain(self, style_id: str | None) -> list:
        """The style and the styles it is based on, the base first."""
        chain, seen = [], set()
        style_id = style_id or self.default_style
        while style_id and style_id in self.by_id and style_id not in seen:
            seen.add(style_id)
            chain.append(self.by_id[style_id])
            based = self.by_id[style_id].find("w:basedOn", NS)
            style_id = based.get(W + "val") if based is not None else None
        return chain[::-1]

    def paragraph(self, p) -> dict:
        """Spacing (points), line rule, font size (points) and font of a paragraph's text."""
        p_pr = p.find("w:pPr", NS)
        style_id = _attr(p_pr, "w:pStyle", "w:val")
        chain = self._chain(style_id)
        spacing: dict[str, str] = {}
        r_props: list = [self.defaults_r]
        for source in [self.defaults_p] + [s.find("w:pPr", NS) for s in chain] + [p_pr]:
            node = source.find("w:spacing", NS) if source is not None else None
            if node is not None:
                spacing.update({etree.QName(k).localname: v for k, v in node.attrib.items()})
        r_props += [s.find("w:rPr", NS) for s in chain]
        mark = p_pr.find("w:rPr", NS) if p_pr is not None else None
        runs = [r.find("w:rPr", NS) for r in p.findall(".//w:r", NS) if r.find("w:t", NS) is not None
                and next(r.iterancestors(W + "p")) is p]
        size = font = None
        for props in r_props + ([runs[0]] if runs else [mark]):
            if props is None:
                continue
            if (sz := _attr(props, "w:sz", "w:val")) is not None:
                size = int(sz) / 2.0
            fonts = props.find("w:rFonts", NS)
            if fonts is not None:
                name = fonts.get(W + "ascii") or fonts.get(W + "hAnsi")
                theme = fonts.get(W + "asciiTheme") or fonts.get(W + "hAnsiTheme")
                if name:
                    font = name.casefold()
                elif theme:
                    font = self.theme["major" if theme.startswith("major") else "minor"]
        sizes = [int(v) / 2.0 for props in runs if props is not None and (v := _attr(props, "w:sz", "w:val"))]
        return {
            "before": 14.0 if spacing.get("beforeAutospacing") in ("1", "true") else _twips(spacing.get("before")),
            "after": 14.0 if spacing.get("afterAutospacing") in ("1", "true") else _twips(spacing.get("after")),
            "line": int(spacing.get("line", 240) or 240), "rule": spacing.get("lineRule", "auto"),
            "size": max([size or 10.0] + sizes), "font": font or self.theme["minor"],
        }


@dataclass
class _Section:
    width: float = 612.0            # page, points (US Letter)
    height: float = 792.0
    top: float = 72.0
    bottom: float = 72.0
    left: float = 72.0
    right: float = 72.0

    @property
    def text_width(self) -> float:
        return max(self.width - self.left - self.right, 72.0)

    @property
    def body_height(self) -> float:
        return max(self.height - self.top - self.bottom, 72.0)


def _section(sect_pr) -> _Section:
    if sect_pr is None:
        return _Section()
    size, margin = sect_pr.find("w:pgSz", NS), sect_pr.find("w:pgMar", NS)
    out = _Section()
    if size is not None:
        out.width, out.height = _twips(size.get(W + "w"), 612), _twips(size.get(W + "h"), 792)
    if margin is not None:
        out.top, out.bottom = abs(_twips(margin.get(W + "top"), 72)), abs(_twips(margin.get(W + "bottom"), 72))
        out.left, out.right = _twips(margin.get(W + "left"), 72), _twips(margin.get(W + "right"), 72)
    return out


@dataclass
class _Flow:
    """The body's paragraphs and tables in order, with what is needed to estimate where each one starts."""
    elements: list = field(default_factory=list)
    sections: list[_Section] = field(default_factory=list)
    heights: list[tuple[float, float]] = field(default_factory=list)   # (scaled part, fixed part) in points
    breaks: list[tuple[bool, bool]] = field(default_factory=list)      # page break before, after

    def layout(self, scale: float) -> tuple[list[float], list[float]]:
        """Where each element starts, and where its page starts, measured down the whole text (points)."""
        tops, pages = [], []
        y = page = 0.0
        for (scaled, fixed), (before, after), section in zip(self.heights, self.breaks, self.sections):
            end = page + section.body_height
            height = scaled * scale + fixed
            if (before and y > page) or (y + height > end and y > page and height < section.body_height):
                page, y = end, end
            tops.append(y)
            pages.append(page)
            y += height
            if after:
                page = y = page + section.body_height if y <= page + section.body_height else y
        return tops, pages


def _text_of(p) -> str:
    """A paragraph's own text (not that of a text box inside it), like python-docx: tabs and breaks kept."""
    out = []
    for node in p.iter(W + "t", W + "tab", W + "br", W + "cr"):
        if next(node.iterancestors(W + "p")) is not p:
            continue
        name = etree.QName(node).localname
        out.append(node.text or "" if name == "t" else "\t" if name == "tab" else "\n")
    return "".join(out)


def _paragraph_height(p, styles: _Styles, width: float) -> tuple[float, float]:
    """(line part, fixed part): the line part grows with the font's real line height, the rest does not."""
    props = styles.paragraph(p)
    text = _text_of(p)
    size = props["size"]
    lines = 0
    for piece in text.split("\n"):
        lines += max(1, math.ceil(len(piece) * 0.5 * size / max(width, 36.0)))
    natural = _LINE_HEIGHT.get(props["font"], _DEFAULT_LINE_HEIGHT) * size
    fixed = props["before"] + props["after"]
    inline = [int(e.get("cy", 0)) / EMU for e in p.findall(".//wp:inline/wp:extent", NS)
              if next(e.iterancestors(W + "p")) is p]
    if inline:
        fixed += max(0.0, max(inline) - natural)
    if props["rule"] == "exact":
        return 0.0, fixed + lines * props["line"] / 20.0
    if props["rule"] == "atLeast":
        least = props["line"] / 20.0
        return (lines * natural, fixed) if natural >= least else (0.0, fixed + lines * least)
    return lines * natural * props["line"] / 240.0, fixed


def _table_height(table, styles: _Styles, width: float) -> tuple[float, float]:
    scaled = fixed = 0.0
    for row in table.findall("w:tr", NS):
        cells = row.findall("w:tc", NS) or [row]
        best = (0.0, 0.0)
        for cell in cells:
            parts = [_paragraph_height(p, styles, width / len(cells)) for p in cell.iter(W + "p")
                     if not any(True for _ in p.iterancestors(W + "txbxContent"))]
            total = (sum(a for a, _ in parts), sum(b for _, b in parts))
            best = max(best, total, key=lambda ab: ab[0] + ab[1])
        rule = _attr(row, "w:trPr/w:trHeight", "w:hRule", "atLeast")
        least = _twips(_attr(row, "w:trPr/w:trHeight", "w:val"))
        if rule == "exact" and least:
            best = (0.0, least)
        elif least > best[0] + best[1]:
            best = (0.0, least)
        scaled, fixed = scaled + best[0], fixed + best[1]
    return scaled, fixed


def _body_flow(body, styles: _Styles) -> _Flow:
    flow = _Flow()

    def visit(parent) -> None:
        for child in parent:
            name = etree.QName(child).localname
            if name == "sdt":
                content = child.find("w:sdtContent", NS)
                if content is not None:
                    visit(content)
            elif name in ("p", "tbl"):
                flow.elements.append(child)
    visit(body)
    # A section's settings are on its last paragraph (or the body, for the last section).
    sections: list[_Section] = []
    current: list = []
    for element in flow.elements:
        current.append(element)
        sect = element.find("w:pPr/w:sectPr", NS) if etree.QName(element).localname == "p" else None
        if sect is not None:
            sections += [_section(sect)] * len(current)
            current = []
    sections += [_section(body.find("w:sectPr", NS))] * len(current)
    flow.sections = sections
    for element, section in zip(flow.elements, sections):
        if etree.QName(element).localname == "tbl":
            flow.heights.append(_table_height(element, styles, section.text_width))
            flow.breaks.append((False, False))
            continue
        width = section.text_width - _twips(_attr(element, "w:pPr/w:ind", "w:left")) \
            - _twips(_attr(element, "w:pPr/w:ind", "w:right"))
        flow.heights.append(_paragraph_height(element, styles, width))
        before = _attr(element, "w:pPr/w:pageBreakBefore", "w:val", None)
        page_break = any(br.get(W + "type") == "page" for br in element.iter(W + "br")
                         if next(br.iterancestors(W + "p")) is element)
        flow.breaks.append((before is not None and before not in ("0", "false"),
                            page_break or element.find("w:pPr/w:sectPr", NS) is not None))
    return flow


# ---------------------------------------------------------------------------------------------------
# Placing the shapes
# ---------------------------------------------------------------------------------------------------

def _rotate(point, centre, degrees: float) -> tuple[float, float]:
    if not degrees:
        return point
    a = math.radians(degrees)
    dx, dy = point[0] - centre[0], point[1] - centre[1]
    return centre[0] + dx * math.cos(a) - dy * math.sin(a), centre[1] + dx * math.sin(a) + dy * math.cos(a)


def _shape(sp, rect, key: str, drawing: int, grouped: bool, outer_id: str | None) -> Shape:
    """A wps:wsp at rect = (x, y, w, h) points before its own rotation."""
    x, y, w, h = rect
    sp_pr = sp.find("wps:spPr", NS)
    xfrm = sp_pr.find("a:xfrm", NS) if sp_pr is not None else None
    rot = int(xfrm.get("rot", 0)) / 60000.0 if xfrm is not None else 0.0
    flip_h = xfrm is not None and xfrm.get("flipH") in ("1", "true")
    flip_v = xfrm is not None and xfrm.get("flipV") in ("1", "true")
    prst = _attr(sp_pr, "a:prstGeom", "prst") or "custom"         # custom: drawn freehand (a:custGeom)
    texts = [_text_of(p) for p in sp.findall("wps:txbx/w:txbxContent/w:p", NS)]
    ids = {i for i in (_attr(sp, "wps:cNvPr", "id"), outer_id) if i}
    centre = (x + w / 2, y + h / 2)
    corners = [_rotate(c, centre, rot) for c in ((x, y), (x + w, y), (x, y + h), (x + w, y + h))]
    box = (min(c[0] for c in corners), min(c[1] for c in corners),
           max(c[0] for c in corners), max(c[1] for c in corners))
    turned = round(rot) % 180 == 90
    shape = Shape(key=key, ids=ids, prst=prst, texts=texts, box=box, rotated=turned, drawing=drawing, grouped=grouped)
    connector = sp.find("wps:cNvCnPr", NS) is not None
    if prst in _LINES or connector or prst in _BLOCK_ARROWS:
        if prst in _BLOCK_ARROWS:
            (fx0, fy0), (fx1, fy1), heads = _BLOCK_ARROWS[prst]
        else:
            (fx0, fy0), (fx1, fy1) = (0, 0), (1, 1)
            line = sp_pr.find("a:ln", NS) if sp_pr is not None else None
            heads = tuple(
                line is not None and _attr(line, f"a:{end}", "type", "none") not in ("none", None)
                for end in ("headEnd", "tailEnd"))
        if flip_h:
            fx0, fx1 = 1 - fx0, 1 - fx1
        if flip_v:
            fy0, fy1 = 1 - fy0, 1 - fy1
        shape.ends = (_rotate((x + fx0 * w, y + fy0 * h), centre, rot),
                      _rotate((x + fx1 * w, y + fy1 * h), centre, rot))
        shape.heads = heads
        cn = sp.find("wps:cNvCnPr", NS)
        if cn is not None:
            shape.glue = (_attr(cn, "a:stCxn", "id"), _attr(cn, "a:endCxn", "id"))
    return shape


def _children(container, transform, drawing: int, prefix: str, out: list[Shape]) -> None:
    """Shapes inside a group or canvas. transform maps the container's own units (EMU) to points."""
    tx, ty, sx, sy = transform
    for k, child in enumerate(container):
        name = etree.QName(child).localname
        if name not in ("wsp", "grpSp"):
            continue
        sp_pr = child.find("wps:spPr" if name == "wsp" else "wpg:grpSpPr", NS)
        xfrm = sp_pr.find("a:xfrm", NS) if sp_pr is not None else None
        if xfrm is None or xfrm.find("a:off", NS) is None or xfrm.find("a:ext", NS) is None:
            continue
        ox, oy = int(xfrm.find("a:off", NS).get("x")), int(xfrm.find("a:off", NS).get("y"))
        ew, eh = int(xfrm.find("a:ext", NS).get("cx")), int(xfrm.find("a:ext", NS).get("cy"))
        rect = (tx + ox * sx, ty + oy * sy, ew * sx, eh * sy)
        if name == "wsp":
            out.append(_shape(child, rect, f"{prefix}.{k}", drawing, True, None))
        else:
            _group(child, rect, drawing, f"{prefix}.{k}", out)


def _group(group, rect, drawing: int, prefix: str, out: list[Shape]) -> None:
    """A group placed at rect (points): its children use its chOff/chExt units."""
    xfrm = group.find("wpg:grpSpPr/a:xfrm", NS)
    x, y, w, h = rect
    ch_off = xfrm.find("a:chOff", NS) if xfrm is not None else None
    ch_ext = xfrm.find("a:chExt", NS) if xfrm is not None else None
    cx, cy = (int(ch_off.get("x")), int(ch_off.get("y"))) if ch_off is not None else (0, 0)
    cw, ch = (int(ch_ext.get("cx")), int(ch_ext.get("cy"))) if ch_ext is not None else (w * EMU, h * EMU)
    sx, sy = w / cw if cw else 1 / EMU, h / ch if ch else 1 / EMU
    _children(group, (x - cx * sx, y - cy * sy, sx, sy), drawing, prefix, out)


def _anchor_position(drawing, section: _Section, top: float, page: float, width: float, height: float,
                     p) -> tuple[float, float]:
    """Top-left corner of a drawing, in points: x from the text's left edge, y down the whole text."""
    if etree.QName(drawing).localname == "inline":
        jc = _attr(p.find("w:pPr", NS), "w:jc", "w:val", "left")
        if jc == "center":
            return (section.text_width - width) / 2, top
        return (section.text_width - width if jc in ("right", "end") else 0.0), top
    if drawing.get("simplePos") in ("1", "true") and drawing.find("wp:simplePos", NS) is not None:
        simple = drawing.find("wp:simplePos", NS)
        return int(simple.get("x", 0)) / EMU - section.left, page + int(simple.get("y", 0)) / EMU - section.top

    def place(tag: str, frames: dict, default: str) -> float:
        pos = drawing.find(f"wp:{tag}", NS)
        if pos is None:
            return frames[default][0]
        start, size = frames.get(pos.get("relativeFrom", default), frames[default])
        own = width if tag == "positionH" else height
        offset = pos.find("wp:posOffset", NS)
        if offset is not None and offset.text:
            return start + int(offset.text) / EMU
        align = (pos.findtext("wp:align", default="", namespaces=NS) or "").strip()
        if align in ("center",):
            return start + (size - own) / 2
        if align in ("right", "bottom", "outside"):
            return start + size - own
        return start

    s = section
    x = place("positionH", {"column": (0.0, s.text_width), "margin": (0.0, s.text_width),
                            "character": (0.0, s.text_width), "page": (-s.left, s.width),
                            "leftMargin": (-s.left, s.left), "insideMargin": (-s.left, s.left),
                            "rightMargin": (s.text_width, s.right), "outsideMargin": (s.text_width, s.right)},
              "column")
    y = place("positionV", {"paragraph": (top, 0.0), "line": (top, 0.0), "page": (page - s.top, s.height),
                            "margin": (page, s.body_height), "topMargin": (page - s.top, s.top),
                            "insideMargin": (page - s.top, s.top),
                            "bottomMargin": (page + s.body_height, s.bottom),
                            "outsideMargin": (page + s.body_height, s.bottom)},
              "paragraph")
    return x, y


def _drawings(body, flow: _Flow) -> list[tuple[int, etree._Element]]:
    """(index of the body element holding it, wp:anchor or wp:inline) for each drawing that has shapes."""
    host = {id(e): i for i, e in enumerate(flow.elements)}
    out = []
    for drawing in body.iter("{%s}anchor" % NS["wp"], "{%s}inline" % NS["wp"]):
        if any(True for _ in drawing.iterancestors("{%s}Fallback" % NS["mc"], W + "txbxContent")):
            continue            # the old-format copy of a shape, or a shape inside a text box
        data = drawing.find("a:graphic/a:graphicData", NS)
        if data is None or not len(data) or etree.QName(data[0]).localname not in ("wsp", "wgp", "wpc"):
            continue
        index = next((host[id(a)] for a in drawing.iterancestors() if id(a) in host), None)
        if index is not None:
            out.append((index, drawing))
    return out


def _place(drawings, flow: _Flow, scale: float) -> list[Shape]:
    tops, pages = flow.layout(scale)
    shapes: list[Shape] = []
    for n, (index, drawing) in enumerate(drawings):
        extent = drawing.find("wp:extent", NS)
        width, height = int(extent.get("cx", 0)) / EMU, int(extent.get("cy", 0)) / EMU
        x, y = _anchor_position(drawing, flow.sections[index], tops[index], pages[index], width, height,
                                flow.elements[index])
        content = drawing.find("a:graphic/a:graphicData", NS)[0]
        kind = etree.QName(content).localname
        outer_id = _attr(drawing, "wp:docPr", "id")
        if kind == "wsp":
            shapes.append(_shape(content, (x, y, width, height), f"d{n}", n, False, outer_id))
        elif kind == "wgp":
            _group(content, (x, y, width, height), n, f"d{n}", shapes)
        else:                                               # a drawing canvas: children in EMU from its corner
            _children(content, (x, y, 1 / EMU, 1 / EMU), n, f"d{n}", shapes)
    return shapes


# ---------------------------------------------------------------------------------------------------
# Joining arrows to boxes
# ---------------------------------------------------------------------------------------------------

def _gap(point, box) -> float:
    """How far a point is from a box's edge (inside a box counts too: an end deep inside a frame is not on it)."""
    x, y = point
    x0, y0, x1, y1 = box
    if x0 <= x <= x1 and y0 <= y <= y1:
        return min(x - x0, x1 - x, y - y0, y1 - y)
    dx, dy = max(x0 - x, 0, x - x1), max(y0 - y, 0, y - y1)
    return math.hypot(dx, dy)


def _area(box) -> float:
    return max(box[2] - box[0], 0.1) * max(box[3] - box[1], 0.1)


def _nearest(point, boxes: list[Shape]) -> tuple[Shape | None, float]:
    best, best_gap = None, math.inf
    for shape in boxes:
        gap = _gap(point, shape.box)
        smaller = best is not None and _area(shape.box) < _area(best.box)
        if gap < best_gap - 0.5 or (abs(gap - best_gap) <= 0.5 and smaller):     # a tie: the inner box
            best, best_gap = shape, gap
    return best, best_gap


def _score(shapes: list[Shape]) -> tuple[int, float]:
    boxes = [s for s in shapes if not s.is_line]
    touching, total = 0, 0.0
    for line in (s for s in shapes if s.is_line):
        for end in line.ends:
            _, gap = _nearest(end, boxes)
            touching += gap <= _TOUCH
            total += min(gap, 40.0)
    return touching, -total


def _segment_gap(point, a, b) -> float:
    (px, py), (ax, ay), (bx, by) = point, a, b
    dx, dy = bx - ax, by - ay
    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _line_gap(point, line: Shape) -> float:
    """Distance from a point to a line: straight, or either elbow route for a bent connector."""
    a, b = line.ends
    routes = [[a, b], [a, (b[0], a[1]), b], [a, (a[0], b[1]), b]]
    return min(min(_segment_gap(point, p, q) for p, q in zip(route, route[1:])) for route in routes)


def _centre(box) -> tuple[float, float]:
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


def _overlap(inner, outer) -> float:
    """Share of `inner`'s area that lies inside `outer`."""
    w = min(inner[2], outer[2]) - max(inner[0], outer[0])
    h = min(inner[3], outer[3]) - max(inner[1], outer[1])
    return max(w, 0) * max(h, 0) / _area(inner)


def _name(shape: Shape) -> str:
    """How a box is named in an arrow: all its text when short, else its first line."""
    text = shape.text or f"(empty {shape.prst} shape)"
    if len(text) <= 60:
        return text
    first = " ".join(next((p for p in shape.texts if p.strip()), "").split()).rstrip(":")
    return first if len(first) <= 60 else first[:57].rstrip() + "…"


def _flow_order(boxes: list[Shape], edges: list[tuple[Shape, Shape, str, str]]) -> list[Shape]:
    """Boxes in the order the arrows visit them, starting from the boxes nothing points to (top first)."""
    where = {b.key: (round(b.box[1] / 6), b.box[0]) for b in boxes}
    nexts: dict[str, list[Shape]] = defaultdict(list)
    incoming = set()
    for a, b, _, _ in edges:
        nexts[a.key].append(b)
        incoming.add(b.key)
    order: list[Shape] = []
    seen: set[str] = set()
    for start in sorted(boxes, key=lambda b: (b.key in incoming, where[b.key])):
        queue = [start]
        while queue:
            box = queue.pop(0)
            if box.key in seen:
                continue
            seen.add(box.key)
            order.append(box)
            queue += sorted(nexts[box.key], key=lambda b: where[b.key])
    return order


def _describe(boxes: list[Shape], stages: list[Shape], edges: list[tuple[Shape, Shape, str, str]]) -> str:
    rows = _flow_order(boxes, edges)
    lines = [HEADER]
    staged: dict[str, list[Shape]] = defaultdict(list)
    for box in rows:
        cy = _centre(box.box)[1]
        stage = next((st for st in stages if st.box[1] - 5 <= cy <= st.box[3] + 5), None)
        staged[stage.key if stage else ""].append(box)
    for box in staged.get("", []):
        lines.append(f"- {box.text or _name(box)}")
    for stage in sorted(stages, key=lambda s: s.box[1]):
        if staged.get(stage.key):
            lines.append(f"{stage.text}:")
            lines.extend(f"- {box.text or _name(box)}" for box in staged[stage.key])
    lines.append("Arrows:")
    order = {box.key: i for i, box in enumerate(rows)}
    for src, dst, arrow, label in sorted(edges, key=lambda e: (order[e[0].key], order[e[1].key])):
        lines.append(f"- {_name(src)} {arrow} {_name(dst)}" + (f" [{label}]" if label else ""))
    return "\n".join(lines)


def _build(shapes: list[Shape]) -> list[Flowchart]:
    lines = [s for s in shapes if s.is_line]
    boxes = [s for s in shapes if not s.is_line]
    # A text box laid over an empty shape (words typed on a diamond) gives that shape its words.
    # An empty shape with several text boxes in it is a frame or a background, not a labelled shape.
    for plain in [b for b in boxes if not b.text]:
        cover = [b for b in boxes if b.text and b is not plain and _overlap(b.box, plain.box) >= 0.6]
        if len(cover) == 1 and 0.15 <= _area(cover[0].box) / _area(plain.box) <= 1.2:
            plain.texts = cover[0].texts
            boxes.remove(cover[0])
    by_id = {i: b for b in boxes for i in b.ids}
    edges: list[tuple[Shape, Shape, Shape]] = []            # from, to, the line
    loose = 0
    for line in lines:
        ends = []
        for end, glued in zip(line.ends, line.glue):
            shape = by_id.get(glued) if glued else None
            if shape is None:
                shape, gap = _nearest(end, boxes)
                shape = shape if gap <= _TOUCH else None
            ends.append(shape)
        start, end = ends
        if start is None or end is None or start is end:
            loose += 1
            continue
        head_start, head_end = line.heads
        if head_start and not head_end:
            start, end = end, start
        edges.append((start, end, line))
    # A short text box lying on an arrow is that arrow's label ("Yes", "No").
    joined = {s.key for a, b, _ in edges for s in (a, b)}
    labels: dict[str, list[Shape]] = defaultdict(list)       # line -> the text boxes labelling it
    for box in [b for b in boxes if b.text and b.key not in joined and len(b.text.split()) <= _LABEL_WORDS]:
        near = [(_line_gap(_centre(box.box), line), line) for _, _, line in edges]
        near = [(gap, line) for gap, line in near if gap <= _LABEL_REACH]
        if near:
            labels[min(near, key=lambda gl: gl[0])[1].key].append(box)
            boxes.remove(box)
    # Boxes joined by arrows, or drawn in one group or canvas, are one flowchart.
    parent = {b.key: b.key for b in boxes}

    def root(k: str) -> str:
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k
    for a, b, _ in edges:
        parent[root(a.key)] = root(b.key)
    grouped: dict[int, list[Shape]] = defaultdict(list)
    for b in boxes:
        if b.grouped:
            grouped[b.drawing].append(b)
    for members in grouped.values():
        for b in members[1:]:
            parent[root(b.key)] = root(members[0].key)
    charts: dict[str, list[Shape]] = defaultdict(list)
    for b in boxes:
        charts[root(b.key)].append(b)
    with_arrows = {root(a.key) for a, _, _ in edges}
    out: list[Flowchart] = []
    taken: set[str] = set()
    for key in sorted(with_arrows, key=lambda k: min(b.box[1] for b in charts[k])):
        members = charts[key]
        x0 = min(b.box[0] for b in members) - _SIDE
        y0 = min(b.box[1] for b in members) - _SIDE
        x1 = max(b.box[2] for b in members) + _SIDE
        y1 = max(b.box[3] for b in members) + _SIDE
        # Loose boxes around it: a title above it, stage labels at its side, notes.
        extra = [b for b in boxes if b.text and root(b.key) not in with_arrows and b.key not in taken
                 and x0 <= _centre(b.box)[0] <= x1 and y0 <= _centre(b.box)[1] <= y1]
        members = members + extra
        taken.update(b.key for b in members)
        linked = {s.key for a, b, _ in edges for s in (a, b)}
        stages = [b for b in members if b.key not in linked and b.text
                  and (b.rotated or (b.box[3] - b.box[1]) > _STAGE_RATIO * (b.box[2] - b.box[0]))]
        nodes = [b for b in members if b not in stages and (b.text or b.key in linked)]
        mine = [(a, b, line) for a, b, line in edges if root(a.key) == key]
        arrows = []
        for a, b, line in mine:
            sign = "↔" if all(line.heads) else "—" if not any(line.heads) else "→"
            label = " ".join(filter(None, [line.text] + [box.text for box in labels[line.key]]))
            arrows.append((a, b, sign, label))
        used = members + [line for _, _, line in mine] + [box for _, _, line in mine for box in labels[line.key]]
        texts = [t for shape in used for t in shape.texts]
        out.append(Flowchart(text=_describe(nodes, stages, arrows), texts=texts, boxes=len(nodes),
                             arrows=len(arrows), loose_lines=loose))
    return out


def read_flowcharts(path: Path) -> list[Flowchart]:
    """Every flowchart drawn with Word shapes in the file, in reading order. [] when there is none."""
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            document = etree.fromstring(z.read("word/document.xml"))
            styles_xml = z.read("word/styles.xml") if "word/styles.xml" in names else None
            theme_xml = z.read("word/theme/theme1.xml") if "word/theme/theme1.xml" in names else None
    except (zipfile.BadZipFile, KeyError, etree.XMLSyntaxError, OSError):
        return []
    body = document.find("w:body", NS)
    if body is None or next(body.iter("{%s}wsp" % NS["wps"]), None) is None:
        return []                                       # no shapes at all: the usual case, and quick
    styles = _Styles(styles_xml, theme_xml)
    flow = _body_flow(body, styles)
    drawings = _drawings(body, flow)
    if not drawings:
        return []
    first = _place(drawings, flow, 1.0)
    if not any(s.is_line for s in first) or sum(not s.is_line for s in first) < 2:
        return []                                       # no arrows, or nothing for them to join
    best_scale, best = 1.0, _score(first)
    if len({index for index, _ in drawings}) > 1:       # loose shapes on different paragraphs: fit the estimate
        for scale in _SCALES:
            score = _score(_place(drawings, flow, scale))
            if score > best or (score == best and abs(scale - 1) < abs(best_scale - 1)):
                best_scale, best = scale, score
    shapes = _place(drawings, flow, best_scale)
    charts = _build(shapes)
    logger.debug("flowcharts: %d, line-height scale %.2f, arrow ends on a box %d", len(charts), best_scale, best[0])
    return charts
