"""Images Docling left out: every image of the PDF ends up in the result, as a picture with its [Figure] mark."""
import zlib

import pytest
from docling_core.types.doc import BoundingBox, CoordOrigin, DocItemLabel, DoclingDocument, ProvenanceItem, Size

from app.ingestion.converter import Conversion
from app.ingestion.dispatcher import ingest_file
from app.ingestion.docling_blocks import to_blocks
from app.ingestion.loaders import pdf
from app.ingestion.pdf_images import add_missed_pictures
from conftest import write_pdf


def _image(width: int = 40, height: int = 20) -> bytes:
    """A small RGB picture object, Flate-compressed like a PNG screenshot."""
    pixels = zlib.compress(bytes((x * 7 + y * 3 + ink * 50) % 256
                                 for y in range(height) for x in range(width) for ink in range(3)))
    return (b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceRGB /BitsPerComponent 8"
            b" /Filter /FlateDecode /Length %d >>\nstream\n" % (width, height, len(pixels)) + pixels + b"\nendstream")


def _draw(left: float, bottom: float, width: float, height: float, image: int = 0) -> str:
    return f"q {width} 0 0 {height} {left} {bottom} cm /Im{image} Do Q"


def _pdf(tmp_path, pages, corner=(0, 0), name="screens.pdf"):
    dx, dy = corner
    return write_pdf(tmp_path / name, pages, mediabox=(dx, dy, dx + 612, dy + 792), images=[_image(), _image(30, 30)])


def _box(l, b, r, t):
    return BoundingBox(l=l, b=b, r=r, t=t, coord_origin=CoordOrigin.BOTTOMLEFT)


def _doc(pages: int = 1) -> DoclingDocument:
    doc = DoclingDocument(name="assignment")
    for page in range(1, pages + 1):
        doc.add_page(page_no=page, size=Size(width=612, height=792))
    return doc


def _text(doc, text, page, box):
    return doc.add_text(DocItemLabel.TEXT, text, prov=ProvenanceItem(page_no=page, bbox=_box(*box), charspan=(0, 1)))


def _kinds(doc):
    return [(b.kind, b.text, b.loc.page) for b in to_blocks(doc, "pdf", "Assignment")]


def test_a_screenshot_docling_left_out_comes_back_as_a_picture_where_it_stands(tmp_path):
    """Assignment page 1: Docling took the terminal screenshot between two paragraphs for text and dropped it."""
    path = _pdf(tmp_path, [_draw(72, 275, 470, 75)])
    doc = _doc()
    _text(doc, "Identified the file type.", 1, (72, 369, 504, 379))
    _text(doc, "strings is always the first move.", 1, (72, 199, 533, 253))
    assert add_missed_pictures(doc, path) == 1
    assert _kinds(doc) == [("paragraph", "Identified the file type.", 1), ("figure", "[Figure]", 1),
                           ("paragraph", "strings is always the first move.", 1)]
    picture = doc.pictures[0]
    assert (picture.prov[0].page_no, picture.prov[0].bbox) == (1, _box(72, 275, 542, 350))


def test_images_inside_a_picture_docling_found_are_not_added(tmp_path):
    """Two screenshots 5 points apart are one picture to Docling (assignment pages 2 and 3)."""
    path = _pdf(tmp_path, [_draw(72, 455, 470, 263) + "\n" + _draw(72, 187, 470, 263)])
    doc = _doc()
    doc.add_picture(prov=ProvenanceItem(page_no=1, bbox=_box(72, 187, 542, 719), charspan=(0, 0)))
    assert add_missed_pictures(doc, path) == 0


def test_an_image_under_text_is_a_background_and_is_not_added(tmp_path):
    path = _pdf(tmp_path, [_draw(0, 0, 612, 792)])
    doc = _doc()
    _text(doc, "A slide's title over its template.", 1, (72, 600, 540, 700))
    assert add_missed_pictures(doc, path) == 0


@pytest.mark.parametrize("pages, added", [(3, 0), (2, 2)])
def test_an_image_at_the_same_place_on_three_pages_is_a_decoration(tmp_path, pages, added):
    """A logo in every slide's corner is no figure of the slides."""
    path = _pdf(tmp_path, [_draw(500, 700, 80, 60)] * pages)
    doc = _doc(pages)
    for page in range(1, pages + 1):
        _text(doc, f"Slide {page}.", page, (72, 600, 400, 650))
    assert add_missed_pictures(doc, path) == added


def test_an_icon_is_not_added(tmp_path):
    path = _pdf(tmp_path, [_draw(72, 160, 12, 12, image=1)])           # the 12-point "@" chip of a video link
    assert add_missed_pictures(_doc(), path) == 0


def test_the_box_is_measured_from_the_visible_page_s_corner(tmp_path):
    """Docling measures from the visible page's corner; some PDFs' pages start at (54, 55), like the OOP book."""
    path = _pdf(tmp_path, [_draw(54 + 72, 55 + 275, 470, 75)], corner=(54, 55))
    doc = _doc()
    assert add_missed_pictures(doc, path) == 1
    assert doc.pictures[0].prov[0].bbox == _box(72, 275, 542, 350)


def test_an_image_on_a_page_docling_did_not_read_is_left_to_the_loader_s_warning(tmp_path):
    path = _pdf(tmp_path, [_draw(72, 400, 470, 263)])
    doc = DoclingDocument(name="assignment")                     # no page 1: Docling did not read it
    assert add_missed_pictures(doc, path) == 0


def test_a_picture_on_a_page_with_nothing_else_goes_after_the_pages_before_it(tmp_path):
    path = _pdf(tmp_path, ["", _draw(72, 400, 470, 263), ""])
    doc = _doc(3)
    _text(doc, "Page one.", 1, (72, 700, 300, 720))
    _text(doc, "Page three.", 3, (72, 700, 300, 720))
    assert add_missed_pictures(doc, path) == 1
    assert _kinds(doc) == [("paragraph", "Page one.", 1), ("figure", "[Figure]", 2), ("paragraph", "Page three.", 3)]


def test_the_pdf_loader_adds_the_missed_picture_and_gives_it_its_figure_label(tmp_path, monkeypatch, data_dir):
    """OOP book page 134: Docling dropped the switch-statement figure (a picture of code), but kept its label."""
    page = ("BT /F1 10 Tf 91 236 Td (FIGURE 3.12) Tj ET\n"
            "BT /F1 10 Tf 91 200 Td (Before entering the switch, assign a value.) Tj ET\n" + _draw(139, 257, 288, 317))
    path = write_pdf(tmp_path / "book.pdf", [page], mediabox=(0, 0, 612, 792), images=[_image()])
    doc = _doc()
    doc.add_text(DocItemLabel.CAPTION, "FIGURE 3.12", prov=ProvenanceItem(page_no=1, bbox=_box(91, 234, 140, 243),
                                                                           charspan=(0, 11)))
    _text(doc, "Before entering the switch, assign a value.", 1, (91, 198, 400, 210))
    monkeypatch.setattr(pdf, "convert", lambda *args, **kwargs: Conversion(doc))
    parsed = ingest_file(path, "r1", "c1")
    caption = next(b for b in parsed.blocks if b.kind == "caption")
    assert (caption.text, caption.figure_id) == ("FIGURE 3.12", "fig0")
    assert "figure" in caption.extra                                 # placed: an answer can show the figure
    assert "missed_pictures" in parsed.quality.seconds_taken
