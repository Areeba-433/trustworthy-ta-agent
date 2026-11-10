"""Images Docling left out: every image in the PDF ends up in the result, as a picture.

Docling finds pictures by looking at the page with its layout model. A screenshot of a terminal or of code looks like
lines of text to it, so it can take it for text or code. Its words then come from the PDF's text layer, and a
screenshot has none (we do no OCR): the item is empty and Docling drops it. The screenshot is gone, not even a
[Figure] mark is left, and the figures check cannot see it, because it counts the pictures Docling found. In a
13-page assignment exported from Google Docs, 2 of 20 screenshots went this way.

add_missed_pictures() compares Docling's result with the images the PDF itself holds (read with pdfium) and adds a
picture for each image that Docling left out entirely: nothing Docling read lies on it. The new picture has the
image's page and box, so it gets its figure id and [Figure] mark like any other, and the images phase can show it.
Not added:
- an image inside a picture Docling found (two screenshots close together often make one picture);
- an image something Docling read lies on: a slide's background under its title, a picture behind text;
- an image at the same place on several pages: a logo or a slide template's art;
- an icon: under 48 points on both sides, as to_blocks() leaves icons out.
"""
import logging
from collections import Counter
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from docling_core.types.doc import (BoundingBox, CoordOrigin, DocItem, DoclingDocument, NodeItem, PictureItem,
                                    ProvenanceItem)

logger = logging.getLogger(__name__)

_ICON = 48.0          # points: an image under this on both sides is an icon (as in docling_blocks)
_INSIDE = 0.5         # an image this much inside a picture Docling found is part of that picture
_UNDER = 0.1          # an image with more than this share under something Docling read is not left out
_ON_TOP = 0.5         # an item this much inside an image stands on it: the image is a background
_REPEATED = 3         # an image at the same place on this many pages is a decoration


def add_missed_pictures(doc: DoclingDocument, path: Path) -> int:
    """Add a picture to Docling's result for each image of the PDF at `path` that Docling left out entirely, in
    reading order on its page; changes `doc` in place. Returns how many were added."""
    images = _images(path)
    repeated = Counter(key for _, _, key in images)
    added = 0
    for page_no, box, key in images:
        if page_no not in doc.pages or repeated[key] >= _REPEATED or _covered(box, page_no, doc):
            continue                              # (a page Docling did not read is reported by the loader)
        prov = ProvenanceItem(page_no=page_no, bbox=box, charspan=(0, 0))
        sibling, after = _position(page_no, box.t, doc)
        if sibling is None:
            doc.add_picture(prov=prov)
        else:
            doc.insert_picture(sibling=sibling, prov=prov, after=after)
        added += 1
    logger.info("%d images in the PDF; %d Docling left out added as pictures", len(images), added)
    return added


def _images(path: Path) -> list[tuple[int, BoundingBox, tuple]]:
    """(page number, box on the visible page measured from its bottom-left corner, what makes it the same image on
    another page) for each image bigger than an icon."""
    found = []
    pdf = pdfium.PdfDocument(str(path))
    try:
        for index in range(len(pdf)):
            page = pdf[index]
            left, bottom, right, top = page.get_cropbox()
            for image in page.get_objects(filter=(pdfium_c.FPDF_PAGEOBJ_IMAGE,), max_depth=3):
                l, b, r, t = image.get_bounds()
                box = BoundingBox(l=max(l, left) - left, b=max(b, bottom) - bottom, r=min(r, right) - left,
                                  t=min(t, top) - bottom, coord_origin=CoordOrigin.BOTTOMLEFT)
                if box.r - box.l < _ICON and box.t - box.b < _ICON or box.r <= box.l or box.t <= box.b:
                    continue                      # an icon, or off the visible page
                key = (round(box.l), round(box.b), round(box.r), round(box.t), tuple(image.get_px_size()))
                found.append((index + 1, box, key))
            page.close()
    finally:
        pdf.close()
    return found


def _covered(box: BoundingBox, page_no: int, doc: DoclingDocument) -> bool:
    """True when the image is inside a picture Docling found, or something Docling read lies on it: over a part of
    the image, or standing on it like a slide's title on its background."""
    area = (box.r - box.l) * (box.t - box.b)
    for item in [*doc.pictures, *doc.texts, *doc.tables]:
        for prov in item.prov:
            if prov.page_no != page_no:
                continue
            other = prov.bbox.to_bottom_left_origin(doc.pages[page_no].size.height)
            overlap = box.intersection_area_with(other)
            other_area = (other.r - other.l) * (other.t - other.b)
            if (overlap / area > _UNDER or isinstance(item, PictureItem) and overlap / area >= _INSIDE
                    or other_area > 0 and overlap / other_area >= _ON_TOP):
                return True
    return False


def _position(page_no: int, top: float, doc: DoclingDocument) -> tuple[NodeItem | None, bool]:
    """Where the new picture goes among the body's items: after the last one on its page that stands above it,
    else before the page's first item, else after the last item of an earlier page. (None, True) for an empty body."""
    placed = [(node, _first_prov(node, doc)) for node in (ref.resolve(doc) for ref in doc.body.children)]
    placed = [(node, prov) for node, prov in placed if prov is not None]
    height = doc.pages[page_no].size.height
    on_page = [(node, prov) for node, prov in placed if prov.page_no == page_no]
    above = [node for node, prov in on_page if prov.bbox.to_bottom_left_origin(height).t >= top]
    if above:
        return above[-1], True
    if on_page:
        return on_page[0][0], False
    before = [node for node, prov in placed if prov.page_no < page_no]
    if before:
        return before[-1], True
    return (placed[0][0], False) if placed else (None, True)


def _first_prov(node: NodeItem, doc: DoclingDocument) -> ProvenanceItem | None:
    """Where an item of the body starts: its own place, or for a group (a list) its first item's."""
    if isinstance(node, DocItem) and node.prov:
        return node.prov[0]
    for child, _ in doc.iterate_items(root=node, with_groups=False):
        if isinstance(child, DocItem) and child.prov:
            return child.prov[0]
    return None
