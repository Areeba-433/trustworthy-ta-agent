"""Cheap checks that decide which loader gets a file. No AI models; milliseconds per page."""
import time
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from PIL import Image

from app.core.config import settings
from app.ingestion import messages
from app.ingestion.cleaning.common import garbage_share
from app.ingestion.contract import PrecheckResult, SourceType

SUPPORTED_EXTENSIONS: dict[str, SourceType] = {
    ".pdf": "pdf", ".docx": "docx", ".pptx": "pptx",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".tif": "image", ".tiff": "image",
    ".mp3": "audio", ".m4a": "audio", ".wav": "audio",
    ".cpp": "code", ".h": "code", ".hpp": "code",
    ".txt": "text", ".md": "text",
}
_MAGIC: dict[str, tuple[bytes, ...]] = {            # the signature each file type starts with
    "pdf": (b"%PDF",),
    "docx": (b"PK\x03\x04",),
    "pptx": (b"PK\x03\x04",),
    "image": (b"\x89PNG", b"\xff\xd8\xff", b"II*\x00", b"MM\x00*"),
}
MIN_LETTERS_PER_PAGE = 25      # starting values: tune them on real samples later
SCANNED_IMAGE_SHARE = 0.5
LARGE_IMAGE_SHARE = 0.3
GARBAGE_MAX = 0.15


class UnsupportedFileType(ValueError):
    pass


def precheck(path: Path) -> PrecheckResult:
    start = time.perf_counter()
    source_type = SUPPORTED_EXTENSIONS.get(path.suffix.lower())
    if source_type is None:
        raise UnsupportedFileType(path.suffix)
    result = _check(path, source_type)
    result.seconds = round(time.perf_counter() - start, 4)
    return result


def _fail(source_type: SourceType, reason: str) -> PrecheckResult:
    return PrecheckResult(source_type=source_type, ok=False, reason=reason)


def _check(path: Path, source_type: SourceType) -> PrecheckResult:
    if path.stat().st_size > settings.INGESTION_MAX_FILE_MB * 1024 * 1024:
        return _fail(source_type, messages.TOO_LARGE)
    expected = _MAGIC.get(source_type)
    if expected:
        with path.open("rb") as f:
            if not f.read(8).startswith(expected):
                return _fail(source_type, messages.TYPE_MISMATCH)
    if source_type == "pdf":
        return _check_pdf(path)
    if source_type == "image":
        try:
            with Image.open(path) as im:
                im.verify()                     # quick check that the image isn't broken
        except Exception:
            return _fail("image", messages.UNREADABLE)
    return PrecheckResult(source_type=source_type)


def _image_share(page) -> float:
    """How much of the page (0 to 1) is covered by pictures."""
    width, height = page.get_size()
    if not width or not height:
        return 0.0
    covered = 0.0
    for obj in page.get_objects(filter=(pdfium_c.FPDF_PAGEOBJ_IMAGE,), max_depth=2):
        left, bottom, right, top = obj.get_bounds()
        covered += max(0.0, right - left) * max(0.0, top - bottom)
    return min(1.0, covered / (width * height))


def _check_pdf(path: Path) -> PrecheckResult:
    try:
        pdf = pdfium.PdfDocument(str(path))
    except pdfium.PdfiumError as err:
        password = "password" in str(err).lower()
        return _fail("pdf", messages.PASSWORD_PROTECTED if password else messages.UNREADABLE)
    scanned, garbage, large = [], [], []
    try:
        total = len(pdf)
        for i in range(total):
            page = pdf[i]
            text = page.get_textpage().get_text_range()
            letters = sum(ch.isalnum() for ch in text)        # counts Urdu letters too
            share = _image_share(page)
            if letters < MIN_LETTERS_PER_PAGE and share >= SCANNED_IMAGE_SHARE:
                scanned.append(i + 1)                        # almost no text, mostly picture: a scan
            elif letters >= MIN_LETTERS_PER_PAGE and garbage_share(text) > GARBAGE_MAX:
                garbage.append(i + 1)                        # has text, but it's broken
            if share >= LARGE_IMAGE_SHARE:
                large.append(i + 1)
    finally:
        pdf.close()
    return PrecheckResult(
        source_type="scanned_pdf" if (scanned or garbage) else "pdf",
        pages_total=total, scanned_pages=scanned, garbage_pages=garbage, large_image_pages=large,
    )