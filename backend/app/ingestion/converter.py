"""Run Docling on a file. One converter per format, built once, because loading the AI models takes seconds."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING

from docling.datamodel.base_models import ConversionStatus, DoclingComponentType, InputFormat
from docling.datamodel.pipeline_options import (HeadingHierarchyOptions, PdfPipelineOptions, TableFormerMode,
                                                TableStructureOptions)
from docling_core.types.doc import DoclingDocument

from app.ingestion import messages
from app.ingestion.documents import FileRefused

if TYPE_CHECKING:                          # for type hints only: the real import waits until it's needed
    from docling.document_converter import DocumentConverter

logger = logging.getLogger("tta.ingestion")

PARSER = "docling"
PARSER_VERSION = version("docling")        # saved in parsed.json: which Docling read each file
PDF_TIMEOUT_SECONDS = 3600.0               # a safety net for a stuck file, not a speed target: tune after measuring

_FORMATS = {"pdf": InputFormat.PDF, "docx": InputFormat.DOCX, "pptx": InputFormat.PPTX}


def pdf_options() -> PdfPipelineOptions:
    """Our PDF settings. Defaults are written out too, so a Docling upgrade can't change them quietly."""
    return PdfPipelineOptions(
        do_ocr=False,                      # digital files only (the pre-check refuses scans); OCR is the slowest
        do_table_structure=True,
        table_structure_options=TableStructureOptions(mode=TableFormerMode.FAST),
        heading_hierarchy_options=HeadingHierarchyOptions(enabled=True),   # levels from bookmarks and "5.3"
        do_code_enrichment=False,          # an extra model per code block: only if listings lose structure
        do_formula_enrichment=False,       # slow, and O(n log n) in a digital book is plain text already
        generate_page_images=False,        # less memory; the original PDF is kept to show pages later
        generate_picture_images=False,
        document_timeout=PDF_TIMEOUT_SECONDS,
    )


@lru_cache(maxsize=None)
def get_converter(source_type: str) -> DocumentConverter:
    """The converter for one format. Built on first use and kept, so its loaded models are reused."""
    if source_type not in _FORMATS:
        raise ValueError(f"Docling doesn't read {source_type!r} files here")
    from docling.document_converter import DocumentConverter, PdfFormatOption   # slow import: only when needed

    fmt = _FORMATS[source_type]
    options = {fmt: PdfFormatOption(pipeline_options=pdf_options())} if fmt is InputFormat.PDF else {}
    return DocumentConverter(allowed_formats=[fmt], format_options=options)


@dataclass(frozen=True)
class Conversion:
    document: DoclingDocument
    problems: tuple[str, ...] = ()         # passed on to parsed_document(problems=...)


def convert(path: Path, source_type: str) -> Conversion:
    """Docling's result in our words. A broken file raises FileRefused; a crash in Docling raises RuntimeError."""
    result = get_converter(source_type).convert(path, raises_on_error=False)
    status = result.status
    if status == ConversionStatus.SUCCESS:
        return Conversion(result.document)
    if status == ConversionStatus.PARTIAL_SUCCESS:     # e.g. the timeout hit: keep what was read, and say so
        logger.warning("docling partial: %s: %s", path.name, [e.error_message for e in result.errors])
        return Conversion(result.document, (messages.PARTIAL,))
    if status == ConversionStatus.SKIPPED:             # Docling found another format inside: slides named .docx
        raise FileRefused(messages.TYPE_MISMATCH)
    if any(e.component_type == DoclingComponentType.USER_INPUT for e in result.errors):
        raise FileRefused(messages.UNREADABLE)         # the file itself is broken
    raise RuntimeError(f"Docling {status.value} on {path.name}: {[e.error_message for e in result.errors]}")