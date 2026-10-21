"""mark_figures() remembers where each figure is; render_figure() cuts it out of the PDF when an answer needs it."""
import io

import pytest
from docling_core.types.doc import BoundingBox, CoordOrigin, DocItemLabel, DoclingDocument, ProvenanceItem, Size
from PIL import Image

from app.ingestion.converter import Conversion
from app.ingestion.dispatcher import ingest_file
from app.ingestion.docling_blocks import to_blocks
from app.ingestion.loaders import pdf
from app.ingestion.pdf_figures import mark_figures, render_figure

# The black rectangle of the figure_pdf fixture, as fractions of its 595 x 842 page from the top-left corner
RECTANGLE = [round(100 / 595, 4), round((842 - 500) / 842, 4), round(400 / 595, 4), round((842 - 300) / 842, 4)]


def prov(l: float, b: float, r: float, t: float) -> ProvenanceItem:
    """A place on page 1, measured from the bottom-left corner, as Docling gives it."""
    box = BoundingBox(l=l, b=b, r=r, t=t, coord_origin=CoordOrigin.BOTTOMLEFT)
    return ProvenanceItem(page_no=1, charspan=(0, 0), bbox=box)


def _book() -> DoclingDocument:
    """A page like book page 424: a paragraph, then Figure 9.7 with a label drawn inside it and its caption."""
    doc = DoclingDocument(name="b")
    doc.add_page(page_no=1, size=Size(width=595, height=842))
    doc.add_text(DocItemLabel.TEXT, "This is shown in Figure 9.7.", prov=prov(72, 600, 500, 612))
    picture = doc.add_picture(prov=prov(100, 300, 400, 500))
    doc.add_text(DocItemLabel.TEXT, "class A", parent=picture, prov=prov(200, 450, 260, 460))
    caption = doc.add_text(DocItemLabel.CAPTION, "FIGURE 9.7 Public and private derivation.", parent=picture,
                           prov=prov(100, 280, 400, 292))
    picture.captions.append(caption.get_ref())
    return doc


def test_the_caption_and_the_words_inside_a_figure_know_where_it_is():
    doc = _book()
    blocks = mark_figures(to_blocks(doc, "pdf", "OOP book"), doc)
    assert [(b.kind, b.extra.get("figure")) for b in blocks] == [
        ("paragraph", None),
        ("figure_text", {"page": 1, "box": RECTANGLE}),
        ("caption", {"page": 1, "box": RECTANGLE}),
    ]


def test_a_figure_on_a_page_docling_did_not_measure_is_left_unplaced():
    doc = _book()
    doc.pages.clear()
    assert all("figure" not in b.extra for b in mark_figures(to_blocks(doc, "pdf", "OOP book"), doc))


@pytest.mark.parametrize("corner", [(0, 0), (54, 55)], ids=["page-at-zero", "page-like-the-OOP-book"])
def test_the_cut_out_is_the_figure_with_a_small_white_margin(figure_pdf, corner):
    png = render_figure(figure_pdf(corner), {"page": 1, "box": RECTANGLE}, dpi=72)   # 72 dpi: 1 pixel = 1 point
    image = Image.open(io.BytesIO(png)).convert("L")
    width, height = image.size
    assert abs(width - (300 + 2 * 6)) <= 2 and abs(height - (200 + 2 * 6)) <= 2     # the figure and 6 points around
    assert image.getpixel((width // 2, height // 2)) < 50                             # inside: the black figure
    assert image.getpixel((2, 2)) > 200                                              # the margin: white page


def test_the_pdf_loader_marks_figures(listing_pdf, monkeypatch, data_dir):
    path, _ = listing_pdf(["int a;"])
    monkeypatch.setattr(pdf, "convert", lambda *args, **kwargs: Conversion(_book()))
    doc = ingest_file(path, "r1", "c1")
    assert [b.kind for b in doc.blocks if "figure" in b.extra] == ["figure_text", "caption"]
    assert "figures" in doc.quality.seconds_taken
