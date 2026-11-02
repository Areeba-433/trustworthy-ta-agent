"""pdf_backend.py: docling-parse reads the words, pdfium draws the pages that Docling's models look at.

The drawing is pdfium's alone, so these tests need neither docling-parse nor any model. A real PDF through
docling-parse and the models: test_converter.py, part 4."""
import pypdfium2 as pdfium
import pytest
from docling.backend import docling_parse_backend
from docling.datamodel.base_models import InputFormat
from docling_core.types.doc import BoundingBox, CoordOrigin

from app.ingestion import converter
from app.ingestion.pdf_backend import DoclingParseWordsPdfiumPages, _lines_without_drawing, draw_page

INSIDE_THE_RECTANGLE = BoundingBox(l=110, t=842 - 490, r=390, b=842 - 310, coord_origin=CoordOrigin.TOPLEFT)


def drawn(path, **kwargs):
    pdf = pdfium.PdfDocument(str(path))
    try:
        return draw_page(pdf, 0, **kwargs)
    finally:
        pdf.close()


def test_the_whole_page_is_drawn_at_the_asked_scale(figure_pdf):
    """figure_pdf's black rectangle: 100 to 400 points from the left, 300 to 500 from the bottom (page: 842 high)."""
    image = drawn(figure_pdf(), scale=2)
    assert image.size == (1190, 1684) and image.mode == "RGB"
    assert image.getpixel((2 * 250, 2 * (842 - 400))) == (0, 0, 0)             # the middle of the rectangle
    assert image.getpixel((2 * 50, 2 * 50)) == (255, 255, 255)                 # paper


def test_a_part_of_the_page_is_measured_on_the_visible_page_like_docling_parse_s_words(figure_pdf):
    """The OOP book's pages start at (54, 55). A box measured from the visible page's top-left corner, as
    docling-parse measures words, must cut out the rectangle there too."""
    image = drawn(figure_pdf(corner=(54, 55)), cropbox=INSIDE_THE_RECTANGLE)
    assert image.size == (280, 180)
    assert image.convert("L").getextrema()[1] < 20                            # all of it black: the lightest pixel too


def test_a_box_measured_from_the_bottom_cuts_out_the_same_part(figure_pdf):
    path = figure_pdf()
    from_bottom = BoundingBox(l=110, t=490, r=390, b=310, coord_origin=CoordOrigin.BOTTOMLEFT)
    assert drawn(path, cropbox=from_bottom).tobytes() == drawn(path, cropbox=INSIDE_THE_RECTANGLE).tobytes()


def test_a_cmyk_picture_is_drawn(picture_pdf):
    """The kind of picture that ends the process in docling-parse's own drawing (book page 94)."""
    image = drawn(picture_pdf("DeviceCMYK"))
    picture = image.crop((80, 792 - 668, 224, 792 - 588))                      # inside the picture (72-232, 580-676)
    assert len(picture.getcolors(maxcolors=100_000)) > 10                      # colours, not empty paper


def test_pdfs_are_read_with_this_backend():
    assert converter.get_converter("pdf").format_to_options[InputFormat.PDF].backend is DoclingParseWordsPdfiumPages


def test_docling_parse_still_measures_page_lines_with_its_drawing_off(monkeypatch):
    """Docling's reading order uses the lines; Docling 2.134 would switch them off together with the drawing."""
    asked = []
    monkeypatch.setattr(docling_parse_backend, "_make_docling_parse_page_content_config",
                        lambda **settings: asked.append(settings))
    docling_s_own = docling_parse_backend._make_docling_parse_page_content_config
    with _lines_without_drawing():
        docling_parse_backend._make_docling_parse_page_content_config(create_words=True, compute_shapes=False)
    assert asked == [{"create_words": True, "compute_shapes": True}]
    assert docling_parse_backend._make_docling_parse_page_content_config is docling_s_own      # put back after


def test_a_page_asked_for_after_docling_stopped_the_document_gets_a_clear_error():
    """On the whole OOP book Docling hit its time limit, closed the file, and a stage still busy asked for a page:
    "'NoneType' object is not subscriptable" said nothing about why."""
    reader = DoclingParseWordsPdfiumPages.__new__(DoclingParseWordsPdfiumPages)    # as it is after unload()
    reader._pdf = None
    with pytest.raises(RuntimeError, match="closed"):
        reader._draw(0)
