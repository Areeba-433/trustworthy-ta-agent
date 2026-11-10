"""mark_figures() remembers where each figure is; render_figure() cuts it out of the PDF when an answer needs it."""
import io

import pytest
from docling_core.types.doc import BoundingBox, CoordOrigin, DocItemLabel, DoclingDocument, ProvenanceItem, Size
from PIL import Image

from app.ingestion.converter import Conversion
from app.ingestion.dispatcher import ingest_file
from app.ingestion.docling_blocks import to_blocks
from app.ingestion.loaders import pdf
from app.ingestion.pdf_figures import join_caption_lines, link_figure_labels, mark_figures, render_figure

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


# ======================================================================== a caption's line Docling cut off

def _captioned(label: str, line: DocItemLabel, gap: float = 3, left: float = 91) -> DoclingDocument:
    """A figure's caption and, right under it, a line Docling made an item of its own."""
    from docling_core.types.doc import ContentLayer
    doc = DoclingDocument(name="b")
    doc.add_page(page_no=1, size=Size(width=595, height=842))
    doc.add_text(DocItemLabel.CAPTION, label, prov=prov(91, 450, 135, 459))
    layer = ContentLayer.BODY if line == DocItemLabel.TEXT else ContentLayer.FURNITURE
    doc.add_text(line, "Passing by reference in the REF program.", content_layer=layer,
                 prov=prov(left, 450 - gap - 7, left + 131, 450 - gap))
    doc.add_text(DocItemLabel.TEXT, "Reference arguments are indicated by the ampersand.", prov=prov(91, 400, 417, 409))
    return doc


@pytest.mark.parametrize("line", [DocItemLabel.TEXT, DocItemLabel.PAGE_FOOTER], ids=["paragraph", "footer"])
def test_a_caption_that_is_only_its_label_gets_its_description_back(line):
    """69 figures of the OOP book: "FIGURE 5.7" as the caption, its description as a paragraph of its own; book page
    682: the description at the bottom of the page taken for the footer."""
    doc = _captioned("FIGURE 5.7", line)
    assert join_caption_lines(doc) == 1
    assert [(b.kind, b.text) for b in to_blocks(doc, "pdf", "OOP book")] == [
        ("caption", "FIGURE 5.7 Passing by reference in the REF program."),
        ("paragraph", "Reference arguments are indicated by the ampersand.")]


@pytest.mark.parametrize("caption, gap, left", [("FIGURE 5.7 Passing by value.", 3, 91), ("FIGURE 5.7", 15, 91),
                                                ("FIGURE 5.7", 3, 150)], ids=["whole", "far", "elsewhere"])
def test_a_line_that_is_not_the_caption_s_stays_where_it_is(caption, gap, left):
    """A caption with its description already, a line further down, or one that does not start where the caption
    starts."""
    doc = _captioned(caption, DocItemLabel.TEXT, gap, left)
    assert join_caption_lines(doc) == 0
    assert len(to_blocks(doc, "pdf", "OOP book")) == 3


# ================================================================ link_figure_labels(): step 14a

def _labelled(label: str = "FIGURE 2.3", kind: DocItemLabel = DocItemLabel.SECTION_HEADER,
              box: tuple[float, float, float, float] = (56, 379, 98, 388), page: int = 1) -> DoclingDocument:
    """A page like book page 65: section "Variables", a figure, its label in the margin under the figure's left
    edge (Docling read it as a heading), the description right under the label, then the text goes on."""
    doc = DoclingDocument(name="b")
    for n in (1, 2):
        doc.add_page(page_no=n, size=Size(width=595, height=842))
    doc.add_heading("Variables", level=1, prov=prov(56, 700, 200, 712))
    doc.add_text(DocItemLabel.TEXT, "A variable has a name and a value.", prov=prov(56, 650, 500, 662))
    doc.add_picture(prov=prov(100, 400, 400, 600))
    where = prov(*box)
    where.page_no = page
    if kind == DocItemLabel.SECTION_HEADER:
        doc.add_heading(label, level=1, prov=where)
    else:
        doc.add_text(kind, label, prov=where)
    doc.add_text(DocItemLabel.TEXT, "Variable of type int in memory.", prov=prov(56, 368, 160, 375))
    doc.add_text(DocItemLabel.TEXT, "Each variable has an address.", prov=prov(56, 330, 500, 342))
    return doc


def _fixed_blocks(doc: DoclingDocument) -> list:
    """The PDF loader's order: labels first, then caption lines, then blocks."""
    link_figure_labels(doc)
    join_caption_lines(doc)
    return mark_figures(to_blocks(doc, "pdf", "OOP book"), doc)


def test_a_figure_label_read_as_a_heading_becomes_the_figures_caption_with_its_description():
    doc = _labelled()
    blocks = _fixed_blocks(doc)
    assert [(b.kind, b.text, b.figure_id) for b in blocks] == [
        ("heading", "Variables", None),
        ("paragraph", "A variable has a name and a value.", None),
        ("caption", "FIGURE 2.3 Variable of type int in memory.", "fig0"),
        ("paragraph", "Each variable has an address.", None),
    ]
    assert blocks[-1].heading_path == ["OOP book", "Variables"]           # not "... > FIGURE 2.3"
    assert blocks[2].extra["figure"]["page"] == 1


@pytest.mark.parametrize("kind", [DocItemLabel.CAPTION, DocItemLabel.TEXT])
def test_a_loose_label_under_a_figure_becomes_its_caption(kind):
    doc = _labelled(kind=kind)
    assert link_figure_labels(doc) == 1
    assert [ref.resolve(doc).text for ref in doc.pictures[0].captions] == ["FIGURE 2.3"]


@pytest.mark.parametrize("label, kind, box, page", [
    ("FIGURE 2.3", DocItemLabel.SECTION_HEADER, (56, 330, 98, 339), 1),          # 61 points below the figure
    ("FIGURE 2.3", DocItemLabel.SECTION_HEADER, (56, 379, 98, 388), 2),          # on the next page
    ("FIGURE 2.3", DocItemLabel.SECTION_HEADER, (20, 379, 60, 388), 1),          # ends 40 points short of it
    ("Figure 2.3 shows a variable.", DocItemLabel.TEXT, (56, 379, 300, 388), 1),  # a sentence, not a label
    ("Variables in memory", DocItemLabel.SECTION_HEADER, (56, 379, 200, 388), 1),  # a real heading
], ids=["too-far-below", "other-page", "off-to-the-side", "a-sentence", "a-heading"])
def test_text_that_is_not_the_figures_label_is_left_alone(label, kind, box, page):
    doc = _labelled(label, kind, box, page)
    assert link_figure_labels(doc) == 0
    assert doc.pictures[0].captions == []


def test_a_label_alone_wins_over_a_caption_that_goes_on():
    doc = _labelled("FIGURE 2.10")                                           # the label, 12 points down
    doc.add_text(DocItemLabel.CAPTION, "Figure 2.10 emphasizes the operator.", prov=prov(100, 392, 400, 398))
    link_figure_labels(doc)
    assert [ref.resolve(doc).text for ref in doc.pictures[0].captions] == ["FIGURE 2.10"]


def test_a_figure_that_has_a_caption_keeps_it_and_takes_no_other_label():
    doc = _labelled()
    caption = doc.add_text(DocItemLabel.CAPTION, "FIGURE 2.2 A variable.", prov=prov(100, 605, 400, 615))
    doc.pictures[0].captions.append(caption.get_ref())
    assert link_figure_labels(doc) == 0
    assert any(b.kind == "heading" and b.text == "FIGURE 2.3" for b in to_blocks(doc, "pdf", "OOP book"))


def test_a_figure_with_no_words_gets_a_placed_figure_block():
    doc = _labelled("Variables in memory")                                    # no label at all
    figure = [b for b in mark_figures(to_blocks(doc, "pdf", "OOP book"), doc) if b.kind == "figure"]
    assert [(b.text, b.figure_id, b.extra["figure"]["page"]) for b in figure] == [("[Figure]", "fig0", 1)]
