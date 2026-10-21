"""Figures in PDF books: remember where each one is, and cut it out of the PDF when an answer needs it.

A figure is a picture. Its words cannot be searched (we do no OCR), and OCR would lose what a diagram means anyway:
its arrows. So nothing is turned into text here. Instead:
- mark_figures() writes the figure's place into the blocks that belong to it, its caption and the words drawn
  inside it: extra["figure"] = {"page": 424, "box": [left, top, right, bottom]}, the box as fractions of the visible
  page, measured from its top-left corner. Retrieval finds the caption ("FIGURE 9.7 Public and private derivation")
  like any text, and through the chunk's block_seqs reaches this note.
- render_figure() then cuts that box out of the stored original PDF as a PNG, in milliseconds: no image is stored.
  The answer step can give it to a vision-capable LLM, and the student's screen can show it as the source.

Docling measures boxes on its own page, which is the visible page (the crop box), so fractions of it are the same in
any PDF reader.
"""
import io
from collections.abc import Sequence
from pathlib import Path

import pypdfium2 as pdfium
from docling_core.types.doc import DoclingDocument, PictureItem

from app.ingestion.contract import Block

_MARGIN = 6.0           # points around the figure, so a cut-out never clips its edge


def mark_figures(blocks: Sequence[Block], doc: DoclingDocument) -> list[Block]:
    """The same blocks; the caption and inner words of every placed figure get extra["figure"]."""
    figure_of: dict[str, dict] = {}                       # Docling id of a caption or an inner word -> its figure
    for picture in doc.pictures:
        figure = _place(picture, doc)
        if figure is None:
            continue
        for ref in picture.captions:
            figure_of[ref.cref] = figure
        for item, _ in doc.iterate_items(root=picture, traverse_pictures=True):
            if item is not picture:
                figure_of[item.self_ref] = figure
    return [b.model_copy(update={"extra": {**b.extra, "figure": figure_of[b.extra["ref"]]}})
            if b.extra.get("ref") in figure_of else b for b in blocks]


def _place(picture: PictureItem, doc: DoclingDocument) -> dict | None:
    if len(picture.prov) != 1:
        return None
    prov = picture.prov[0]
    page = doc.pages.get(prov.page_no)
    if page is None or page.size.width <= 0 or page.size.height <= 0:
        return None
    w, h = page.size.width, page.size.height
    box = prov.bbox.to_top_left_origin(h)
    return {"page": prov.page_no,
            "box": [round(max(0.0, box.l / w), 4), round(max(0.0, box.t / h), 4),
                    round(min(1.0, box.r / w), 4), round(min(1.0, box.b / h), 4)]}


def render_figure(pdf_path: Path, figure: dict, dpi: int = 150) -> bytes:
    """The figure cut out of the PDF, as PNG bytes. 150 dpi keeps labels readable and the image small."""
    left, top, right, bottom = figure["box"]
    out = io.BytesIO()
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        page = pdf[figure["page"] - 1]
        w, h = page.get_size()                            # the visible page, in points
        crop = (max(0.0, left * w - _MARGIN), max(0.0, (1 - bottom) * h - _MARGIN),
                max(0.0, (1 - right) * w - _MARGIN), max(0.0, top * h - _MARGIN))   # cut from each side: l, b, r, t
        page.render(scale=dpi / 72, crop=crop).to_pil().save(out, format="PNG")    # before the PDF is closed
        page.close()
    finally:
        pdf.close()
    return out.getvalue()
