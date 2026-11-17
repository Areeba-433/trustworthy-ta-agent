"""order_by_position(): what stands higher on a page comes first.

Docling's reading order keeps the items of a list together and puts what stands between them after the list. In the
OOP book's exercises that sends a sample output to the wrong exercise: on book page 184, exercise 1 ends with "The
interchange might look like this:", but its sample interaction came after exercise 2; pages 98 and 99 likewise.

A block moves up past the blocks before it that stand entirely below it in the same column. Nothing else moves:
blocks side by side (columns, the two halves of a line) keep Docling's order, and so do blocks made from one Docling
item (they share its box), and blocks on different pages. The words inside a figure move together, with the
figure's own box: one by one, a narrow label would stop at any narrow block and end up between paragraphs (book
page 210). Two blocks that do not overlap sideways are in one column too when a block between them, top to bottom,
reaches over both: on page 210 the code line "float& intp" at the left edge still stopped the centred figure, which
ended up in the middle of a sentence, though the paragraph between them spans the page. Two real columns have no
such block between them.

A heading that stands above everything else on its page goes first on it, whatever the column: a page's title over
two narrow labels (a lab sheet: "Lab 4" centred at the top, "Name:" and "Task 1:" at the left edge, and Docling put
the title after Task 3) would otherwise stop at the first label it does not overlap.

When anything moved, every block's heading path is built again in the new order, by the rule to_blocks() uses,
with each heading's level from its Docling item. A block that moved past a heading now sits in the section above
it: the lab sheet's Tasks 1 to 3 were outside "Lab 4", and the words inside two of the book's UML diagrams (pages
842 and 848) kept the section of the text Docling had put them after.
"""
import logging
from collections.abc import Sequence

from docling_core.types.doc import (BoundingBox, ContentLayer, DocItem, DoclingDocument, PictureItem,
                                    SectionHeaderItem)

from app.ingestion.contract import Block

logger = logging.getLogger(__name__)

_GAP = 1.0      # points: a box whose bottom is at most this far below another's top still stands above it


def order_by_position(blocks: Sequence[Block], doc: DoclingDocument) -> list[Block]:
    """The blocks, each page's in the order they stand on it; seq numbered again when anything moved."""
    places, figure_of = _places(doc), _figure_of(doc)
    units: list[tuple[str, list[Block]]] = []           # (Docling id that places them, blocks that move together)
    for block in blocks:
        owner = figure_of.get(block.extra.get("ref"), block.extra.get("ref"))
        if units and units[-1][0] == owner:
            units[-1][1].append(block)
        else:
            units.append((owner, [block]))
    boxes: dict[int, list[BoundingBox]] = {}            # every unit's box, page by page
    for owner, _ in units:
        if owner in places:
            boxes.setdefault(places[owner][0], []).append(places[owner][1])
    moved = 0
    for n in range(1, len(units)):
        j = n
        while j > 0 and _stands_above(places.get(units[j][0]), places.get(units[j - 1][0]), boxes):
            units[j - 1], units[j] = units[j], units[j - 1]
            j -= 1
        moved += j != n
    moved += _page_titles_first(units, places, boxes)
    if not moved:
        return list(blocks)
    moved_blocks = [b for _, unit in units for b in unit]
    ordered = heading_paths(moved_blocks, doc)
    logger.info("%d blocks or figures moved up to where they stand on their page; %d heading paths changed", moved,
                sum(a.heading_path != b.heading_path for a, b in zip(moved_blocks, ordered)))
    return [b.model_copy(update={"seq": n}) for n, b in enumerate(ordered)]


def heading_paths(blocks: Sequence[Block], doc: DoclingDocument) -> list[Block]:
    """The blocks with their heading paths built again in this order, as to_blocks() builds them: a heading closes
    the open headings of its level and deeper ones, and opens its own. Its level is its Docling item's (from its
    size, set_heading_levels()); a title is above every level. In Docling's order this gives every block the path
    it had. If a heading's Docling item is not found, nothing changes."""
    items = {item.self_ref: item for item in doc.texts}
    open_headings: list[tuple[int, str]] = []        # (level, name) of the headings above the current block
    out: list[Block] = []
    for block in blocks:
        if block.kind == "heading":
            item = items.get(block.extra.get("ref"))
            if item is None:
                return list(blocks)
            level = item.level if isinstance(item, SectionHeaderItem) else 0
            open_headings = [h for h in open_headings if h[0] < level] + [(level, block.heading_path[-1])]
        path = block.heading_path[:1] + [name for _, name in open_headings]
        out.append(block if path == block.heading_path else block.model_copy(update={"heading_path": path}))
    return out


def _page_titles_first(units: list[tuple[str, list[Block]]], places: dict[str, tuple[int, BoundingBox]],
                       boxes: dict[int, list[BoundingBox]]) -> int:
    """Put each heading that stands above everything else on its page first on its page, in place; how many moved."""
    moved = 0
    for n in range(len(units)):
        owner, unit = units[n]
        place = places.get(owner)
        if place is None or unit[0].kind != "heading":
            continue
        page, box = place
        if not all(box.b <= other.t + _GAP for other in boxes.get(page, []) if other is not box):
            continue
        first = next(i for i, (o, _) in enumerate(units) if o in places and places[o][0] == page)
        if first < n:
            units.insert(first, units.pop(n))
            moved += 1
    return moved


def _figure_of(doc: DoclingDocument) -> dict[str, str]:
    """{Docling id of a word inside a figure: the figure's id}."""
    owners = {}
    for picture in doc.pictures:
        for item, _ in doc.iterate_items(root=picture, traverse_pictures=True):
            if item is not picture and not isinstance(item, PictureItem):
                owners[item.self_ref] = picture.self_ref
    return owners


def _places(doc: DoclingDocument) -> dict[str, tuple[int, BoundingBox]]:
    """{Docling id: (page, box measured from the page's top-left corner)} for every item with a box on a page."""
    places = {}
    for item, _ in doc.iterate_items(traverse_pictures=True, included_content_layers=set(ContentLayer)):
        if not isinstance(item, DocItem) or not item.prov:
            continue
        prov = item.prov[0]                              # where the item starts; it may run onto the next page
        page = doc.pages.get(prov.page_no)
        if page is not None:
            places[item.self_ref] = (prov.page_no, prov.bbox.to_top_left_origin(page.size.height))
    return places


def _stands_above(lower: tuple[int, BoundingBox] | None, upper: tuple[int, BoundingBox] | None,
                  boxes: dict[int, list[BoundingBox]] | None = None) -> bool:
    """`lower` (later in Docling's order) stands entirely above `upper` on the same page, in the same column: they
    overlap sideways, or a block between them, top to bottom, overlaps both."""
    if lower is None or upper is None or lower[0] != upper[0]:
        return False
    a, b = lower[1], upper[1]
    if a.b > b.t + _GAP:
        return False
    if _sideways(a, b):
        return True
    return any(a.b <= c.t + _GAP and c.b <= b.t + _GAP and _sideways(c, a) and _sideways(c, b)
               for c in (boxes or {}).get(lower[0], []) if c is not a and c is not b)


def _sideways(a: BoundingBox, b: BoundingBox) -> bool:
    return min(a.r, b.r) > max(a.l, b.l)
