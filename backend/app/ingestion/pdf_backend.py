"""How Docling reads our PDFs: docling-parse reads the words, pdfium draws the pages.

Docling's PDF reader, docling-parse, does two jobs: it reads every word with its position, and it draws every page
as a picture for the layout and table models. Its drawing crashes the whole Python process on a picture stored as
Flate-compressed CMYK (the four printing inks): 13 pages of the OOP book, book page 94 among them. Reproduced with a
one-page PDF made from nothing (tests/ingestion/test_converter.py), with docling-parse 7.22.2 and 7.22.4.

pdfium, the PDF engine of Chrome, draws those pictures without trouble, so it does the drawing here. The words stay
docling-parse's: Docling's pdfium reader puts them in the wrong place on pages that do not start at (0, 0), like
the OOP book's, which start at (54, 55). Both measure on the visible page (the crop box), so a box the models find
on pdfium's picture is a box in docling-parse's words.

Switching docling-parse's drawing off would also switch off the lines and boxes it measures on each page (Docling
2.134 ties the two). Docling's reading order uses those lines to tell columns and sections apart, so they are kept.
"""
import logging
import threading
from contextlib import contextmanager
from functools import partial
from io import BytesIO
from pathlib import Path

import pypdfium2 as pdfium
from docling.backend import docling_parse_backend
from docling.backend.docling_parse_backend import ThreadedDoclingParseDocumentBackend
from docling.datamodel.backend_options import PdfBackendOptions, ThreadedDoclingParseBackendOptions
from docling.utils.locks import pypdfium2_lock
from docling_core.types.doc import BoundingBox, CoordOrigin
from PIL import Image

logger = logging.getLogger(__name__)

_SHARPER = 1.5          # draw 1.5 times larger than asked, then shrink: sharper letters, as Docling's pdfium reader
_setup_lock = threading.Lock()


class DoclingParseWordsPdfiumPages(ThreadedDoclingParseDocumentBackend):
    """docling-parse with its page drawing switched off; pdfium draws each page when a model asks for it."""

    def __init__(self, in_doc, path_or_stream: BytesIO | Path, options: PdfBackendOptions | None = None):
        if isinstance(options, ThreadedDoclingParseBackendOptions):
            options = options.model_copy(update={"render_pages": False})
        else:
            options = ThreadedDoclingParseBackendOptions(render_pages=False)
        with _lines_without_drawing():
            super().__init__(in_doc, path_or_stream, options)
        source = path_or_stream.getvalue() if isinstance(path_or_stream, BytesIO) else path_or_stream
        with pypdfium2_lock:                              # pdfium must never be used by two threads at once
            self._pdf: pdfium.PdfDocument | None = pdfium.PdfDocument(source)

    def iter_pages(self):
        for page in super().iter_pages():
            page.get_page_image = partial(self._draw, page.page_no - 1)    # this page's drawing, by pdfium
            yield page

    def _draw(self, index: int, scale: float = 1, cropbox: BoundingBox | None = None) -> Image.Image:
        with pypdfium2_lock:
            return draw_page(self._pdf, index, scale, cropbox)

    def unload(self) -> None:
        super().unload()
        with pypdfium2_lock:
            if getattr(self, "_pdf", None) is not None:  # not there if docling-parse refused the file
                self._pdf.close()
                self._pdf = None


@contextmanager
def _lines_without_drawing():
    """While docling-parse is set up: measure the page's lines and boxes although nothing is drawn."""
    make_config = getattr(docling_parse_backend, "_make_docling_parse_page_content_config", None)
    if make_config is None:                               # another Docling: its own choice, but say so
        logger.warning("Docling changed: docling-parse may not measure page lines now, reading order may suffer")
        yield
        return

    def with_lines(**settings):
        return make_config(**{**settings, "compute_shapes": True})

    with _setup_lock:
        docling_parse_backend._make_docling_parse_page_content_config = with_lines
        try:
            yield
        finally:
            docling_parse_backend._make_docling_parse_page_content_config = make_config


def draw_page(pdf: pdfium.PdfDocument, index: int, scale: float = 1,
              cropbox: BoundingBox | None = None) -> Image.Image:
    """The page as an RGB picture, `scale` pixels per point; with a cropbox, only that part of the visible page.
    The caller holds pypdfium2_lock."""
    page = pdf[index]
    try:
        width, height = page.get_size()                   # the visible page, in points
        box = (cropbox.to_top_left_origin(height) if cropbox is not None
               else BoundingBox(l=0, t=0, r=width, b=height, coord_origin=CoordOrigin.TOPLEFT))
        cut = (box.l, height - box.b, width - box.r, box.t)              # what to cut off: left, bottom, right, top
        bitmap = page.render(scale=scale * _SHARPER, crop=tuple(max(0.0, side) for side in cut))
        try:
            image = bitmap.to_pil().convert("RGB")       # a copy: the bitmap's memory is freed below
        finally:
            bitmap.close()
    finally:
        page.close()
    return image.resize((max(1, round(box.width * scale)), max(1, round(box.height * scale))))
