"""Where a slide's blocks stand on the slide: the PowerPoint loader's layout rules, on Docling's own boxes.

Docling reads a slide in rows: it sorts shapes by their top edge and reads left to right within a row (0.05 inch
tolerance). That suits one column and mixes side-by-side layouts: the label row of three cards came before all three
values, and a map on the left was read into the step panel beside it. Every block keeps its Docling id in
extra["ref"], and Docling gives each shape's box (EMU, from the slide's top-left corner), so here:
- drop_position_footers(): a thin text at the same place at the bottom of most slides is a footer, even when its
  words change from slide to slide (one real deck adds the topic: "... | Topic 9 · What Is a Heuristic?");
- code_blocks(): a shape in a fixed-width font (the PDF loader's rule too), or whose lines are indented like code,
  becomes one code block with its line breaks and indentation, which Docling keeps and to_blocks() cleans away;
- number_cells(): numbers in a row of boxes (an array drawn as cells) become one line. The shared cleaner drops a
  text that is only a number, as it would a page number; a lone number, such as a slide counter, stays dropped;
- reading_order(): each slide is cut along its widest empty band, across or down, and again inside each part (the
  recursive XY-cut), then read part by part, so a card's label stays with its value;
- section_labels(): a short label above the title, repeated on neighbouring slides ("TOPIC 9 · ..."), moves into
  the heading path between the deck and the slide title;
- mark_figures(): each picture's place, extra["figure"] = {"page": slide, "box": [left, top, right, bottom]} as
  fractions of the slide from its top-left corner: the note the PDF loader writes, so one images step serves both.
Slide notes never move: they stay at the end of their slide. Nothing here reads the file again.
"""
from __future__ import annotations

import re
import textwrap
from collections import defaultdict
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any

from app.ingestion.cleaning.common import clean_text, detect_lang
from app.ingestion.contract import Block, Location

Box = tuple[float, float, float, float]      # left, top, right, bottom, in EMU from the slide's top-left corner

FOOTER_BAND = 0.85          # a footer starts in the bottom 15% of the slide
FOOTER_HEIGHT = 0.08        # and is at most 8% of the slide high: one line, not a box of content
MIN_GAP = 0.004             # an empty band this wide (share of the slide) separates two parts of a slide
ROW_TOLERANCE = 45720       # EMU (0.05 inch, Docling's own): tops this close are one row
CELL_GAP = 1.5              # cells of one row stand at most 1.5 cell widths apart
LABEL_TOP = 0.3             # a section label stands in the top 30% of the slide
LABEL_MAX_WORDS = 10
INDENTED_LINES = 2          # without a fixed-width font: this many indented lines and one code-like line
CODE_LIKE = re.compile(r"[:{};]\s*$|\w\(|\s(?:==|<=|>=|!=|\+=|-=|=)\s|^\s*(?://|#)")
NUMBER = re.compile(r"\d{1,4}")
BODY, CELL_LABELS = "body", {"paragraph", "text"}


class Places:
    """Docling's box for each block, found through its id; a merged block covers each id in extra["merged_from"]."""

    def __init__(self, doc: Any) -> None:
        self.items = {item.self_ref: item for item in [*doc.texts, *doc.tables, *doc.pictures]}
        self.sizes = {n: (page.size.width or 1.0, page.size.height or 1.0) for n, page in doc.pages.items()}

    def of_item(self, item: Any) -> Box | None:
        if item is None or not getattr(item, "prov", None):
            return None
        box = item.prov[0].bbox                      # Docling tags PowerPoint boxes TOPLEFT: t is the top edge
        return box.l, min(box.t, box.b), box.r, max(box.t, box.b)

    def of(self, block: Block) -> Box | None:
        boxes = [b for b in (self.of_item(self.items.get(ref)) for ref in refs(block)) if b is not None]
        return _union(boxes) if boxes else None

    def size(self, slide: int) -> tuple[float, float]:
        return self.sizes.get(slide, (1.0, 1.0))


def refs(block: Block) -> list[str]:
    return list(block.extra.get("merged_from") or [block.extra.get("ref")])


def slides(blocks: Sequence[Block]) -> Iterator[tuple[int, list[Block]]]:
    """The blocks slide by slide, in order (to_blocks() keeps each slide's blocks together)."""
    run: list[Block] = []
    for block in blocks:
        if run and block.loc.slide != run[0].loc.slide:
            yield run[0].loc.slide, run
            run = []
        run.append(block)
    if run:
        yield run[0].loc.slide, run


def insert(blocks: Sequence[Block], additions: Sequence[Block]) -> list[Block]:
    """Each new block goes at the end of its slide's content, before that slide's speaker notes."""
    out = list(blocks)
    for new in additions:
        slide = new.loc.slide
        notes = [i for i, b in enumerate(out) if b.loc.slide == slide and b.kind == "slide_notes"]
        out.insert(notes[0] if notes else sum(1 for b in out if b.loc.slide <= slide), new)
    return out


# ================================================================ footers by their place

def drop_position_footers(blocks: Sequence[Block], doc: Any) -> list[Block]:
    """Drop a thin paragraph at the same place at the bottom of more than half the slides with text (3 at least)."""
    places = Places(doc)
    where: dict[tuple[int, int], set[int]] = defaultdict(set)
    keys: dict[int, tuple[int, int]] = {}
    for i, block in enumerate(blocks):
        key = _footer_key(block, places)
        if key is not None:
            keys[i] = key
            where[key].add(block.loc.slide)
    with_text = len({b.loc.slide for b in blocks})
    footers = {key for key, on in where.items() if len(on) >= 3 and 2 * len(on) > with_text}
    return [b for i, b in enumerate(blocks) if keys.get(i) not in footers]


def _footer_key(block: Block, places: Places) -> tuple[int, int] | None:
    box = places.of(block) if block.kind == "paragraph" else None
    if box is None:
        return None
    width, height = places.size(block.loc.slide)
    if box[1] < FOOTER_BAND * height or box[3] - box[1] > FOOTER_HEIGHT * height:
        return None
    return round(100 * box[0] / width), round(100 * box[1] / height)


# ================================================================ code

def code_blocks(blocks: Sequence[Block], doc: Any, monospace: set[tuple[int, tuple[int, ...]]]) -> list[Block]:
    """Each run of paragraphs from one shape that is code becomes one code block, lines and indentation kept.

    `monospace` holds (slide, (left, top, width, height)) of each shape in a fixed-width font, from _pptx_shapes.
    The block keeps the first paragraph's place; extra["merged_from"] lists every paragraph's Docling id and
    extra["lines_from"] = "pptx_text" says where the lines came from, as the PDF loader's "pdf_text" does.
    """
    places, lines_of = Places(doc), _shape_lines(doc)
    out: list[Block] = []
    i = 0
    while i < len(blocks):
        first = blocks[i]
        box = places.of(first) if first.kind == "paragraph" else None
        j = i + 1
        while (box is not None and j < len(blocks) and blocks[j].kind == "paragraph"
               and blocks[j].loc.slide == first.loc.slide and places.of(blocks[j]) == box):
            j += 1
        run = blocks[i:j]
        if box is not None:
            lines = lines_of.get((first.loc.slide, box), [])
            if [line.strip() for line in lines if line.strip()] != [places.items[r].text.strip() for b in run
                                                                   for r in refs(b) if r in places.items]:
                lines = [places.items[r].text for b in run for r in refs(b) if r in places.items]
            emu = (int(box[0]), int(box[1]), int(box[2] - box[0]), int(box[3] - box[1]))
            if lines and is_code(lines, (first.loc.slide, emu) in monospace):
                out.append(_code_block(run, lines))
                i = j
                continue
        out.extend(run)
        i = j
    return out


def is_code(lines: Sequence[str], monospace: bool) -> bool:
    """A fixed-width font marks code. Without one: three lines or more, two of them indented, one code-like."""
    filled = [line for line in (_spaces(line) for line in lines) if line.strip()]
    if monospace:
        return bool(filled)
    indented = sum(1 for line in filled if len(line) - len(line.lstrip(" ")) >= 2)
    return len(filled) >= 3 and indented >= INDENTED_LINES and any(CODE_LIKE.search(line) for line in filled)


def code_text(lines: Sequence[str]) -> str:
    """The lines with their indentation, common indentation removed, one empty line at most between two."""
    kept: list[str] = []
    for line in (_spaces(line).rstrip() for line in lines):
        if line or (kept and kept[-1]):
            kept.append(line)
    while kept and not kept[-1]:
        kept.pop()
    return textwrap.dedent("\n".join(kept))


def _spaces(line: str) -> str:
    return line.replace("\u00a0", " ").replace("\v", " ").expandtabs(4)


def _shape_lines(doc: Any) -> dict[tuple[int, Box], list[str]]:
    """Every paragraph of each text shape, empty ones included, keyed by slide and box (Docling gives all the
    paragraphs of one shape that shape's box)."""
    places = Places(doc)
    lines: dict[tuple[int, Box], list[str]] = defaultdict(list)
    for item in doc.texts:
        box = places.of_item(item)
        if box is not None and str(getattr(item.content_layer, "value", item.content_layer)) == BODY:
            lines[(item.prov[0].page_no, box)].append(item.text or "")
    return lines


def _code_block(run: Sequence[Block], lines: Sequence[str]) -> Block:
    first = run[0]
    extra = {**first.extra, "lines_from": "pptx_text"}
    if len(run) > 1:
        extra["merged_from"] = [r for block in run for r in refs(block)]
    return first.model_copy(update={"kind": "code", "text": code_text(lines), "lang": "code", "extra": extra})


# ================================================================ numbers in cells

@dataclass(frozen=True)
class _Cell:
    box: Box
    text: str
    ref: str


def number_cells(blocks: Sequence[Block], doc: Any, title: str) -> list[Block]:
    """Rows of number cells, which the cleaner dropped, come back as one block per row, numbers left to right.

    A cell is a Docling paragraph of 1 to 4 digits that no block holds. Cells of about one height whose middles
    line up form a row; a row splits where two cells stand more than 1.5 cell widths apart (two boards side by
    side). A run of two cells or more is a row of data; a lone number (a slide counter, a value beside a map node)
    stays out. The block gets the slide's heading path and extra["origin"] = "number cells".
    """
    places = Places(doc)
    held = {r for block in blocks for r in refs(block)}
    cells: dict[int, list[_Cell]] = defaultdict(list)
    for item in doc.texts:
        text = (item.text or "").strip()
        box = places.of_item(item)
        layer = str(getattr(item.content_layer, "value", item.content_layer))
        label = str(getattr(item.label, "value", item.label))
        if (box is None or item.self_ref in held or layer != BODY or label not in CELL_LABELS
                or not NUMBER.fullmatch(text) or clean_text(text)):
            continue
        cells[item.prov[0].page_no].append(_Cell(box, text, item.self_ref))
    paths = {}
    for slide, here in slides(blocks):
        heading = next((b for b in here if b.kind == "heading"), None)
        paths[slide] = list(heading.heading_path) if heading else [here[0].heading_path[0]]
    added = [Block(seq=0, kind="paragraph", text=" ".join(c.text for c in run), loc=Location(slide=slide),
                   heading_path=paths.get(slide, [title]), lang=detect_lang(" ".join(c.text for c in run)),
                   extra={"ref": run[0].ref, "merged_from": [c.ref for c in run], "origin": "number cells"})
             for slide in sorted(cells) for run in cell_runs(cells[slide])]
    return insert(blocks, added)


def cell_runs(cells: Sequence[_Cell]) -> list[list[_Cell]]:
    """Runs of cells of one height, middles in line, at most 1.5 cell widths apart: three cells or more, or two
    with another run right above or below them (a board row with a blank square; two map values in line are not)."""
    rows: list[list[_Cell]] = []
    for cell in sorted(cells, key=lambda c: (_middle(c.box), c.box[0])):
        row = rows[-1] if rows else None
        height = cell.box[3] - cell.box[1]
        if row and abs(_middle(cell.box) - _middle(row[0].box)) <= height / 2 \
                and 2 / 3 <= height / max(row[0].box[3] - row[0].box[1], 1) <= 3 / 2:
            row.append(cell)
        else:
            rows.append([cell])
    runs: list[list[_Cell]] = []
    for row in rows:
        row.sort(key=lambda c: c.box[0])
        run = [row[0]]
        for before, cell in zip(row, row[1:]):
            widest = max(before.box[2] - before.box[0], cell.box[2] - cell.box[0])
            if cell.box[0] - before.box[2] <= CELL_GAP * widest:
                run.append(cell)
            else:
                runs.append(run)
                run = [cell]
        runs.append(run)
    runs = [run for run in runs if len(run) >= 2]
    return [run for run in runs if len(run) >= 3 or any(_stacked(run, other) for other in runs if other is not run)]


def _stacked(run: list[_Cell], other: list[_Cell]) -> bool:
    a, b = _union([c.box for c in run]), _union([c.box for c in other])
    height = a[3] - a[1]
    side_by_side = min(a[2], b[2]) > max(a[0], b[0])
    return side_by_side and max(b[1] - a[3], a[1] - b[3]) <= height / 2


def _union(boxes: Sequence[Box]) -> Box:
    return min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)


def _middle(box: Box) -> float:
    return (box[1] + box[3]) / 2


# ================================================================ reading order

@dataclass
class Unit:
    box: Box
    blocks: list[Block]
    index: int


def reading_order(blocks: Sequence[Block], doc: Any) -> list[Block]:
    """Each slide's blocks in the order its parts stand on it (recursive XY-cut); notes stay last."""
    places = Places(doc)
    out: list[Block] = []
    for slide, here in slides(blocks):
        units, loose = _units([b for b in here if b.kind != "slide_notes"], places)
        out += [b for unit in xy_cut(units, places.size(slide)) for b in unit.blocks]
        out += loose + [b for b in here if b.kind == "slide_notes"]
    return out


def _units(blocks: Sequence[Block], places: Places) -> tuple[list[Unit], list[Block]]:
    """Blocks of one shape (they share its box) move together; a block with no box keeps its place at the end."""
    units: list[Unit] = []
    loose: list[Block] = []
    for block in blocks:
        box = places.of(block)
        if box is None:
            loose.append(block)
        elif units and units[-1].box == box:
            units[-1].blocks.append(block)
        else:
            units.append(Unit(box, [block], len(units)))
    return units, loose


def xy_cut(units: Sequence[Unit], size: tuple[float, float]) -> list[Unit]:
    """Cut the slide at its empty bands, then cut each part again; a part with no empty band is read in rows.

    Rows first (bands across), but the next row joins the part above when both share an empty band down the slide
    that is wider than the gap between them: what stands in one column is closer together than the columns stand
    apart, so the part is read column by column (a case over its value in three cards, a map beside a step panel).
    A list of labels beside their values, closer across than down, stays row by row.
    """
    if len(units) < 2:
        return list(units)
    gap_down, gap_across = MIN_GAP * size[0], MIN_GAP * size[1]
    rows = _bands(units, 1, gap_across)
    if len(rows) > 1:
        parts = _join_columns(rows, gap_down)
        if len(parts) > 1:
            return [unit for part in parts for unit in xy_cut(part, size)]
    columns = _bands(units, 0, gap_down)
    if len(columns) > 1:
        return [unit for column in columns for unit in xy_cut(column, size)]
    return _rows(units)


def _bands(units: Sequence[Unit], axis: int, min_gap: float) -> list[list[Unit]]:
    """The units in bands along one axis (1: rows, top to bottom; 0: columns, left to right), split at every empty
    band at least `min_gap` wide."""
    parts: list[list[Unit]] = []
    end = None
    for unit in sorted(units, key=lambda u: (u.box[axis], u.index)):
        if end is None or unit.box[axis] - end >= min_gap:
            parts.append([])
        parts[-1].append(unit)
        end = unit.box[axis + 2] if end is None else max(end, unit.box[axis + 2])
    return [sorted(part, key=lambda u: u.index) for part in parts]


def _join_columns(rows: list[list[Unit]], gap_down: float) -> list[list[Unit]]:
    parts: list[list[Unit]] = [list(rows[0])]
    for row in rows[1:]:
        joined = parts[-1] + row
        between = min(u.box[1] for u in row) - max(u.box[3] for u in parts[-1])
        if _widest_gap(joined, 0, gap_down) > between:
            parts[-1] = joined
        else:
            parts.append(list(row))
    return parts


def _widest_gap(units: Sequence[Unit], axis: int, min_gap: float) -> float:
    """The widest empty band along an axis (0 when there is none)."""
    bands = _bands(units, axis, min_gap)
    ends = [max(u.box[axis + 2] for u in band) for band in bands]
    starts = [min(u.box[axis] for u in band) for band in bands]
    return max((start - end for end, start in zip(ends, starts[1:])), default=0.0)


def _rows(units: Sequence[Unit]) -> list[Unit]:
    rows: list[list[Unit]] = []
    for unit in sorted(units, key=lambda u: (u.box[1], u.index)):
        if rows and unit.box[1] - rows[-1][-1].box[1] <= ROW_TOLERANCE:
            rows[-1].append(unit)
        else:
            rows.append([unit])
    return [unit for row in rows for unit in sorted(row, key=lambda u: (u.box[0], u.index))]


# ================================================================ section labels

def section_labels(blocks: Sequence[Block], doc: Any) -> list[Block]:
    """A short label above a slide's title, the same on the slide before or after, joins the heading path.

    The label is the topmost one-line paragraph of up to 10 words that starts above the title, in the top 30% of the
    slide. Its block goes; every block of the slide gets [deck, label, ...] as its heading path.
    """
    places = Places(doc)
    found: dict[int, tuple[Block, str]] = {}
    for slide, here in slides(blocks):
        heading = next((b for b in here if b.kind == "heading"), None)
        top = places.of(heading)[1] if heading is not None and places.of(heading) is not None else None
        if top is None:
            continue
        height = places.size(slide)[1]
        labels = [(box[1], b) for b in here if b.kind == "paragraph" and "\n" not in b.text
                  and len(b.text.split()) <= LABEL_MAX_WORDS and (box := places.of(b)) is not None
                  and box[1] < top and box[1] < LABEL_TOP * height]
        if labels:
            label = min(labels, key=lambda pair: pair[0])[1]
            found[slide] = (label, " ".join(label.text.split()).casefold())
    kept = {slide for slide, (_, words) in found.items()
            if any(found.get(other, (None, None))[1] == words for other in (slide - 1, slide + 1))}
    out: list[Block] = []
    for block in blocks:
        slide = block.loc.slide
        if slide not in kept:
            out.append(block)
        elif block is not found[slide][0]:
            path = list(block.heading_path)
            label = found[slide][0].text
            if label not in path:
                path = [path[0], label, *path[1:]]
            out.append(Block.model_validate({**block.model_dump(), "heading_path": path}))
    return out


# ================================================================ figure places

def mark_figures(blocks: Sequence[Block], doc: Any) -> list[Block]:
    """The blocks of each picture (its "[Figure]", caption, inner words, a chart's table) get extra["figure"]."""
    places = Places(doc)
    place_of: dict[str, dict] = {}
    for picture in doc.pictures:
        box = places.of_item(picture)
        if box is None or len(picture.prov) != 1:
            continue
        slide = picture.prov[0].page_no
        width, height = places.size(slide)
        place = {"page": slide, "box": [round(max(0.0, box[0] / width), 4), round(max(0.0, box[1] / height), 4),
                                        round(min(1.0, box[2] / width), 4), round(min(1.0, box[3] / height), 4)]}
        place_of[picture.self_ref] = place
        for ref in picture.captions:
            place_of[ref.cref] = place
        for item, _ in doc.iterate_items(root=picture, traverse_pictures=True):
            if item is not picture:
                place_of[item.self_ref] = place
    return [b.model_copy(update={"extra": {**b.extra, "figure": place_of[b.extra["ref"]]}})
            if b.extra.get("ref") in place_of else b for b in blocks]