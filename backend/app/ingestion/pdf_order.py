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
"""
import logging
from collections.abc import Sequence

from docling_core.types.doc import BoundingBox, ContentLayer, DocItem, DoclingDocument, PictureItem

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
    if not moved:
        return list(blocks)
    logger.info("%d blocks or figures moved up to where they stand on their page", moved)
    return [b.model_copy(update={"seq": n}) for n, b in enumerate(b for _, unit in units for b in unit)]


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
