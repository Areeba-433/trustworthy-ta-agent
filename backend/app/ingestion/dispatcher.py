"""Pre-check and routing: sends each file to exactly one track. Owner: Minahil.

    doc = dispatch(path, ResourceMeta(resource_id=..., course_id=..., file_name=...))

PDFs get a fast pre-check with pypdfium2 (milliseconds per page, no AI models):
digital PDFs go to Track 1, PDFs with scanned pages or a garbled text layer go
to Track 2. Every other type is routed by its extension. The dispatcher never
lets a loader's crash escape: the teacher gets a failed document with a
readable warning instead.
"""

from __future__ import annotations

import logging
import time
import unicodedata
from importlib.metadata import version
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from app.ingestion.contract import ParsedDocument, QualityReport, ResourceMeta, SourceType
from app.ingestion.registry import get_loader
from app.ingestion.storage import file_sha256, save_parsed

log = logging.getLogger(__name__)

EXTENSIONS: dict[str, SourceType] = {
    ".pdf": "pdf",            # the pre-check may change this to "scanned_pdf"
    ".docx": "docx",
    ".pptx": "pptx",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".webp": "image",
    ".tif": "image", ".tiff": "image", ".bmp": "image",
    ".mp3": "audio", ".m4a": "audio", ".wav": "audio",
    ".cpp": "code", ".cc": "code", ".cxx": "code", ".c": "code", ".h": "code", ".hpp": "code",
    ".txt": "text", ".md": "text",
}

# Messages the teacher sees. Share any change with whoever builds the upload UI.
UNSUPPORTED = ("This file type isn't supported. Upload a PDF, Word, PowerPoint, "
               "image, audio, C++ or text file.")
PDF_PASSWORD = "This PDF is password-protected. Please upload an unlocked copy."
PDF_UNREADABLE = ("We couldn't open this PDF. Check that it opens normally on your "
                  "computer, then upload it again.")
LOADER_CRASHED = ("We couldn't read this file. Check that it opens normally, "
                  "then upload it again.")

# Pre-check thresholds, version 0. Tune them on real course files and log the
# final values in docs/ingestion-decisions.md (Areeba needs to know: they decide
# which PDFs reach Track 1).
MIN_TEXT_CHARS = 20       # fewer non-space characters than this = no real text layer
SCAN_IMAGE_COVER = 0.5    # ...and pictures covering half the page or more = a scanned page
LARGE_IMAGE_COVER = 0.3   # digital page whose pictures cover 30%+ may have text inside them
GARBAGE_SHARE = 0.05      # share of unreadable characters that marks a broken text layer


class UnsupportedFileType(ValueError):
    """Raised before any work is done; the upload API turns it into a 400 with this message."""


def source_type_for(path: Path) -> SourceType | None:
    """The source type implied by the extension alone ("pdf" before the pre-check)."""
    return EXTENSIONS.get(Path(path).suffix.lower())


def is_supported(file_name: str) -> bool:
    """For the upload API: reject unknown types before saving the file."""
    return source_type_for(Path(file_name)) is not None


# ---------------------------------------------------------------------------
# PDF pre-check
# ---------------------------------------------------------------------------

def _is_garbage(ch: str) -> bool:
    code = ord(ch)
    return (ch == "\ufffd"                          # replacement character
            or 0xE000 <= code <= 0xF8FF             # private-use area (broken font mappings)
            or 0x00C0 <= code <= 0x024F             # Latin-1/Extended letters: InPage Urdu shows up as these
            or unicodedata.category(ch) == "Cc")    # control characters


def garbage_share(text: str) -> float:
    chars = [ch for ch in text if not ch.isspace()]
    if not chars:
        return 0.0
    return sum(_is_garbage(ch) for ch in chars) / len(chars)


def _image_cover(page: pdfium.PdfPage) -> float:
    """Share of the page covered by pictures (overlaps counted twice; capped at 1)."""
    width, height = page.get_size()
    if width <= 0 or height <= 0:
        return 0.0
    area = 0.0
    for obj in page.get_objects(filter=(pdfium_c.FPDF_PAGEOBJ_IMAGE,)):
        # pypdfium2 v5 calls it get_bounds(); v4 (which Docling may pin) calls it get_pos()
        bounds = obj.get_bounds() if hasattr(obj, "get_bounds") else obj.get_pos()
        left, bottom, right, top = bounds
        w = max(0.0, min(right, width) - max(left, 0.0))
        h = max(0.0, min(top, height) - max(bottom, 0.0))
        area += w * h
    return min(1.0, area / (width * height))


def precheck_pdf(path: Path) -> dict:
    """Per-page text and picture check. Raises PdfiumError if the PDF can't be opened."""
    pdf = pdfium.PdfDocument(str(path))
    pages = []
    try:
        for index in range(len(pdf)):
            page = pdf[index]
            try:
                textpage = page.get_textpage()
                text = textpage.get_text_range()
                textpage.close()
                cover = _image_cover(page)
            finally:
                page.close()
            chars = sum(not ch.isspace() for ch in text)
            pages.append((index + 1, chars, garbage_share(text), cover))
    finally:
        pdf.close()  # Windows keeps the file locked until this runs

    scanned = [n for n, chars, _, cover in pages if chars < MIN_TEXT_CHARS and cover >= SCAN_IMAGE_COVER]
    garbled = [n for n, chars, share, _ in pages if chars >= MIN_TEXT_CHARS and share > GARBAGE_SHARE]
    large_images = [n for n, _, _, cover in pages if n not in scanned and cover >= LARGE_IMAGE_COVER]
    total_chars = sum(chars for _, chars, _, _ in pages)

    if scanned:
        reason = "scanned pages"
    elif garbled:
        reason = "garbled text layer"
    elif pages and total_chars < MIN_TEXT_CHARS:
        reason = "no text layer"   # e.g. text drawn as shapes: only OCR can read it
    else:
        reason = "digital"
    return {
        "pages": len(pages),
        "per_page": [{"page": n, "chars": chars, "garbage": round(share, 3), "image_cover": round(cover, 3)}
                     for n, chars, share, cover in pages],
        "scanned_pages": scanned,
        "garbled_pages": garbled,
        "large_image_pages": large_images,   # Track 1 turns on picture OCR for these
        "route": "pdf" if reason == "digital" else "scanned_pdf",
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def failed_document(path: Path, meta: ResourceMeta, source_type: SourceType, warning: str,
                    *, parser: str, parser_version: str) -> ParsedDocument:
    """A contract-valid 'failed' result. Loaders may use it too."""
    path = Path(path)
    name = meta.file_name or path.name
    return ParsedDocument(
        resource_id=meta.resource_id, course_id=meta.course_id, file_name=name,
        file_sha256=file_sha256(path), source_type=source_type, title=Path(name).stem,
        parser=parser, parser_version=parser_version, blocks=[],
        quality=QualityReport(status="failed", warnings=[warning], units_total=0, chars_total=0),
    )


def _pdf_open_warning(error: Exception) -> str:
    text = str(error).lower()
    return PDF_PASSWORD if ("password" in text or "encrypt" in text) else PDF_UNREADABLE


def dispatch(path: Path, meta: ResourceMeta, *, save: bool = True) -> ParsedDocument:
    """Pre-check, route to one track, time it, save parsed/<resource_id>/parsed.json."""
    started = time.perf_counter()
    path = Path(path)
    source_type = source_type_for(path)
    if source_type is None:
        raise UnsupportedFileType(UNSUPPORTED)

    precheck: dict = {}
    if source_type == "pdf":
        try:
            precheck = precheck_pdf(path)
        except pdfium.PdfiumError as error:
            log.info("Pre-check could not open %s: %s", path.name, error)
            doc = failed_document(path, meta, "pdf", _pdf_open_warning(error),
                                  parser="pypdfium2", parser_version=version("pypdfium2"))
            return _finish(doc, started, time.perf_counter(), save)
        except Exception:  # a bug in the pre-check must not block uploads
            log.exception("Pre-check crashed on %s; sending it to Track 1 unchecked", path.name)
            precheck = {"route": "pdf", "reason": "pre-check failed", "large_image_pages": []}
        source_type = precheck["route"]
    precheck_done = time.perf_counter()

    meta = meta.model_copy(update={"precheck": precheck})
    try:
        loader = get_loader(source_type)
        doc = loader(path, meta)
    except Exception:  # a loader must never take the worker down
        log.exception("Loader for %s crashed on %s", source_type, path.name)
        doc = failed_document(path, meta, source_type, LOADER_CRASHED,
                              parser=f"loader:{source_type}", parser_version="unknown")
    return _finish(doc, started, precheck_done, save)


def _finish(doc: ParsedDocument, started: float, precheck_done: float, save: bool) -> ParsedDocument:
    now = time.perf_counter()
    doc.quality.seconds_taken = {
        "precheck": round(precheck_done - started, 3),
        **doc.quality.seconds_taken,
        "dispatch_total": round(now - started, 3),
    }
    if save:
        save_parsed(doc)
    return doc
