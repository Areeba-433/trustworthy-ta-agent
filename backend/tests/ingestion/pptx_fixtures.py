"""Script-made PowerPoint decks for tests and measurements: one builder per case, nothing from real courses.

Every picture is drawn in memory with Pillow (shapes only, no words), every text is a made-up label from TEXTS, and
nothing is written to disk unless write_deck() or write_all() is asked to. Used by test_pptx_fixtures.py,
scripts/try_pptx.py and scripts/pptx_gap_check.py.

    python -m tests.ingestion.pptx_fixtures <folder>      # writes every deck into <folder>, prints the paths

TODO (SmartArt): python-pptx cannot create SmartArt, so there is no builder for it. A real fixture needs the
ppt/diagrams/data1.xml, layout1.xml, quickStyle1.xml and colors1.xml parts, plus a graphicFrame whose graphicData
uri is http://schemas.openxmlformats.org/drawingml/2006/diagram, injected by hand into a deck saved here. Do not
fake it with shapes: the point of the fixture is the diagram parts.
"""
from __future__ import annotations

import io
import sys
from collections.abc import Callable
from dataclasses import dataclass, fields
from pathlib import Path

from lxml import etree
from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE, MSO_SHAPE_TYPE
from pptx.oxml.ns import qn
from pptx.presentation import Presentation as Deck
from pptx.shapes.autoshape import Shape
from pptx.shapes.connector import Connector
from pptx.shapes.graphfrm import GraphicFrame
from pptx.shapes.group import GroupShape
from pptx.shapes.picture import Picture
from pptx.slide import Slide
from pptx.util import Inches, Pt

LAYOUT = {"title": 0, "content": 1, "title_only": 5, "blank": 6}      # python-pptx's default template
PICTURE_PX = (640, 360)       # a normal pasted picture
LOGO_PX = (200, 80)           # big enough to pass a 64 px size rule: only the repeated-hash rule catches it
ICON_PX = (32, 32)            # under 64 px: junk by size
RECTANGLE_RIGHT, RECTANGLE_LEFT = 3, 1   # connection points on a rectangle: 0 top, 1 left, 2 bottom, 3 right
LOOSE_SHAPES = (MSO_SHAPE.OVAL, MSO_SHAPE.ISOSCELES_TRIANGLE, MSO_SHAPE.ROUNDED_RECTANGLE)

TEXTS = {                     # every string any deck contains; tests check none of them is ever printed
    "deck": "Fixture deck",
    "title": "Fixture slide title",
    "bullets": ["Point alpha", "Point beta", "Point beta detail", "Point gamma"],
    "notes": "Speaker note for the fixture slide",
    "caption": "Figure 1: Fixture diagram",
    "boxes": ["Box one", "Box two", "Box three"],
    "shapes": ["Shape one", "Shape two", "Shape three"],
    "grouped": ["Outer group text", "Inner group text", "Inner group more"],
    "table": [["Head A", "Head B", "Head C"], ["Cell A1", "Cell B1", "Cell C1"], ["Cell A2", "Cell B2", "Cell C2"]],
    "chart": {"categories": ["Cat one", "Cat two", "Cat three"], "series": ["Series one", "Series two"]},
    "loose": "Only a text box",
    "order": ["Order first", "Order second", "Order third"],
    "box_titles": {"first": "Fixture text box title", "body": "Body sentence under the text box title",
                   "symbol": "\u2605", "kicker": "FIXTURE KICKER LABEL", "second": "Second fixture slide title",
                   "formula": "Fixture formula line", "body2": "Second body sentence for the fixture"},
    "layout": {
        "sections": ["FIXTURE SECTION ONE", "FIXTURE SECTION TWO"],
        "titles": ["Fixture cells slide", "Fixture columns slide", "Fixture cards slide", "Fixture code slide",
                   "Fixture map slide", "Fixture boards slide"],
        "footers": ["Fixture course footer | Part alpha", "Fixture course footer | Part beta",
                    "Fixture course footer | Part gamma"],
        "counters": ["1 / 6", "2 / 6", "3 / 6", "4 / 6", "5 / 6", "6 / 6"],
        "row_label": "Fixture input row", "cells": ["41", "17", "58", "6", "23", "90"],
        "under": "Fixture sentence under the cells",
        "halves": ["Fixture left half", "Fixture right half"],
        "pairs": ["[41, 17]", "[58, 6]", "[23, 90]", "[3, 12]"],
        "columns_note": "Fixture sentence under the columns",
        "cases": ["Fixture case one", "Fixture case two", "Fixture case three"],
        "values": ["Fixture value one", "Fixture value two", "Fixture value three"],
        "code": ["FIXTURE_PROC(a, b):", "    if a > b:", "        return a", "", "    return b"],
        "mono": "fixture_call(41, 17)",
        "nodes": ["Fixture node A", "Fixture node B", "Fixture node C"], "node_numbers": ["77", "35", "120"],
        "panel": ["FIXTURE STEP ONE", "Fixture panel sentence one", "Fixture panel sentence two"],
        "boards": ["Fixture board one", "Fixture board two"],
        "tiles": [["11", "12", "13", "14"], ["21", "22", "23", "24"]],
    },
}


def all_texts() -> set[str]:
    """Every worded string written into any fixture deck, flattened. Numbers alone ("41", "2 / 6") and empty lines
    are left out: they say nothing about a course, and the numeric summaries print digits of their own."""
    found: set[str] = set()

    def walk(value: object) -> None:
        if isinstance(value, str):
            if any(c.isalpha() for c in value):
                found.add(value)
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(TEXTS)
    return found


# ================================================================ pictures and small helpers

def picture_png(size: tuple[int, int] = PICTURE_PX, seed: int = 0) -> bytes:
    """A wordless diagram-like picture: rectangles and a line. `seed` changes it, so hashes differ."""
    width, height = size
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((width // 10, height // 4, width // 2 - 4, 3 * height // 4), outline="black", width=3)
    draw.rectangle((width // 2 + 4, height // 4, 9 * width // 10, 3 * height // 4), outline=(seed * 40 % 256, 0, 0),
                   width=3)
    draw.line((width // 2 - 4, height // 2, width // 2 + 4, height // 2), fill="black", width=3)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def _new_deck() -> Deck:
    return Presentation()


def _slide(deck: Deck, layout: str, title: str | None = None) -> Slide:
    slide = deck.slides.add_slide(deck.slide_layouts[LAYOUT[layout]])
    if title is not None:
        slide.shapes.title.text = title
    return slide


def _picture(slide: Slide, png: bytes, left: float = 1.0, top: float = 1.8, width: float = 5.0) -> Picture:
    return slide.shapes.add_picture(io.BytesIO(png), Inches(left), Inches(top), Inches(width))


def _textbox(shapes, text: str, left: float, top: float, width: float = 4.0, height: float = 0.6):
    box = shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    box.text_frame.text = text
    return box


def _arrowhead(connector: Connector) -> None:
    """python-pptx has no API for arrowheads: add <a:tailEnd type="triangle"/> to the line."""
    line = connector.line._get_or_add_ln()
    etree.SubElement(line, qn("a:tailEnd"), type="triangle")


# ================================================================ one slide per case (added to an existing deck)

def add_title_bullets(deck: Deck) -> Slide:
    slide = _slide(deck, "content", TEXTS["title"])
    frame = slide.placeholders[1].text_frame
    for i, (text, level) in enumerate(zip(TEXTS["bullets"], (0, 0, 1, 0))):
        paragraph = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
        paragraph.text, paragraph.level = text, level
    return slide


def add_with_notes(deck: Deck) -> Slide:
    slide = _slide(deck, "content", TEXTS["title"])
    slide.placeholders[1].text_frame.text = TEXTS["bullets"][0]
    slide.notes_slide.notes_text_frame.text = TEXTS["notes"]
    return slide


def add_picture_only(deck: Deck) -> Slide:
    slide = _slide(deck, "title_only", TEXTS["title"])
    _picture(slide, picture_png(seed=1))
    return slide


def add_picture_caption(deck: Deck) -> Slide:
    slide = _slide(deck, "blank")
    _picture(slide, picture_png(seed=2), top=1.0)
    _textbox(slide.shapes, TEXTS["caption"], left=1.0, top=4.0)
    return slide


def add_flowchart(deck: Deck) -> Slide:
    """Three boxes joined by two connectors glued to their edges (begin_connect / end_connect)."""
    slide = _slide(deck, "title_only", TEXTS["title"])
    boxes = []
    for i, text in enumerate(TEXTS["boxes"]):
        box = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.5 + 3.2 * i), Inches(3), Inches(2.2), Inches(1))
        box.text_frame.text = text
        boxes.append(box)
    for start, end in zip(boxes, boxes[1:]):
        connector = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, 0, 0, Inches(1), Inches(1))
        connector.begin_connect(start, RECTANGLE_RIGHT)
        connector.end_connect(end, RECTANGLE_LEFT)
        _arrowhead(connector)
    return slide


def add_loose_shapes(deck: Deck) -> Slide:
    slide = _slide(deck, "title_only", TEXTS["title"])
    for i, (kind, text) in enumerate(zip(LOOSE_SHAPES, TEXTS["shapes"])):
        shape = slide.shapes.add_shape(kind, Inches(0.8 + 3 * i), Inches(2.5 + 0.4 * i), Inches(2), Inches(1.4))
        shape.text_frame.text = text
    return slide


def add_grouped(deck: Deck) -> Slide:
    """A group holding a text box and a second group with two more text boxes: two levels deep."""
    slide = _slide(deck, "title_only", TEXTS["title"])
    outer = slide.shapes.add_group_shape()
    _textbox(outer.shapes, TEXTS["grouped"][0], left=1.0, top=2.0)
    inner = outer.shapes.add_group_shape()
    _textbox(inner.shapes, TEXTS["grouped"][1], left=1.5, top=3.0)
    _textbox(inner.shapes, TEXTS["grouped"][2], left=1.5, top=3.8)
    return slide


def add_table(deck: Deck) -> Slide:
    slide = _slide(deck, "title_only", TEXTS["title"])
    table = slide.shapes.add_table(3, 3, Inches(1), Inches(2), Inches(7), Inches(2)).table
    for r, row in enumerate(TEXTS["table"]):
        for c, text in enumerate(row):
            table.cell(r, c).text = text
    return slide


def add_chart(deck: Deck) -> Slide:
    slide = _slide(deck, "title_only", TEXTS["title"])
    data = CategoryChartData()
    data.categories = TEXTS["chart"]["categories"]
    for i, name in enumerate(TEXTS["chart"]["series"]):
        data.add_series(name, (3 + i, 5 - i, 4))
    slide.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(1), Inches(1.8), Inches(7), Inches(4.5), data)
    return slide


def add_no_title(deck: Deck) -> Slide:
    slide = _slide(deck, "blank")
    _textbox(slide.shapes, TEXTS["loose"], left=1.0, top=2.0)
    return slide


def add_empty_slide(deck: Deck) -> Slide:
    return _slide(deck, "blank")


def add_hidden_slide(deck: Deck) -> Slide:
    slide = add_with_notes(deck)
    slide._element.set("show", "0")
    return slide


def add_tiny_icon(deck: Deck) -> Slide:
    slide = _slide(deck, "title_only", TEXTS["title"])
    _picture(slide, picture_png(ICON_PX, seed=3), left=8.5, top=0.3, width=0.4)
    return slide


def add_reading_order(deck: Deck) -> Slide:
    """Three text boxes added bottom, top, middle, but placed top to bottom on the slide."""
    slide = _slide(deck, "blank")
    for index in (2, 0, 1):
        _textbox(slide.shapes, TEXTS["order"][index], left=1.0, top=1.5 + 1.5 * index)
    return slide


def _sized_box(slide: Slide, text: str, top: float, points: int, on_paragraph: bool, left: float = 0.6) -> None:
    """A text box whose font size is set on the paragraph (a:pPr/a:defRPr) or on the run (a:rPr)."""
    paragraph = _textbox(slide.shapes, text, left=left, top=top, width=8.5, height=0.8).text_frame.paragraphs[0]
    font = paragraph.font if on_paragraph else paragraph.runs[0].font
    font.size = Pt(points)


def add_text_box_titles(deck: Deck) -> list[Slide]:
    """Two slides titled with plain text boxes, no title placeholder, as two of three real decks are.

    Slide 1 sets sizes on the paragraph (29 pt title, 18 pt body). Slide 2 sets them on the runs: a 12 pt kicker
    above a 28 pt title, a bigger 30 pt formula line below it, a 14 pt body and a 90 pt star with no words.
    """
    texts = TEXTS["box_titles"]
    first, second = _slide(deck, "blank"), _slide(deck, "blank")
    _sized_box(first, texts["first"], top=0.3, points=29, on_paragraph=True)
    _sized_box(first, texts["body"], top=1.6, points=18, on_paragraph=True)
    _sized_box(second, texts["symbol"], top=0.2, points=90, on_paragraph=False, left=0.1)
    _sized_box(second, texts["kicker"], top=0.3, points=12, on_paragraph=False)
    _sized_box(second, texts["second"], top=0.7, points=28, on_paragraph=False)
    _sized_box(second, texts["formula"], top=2.6, points=30, on_paragraph=False)
    _sized_box(second, texts["body2"], top=4.2, points=14, on_paragraph=False)
    return [first, second]


def _text_at(slide: Slide, lines: str | list[str], left: float, top: float, width: float, height: float,
             points: int, font: str | None = None) -> None:
    """A text box at an exact place, one paragraph per line, each run at `points` (and in `font` if given)."""
    frame = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height)).text_frame
    for i, line in enumerate([lines] if isinstance(lines, str) else lines):
        paragraph = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
        paragraph.text = line
        for run in paragraph.runs:
            run.font.size = Pt(points)
            if font is not None:
                run.font.name = font


def _cell(slide: Slide, text: str, left: float, top: float, width: float, height: float) -> None:
    """A rounded box holding one short text, as slides draw array cells, cards and board squares."""
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width),
                                   Inches(height))
    shape.text_frame.text = text
    shape.text_frame.paragraphs[0].runs[0].font.size = Pt(16)


def add_slide_layout(deck: Deck) -> list[Slide]:
    """Six slides whose meaning depends on where things stand (blank layout, 28 pt titles in text boxes).

    Every slide has a footer whose last words change by section, at the same place, and a slide counter. Slides 1-2
    and 3-4 have a section label above the title. 1: a label over a row of number cells, a sentence under them.
    2: two halves, each a label over two boxes. 3: three cards, a case over its value. 4: pseudocode indented with
    spaces, no fixed-width font, and one line in Courier New. 5: a map of labelled nodes with numbers beside them,
    and a step panel to its right. 6: two boards of number squares side by side, each under its label.
    """
    texts = TEXTS["layout"]
    slides = [_slide(deck, "blank") for _ in range(6)]
    for n, slide in enumerate(slides):
        if n < 4:
            _text_at(slide, texts["sections"][n // 2], 0.6, 0.15, 8.5, 0.3, 11)
        _text_at(slide, texts["titles"][n], 0.6, 0.5, 8.5, 0.7, 28)
        _text_at(slide, texts["footers"][n // 2], 0.4, 7.0, 6.0, 0.3, 10)
        _text_at(slide, texts["counters"][n], 9.0, 7.0, 0.7, 0.3, 10)
    cells, columns, cards, code, chart, boards = slides
    _text_at(cells, texts["row_label"], 0.6, 1.4, 3.0, 0.4, 16)
    for i, number in enumerate(texts["cells"]):
        _cell(cells, number, 0.6 + 1.4 * i, 2.0, 1.1, 0.8)
    _text_at(cells, texts["under"], 0.6, 3.6, 8.5, 0.6, 16)
    for side, left in enumerate((0.6, 5.4)):
        _text_at(columns, texts["halves"][side], left + 0.4, 1.5, 3.0, 0.4, 16)
        for k in range(2):
            _cell(columns, texts["pairs"][2 * side + k], left + 2.0 * k, 2.2, 1.8, 0.7)
    _text_at(columns, texts["columns_note"], 0.8, 4.2, 8.4, 0.8, 16)
    for i in range(3):
        _cell(cards, texts["cases"][i], 0.6 + 3.0 * i, 1.6, 2.6, 0.6)
        _cell(cards, texts["values"][i], 0.6 + 3.0 * i, 2.4, 2.6, 0.9)
    _text_at(code, texts["code"], 0.6, 1.5, 6.0, 2.4, 14)
    _text_at(code, texts["mono"], 0.6, 4.2, 6.0, 0.6, 14, font="Courier New")
    for (left, top), node in zip(((0.4, 1.9), (2.4, 3.0), (1.0, 4.4)), texts["nodes"]):
        _text_at(chart, node, left, top, 1.8, 0.35, 14)
    for (left, top, height), number in zip(((2.2, 1.5, 0.4), (0.5, 3.5, 0.3), (3.0, 4.6, 0.4)),
                                           texts["node_numbers"]):
        _text_at(chart, number, left, top, 0.5, height, 12)
    for (top, height), line in zip(((1.5, 0.4), (2.1, 0.9), (3.3, 0.9)), texts["panel"]):
        _text_at(chart, line, 6.2, top, 3.2, height, 14)
    for b, left in enumerate((0.8, 4.8)):
        _text_at(boards, texts["boards"][b], left, 1.4, 3.0, 0.4, 16)
        for k, number in enumerate(texts["tiles"][b]):
            _cell(boards, number, left + 0.8 * (k % 2), 2.0 + 0.8 * (k // 2), 0.7, 0.7)
    return slides


def add_logo(slide: Slide) -> Picture:
    """The same small picture in the same corner: template decoration."""
    return _picture(slide, picture_png(LOGO_PX, seed=9), left=8.3, top=0.2, width=1.4)


# ================================================================ decks

def _single(add: Callable[[Deck], Slide]) -> Callable[[], Deck]:
    def build() -> Deck:
        deck = _new_deck()
        add(deck)
        return deck
    return build


def build_repeated_logo() -> Deck:
    deck = _new_deck()
    for _ in range(4):
        add_logo(add_with_notes(deck))
    return deck


MIXED_SLIDES = [               # (fixture cases covered, builder); 8 slides, the logo on slides 1-7
    ("title_bullets+with_notes", lambda deck: _with_note(add_title_bullets(deck))),
    ("picture_only+tiny_icon", lambda deck: _with_icon(add_picture_only(deck))),
    ("picture_caption", add_picture_caption),
    ("flowchart", add_flowchart),
    ("grouped", add_grouped),
    ("table+hidden_slide", lambda deck: _hidden(add_table(deck))),
    ("chart+loose_shapes", lambda deck: _with_loose_shapes(add_chart(deck))),
    ("no_title+reading_order", add_reading_order),
]


def _with_note(slide: Slide) -> Slide:
    slide.notes_slide.notes_text_frame.text = TEXTS["notes"]
    return slide


def _with_icon(slide: Slide) -> Slide:
    _picture(slide, picture_png(ICON_PX, seed=3), left=8.5, top=6.5, width=0.4)
    return slide


def _hidden(slide: Slide) -> Slide:
    slide._element.set("show", "0")
    return slide


def _with_loose_shapes(slide: Slide) -> Slide:
    for i, (kind, text) in enumerate(zip(LOOSE_SHAPES, TEXTS["shapes"])):
        shape = slide.shapes.add_shape(kind, Inches(0.3 + 3.2 * i), Inches(6.4), Inches(1.6), Inches(0.8))
        shape.text_frame.text = text
        shape.text_frame.paragraphs[0].runs[0].font.size = Pt(10)
    return slide


def build_mixed_deck() -> Deck:
    deck = _new_deck()
    for i, (_, add) in enumerate(MIXED_SLIDES):
        slide = add(deck)
        if i < len(MIXED_SLIDES) - 1:
            add_logo(slide)
    return deck


BUILDERS: dict[str, Callable[[], Deck]] = {
    "title_bullets": _single(add_title_bullets),
    "with_notes": _single(add_with_notes),
    "picture_only": _single(add_picture_only),
    "picture_caption": _single(add_picture_caption),
    "flowchart": _single(add_flowchart),
    "loose_shapes": _single(add_loose_shapes),
    "grouped": _single(add_grouped),
    "table": _single(add_table),
    "chart": _single(add_chart),
    "no_title": _single(add_no_title),
    "empty_slide": _single(add_empty_slide),
    "hidden_slide": _single(add_hidden_slide),
    "repeated_logo": build_repeated_logo,
    "tiny_icon": _single(add_tiny_icon),
    "reading_order": _single(add_reading_order),
    "mixed_deck": build_mixed_deck,
    "text_box_titles": _single(add_text_box_titles),
    "slide_layout": _single(add_slide_layout),
}


def deck_bytes(name: str) -> bytes:
    buffer = io.BytesIO()
    BUILDERS[name]().save(buffer)
    return buffer.getvalue()


def write_deck(name: str, folder: Path | str) -> Path:
    path = Path(folder) / f"{name}.pptx"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(deck_bytes(name))
    return path


def write_all(folder: Path | str) -> dict[str, Path]:
    return {name: write_deck(name, folder) for name in BUILDERS}


# ================================================================ what python-pptx sees in a deck

@dataclass(frozen=True)
class Census:
    slides: int = 0
    pictures: int = 0         # Picture shapes, inside groups and placeholders too
    connectors: int = 0
    glued_ends: int = 0       # connector ends attached to a shape (stCxn / endCxn)
    autoshapes: int = 0       # drawn shapes: rectangles, ovals...; not text boxes or placeholders
    textboxes: int = 0
    groups: int = 0           # every group, nested ones included
    tables: int = 0
    charts: int = 0
    notes: int = 0            # slides whose speaker notes hold text
    hidden: int = 0


def _shapes(shapes) -> list:
    found = []
    for shape in shapes:
        found.append(shape)
        if isinstance(shape, GroupShape):
            found += _shapes(shape.shapes)
    return found


def census(deck: Deck) -> Census:
    counts = {f.name: 0 for f in fields(Census)}
    for slide in deck.slides:
        counts["slides"] += 1
        counts["hidden"] += slide._element.get("show") == "0"
        notes = slide.notes_slide.notes_text_frame if slide.has_notes_slide else None
        counts["notes"] += bool(notes is not None and notes.text.strip())
        for shape in _shapes(slide.shapes):
            if isinstance(shape, Picture):
                counts["pictures"] += 1
            elif isinstance(shape, Connector):
                counts["connectors"] += 1
                counts["glued_ends"] += sum(shape._element.find(f".//{qn(tag)}") is not None
                                            for tag in ("a:stCxn", "a:endCxn"))
            elif isinstance(shape, GroupShape):
                counts["groups"] += 1
            elif isinstance(shape, GraphicFrame):
                counts["tables"] += shape.has_table
                counts["charts"] += shape.has_chart
            elif isinstance(shape, Shape) and shape.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE:
                counts["autoshapes"] += 1
            elif isinstance(shape, Shape) and shape.shape_type == MSO_SHAPE_TYPE.TEXT_BOX:
                counts["textboxes"] += 1
    return Census(**counts)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m tests.ingestion.pptx_fixtures <folder>")
    for fixture, written in write_all(sys.argv[1]).items():
        print(f"{fixture:<16} {written}")