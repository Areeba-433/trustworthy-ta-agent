"""Track 2: scanned PDFs and images of printed text, OCR through Docling. Owner: Minahil.

DAY-0 STUB: returns one fake block. Also provides ocr_options(), the one
deliberate shared dependency: Track 1 uses it for pictures inside digital PDFs.
"""

from __future__ import annotations

from pathlib import Path

from app.ingestion.contract import Location, ParsedDocument, ResourceMeta
from app.ingestion.loaders._stub import stub_document
from app.ingestion.registry import register


@register("scanned_pdf", "image")
def load(path: Path, meta: ResourceMeta) -> ParsedDocument:
    source_type = "scanned_pdf" if Path(path).suffix.lower() == ".pdf" else "image"
    return stub_document(path, meta, source_type, kind="ocr_text", loc=Location(page=1),
                         parser="docling+ocr", confidence=0.9)


def ocr_options():
    """STUB until day 4: Docling's own default OCR settings for the installed version.

    Real version: the engine and languages that won the 5-page comparison
    (EasyOCR ["en", "ur"] vs Tesseract "eng+urd"). Announce any change to Areeba.
    """
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    return PdfPipelineOptions().ocr_options
