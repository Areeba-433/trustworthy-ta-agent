from pathlib import Path

import pypdfium2 as pdfium
import pytest
from PIL import Image

from app.core.config import settings
from app.ingestion import messages
from app.ingestion.precheck import SUPPORTED_EXTENSIONS, UnsupportedFileType, precheck


def test_scanned_pdf_goes_to_ocr(scanned_pdf):
    result = precheck(scanned_pdf)
    assert result.ok
    assert result.source_type == "scanned_pdf"
    assert result.scanned_pages == [1]


def test_a_book_with_a_picture_cover_is_still_digital(scanned_pdf, tmp_path):
    textbook = Path(__file__).parent / "samples" / "fast_pdf" / "textbook.pdf"
    book = pdfium.PdfDocument.new()
    book.import_pages(pdfium.PdfDocument(str(scanned_pdf)))      # a cover that is only a picture
    book.import_pages(pdfium.PdfDocument(str(textbook)))         # then 25 pages of text
    path = tmp_path / "book.pdf"
    book.save(str(path))
    result = precheck(path)
    assert result.source_type == "pdf" and result.scanned_pages == [1]


def test_the_ocr_page_limit_is_only_for_files_that_go_to_ocr(scanned_pdf, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "INGESTION_MAX_OCR_PAGES", 0)
    textbook = Path(__file__).parent / "samples" / "fast_pdf" / "textbook.pdf"
    book = pdfium.PdfDocument.new()
    book.import_pages(pdfium.PdfDocument(str(scanned_pdf)))
    book.import_pages(pdfium.PdfDocument(str(textbook)))
    path = tmp_path / "book.pdf"
    book.save(str(path))
    result = precheck(path)
    assert result.ok and result.source_type == "pdf"             # a digital book is not refused for its cover


def test_mostly_scanned_pages_go_to_ocr(scanned_pdf, tmp_path):
    textbook = Path(__file__).parent / "samples" / "fast_pdf" / "textbook.pdf"
    book = pdfium.PdfDocument.new()
    for _ in range(4):
        book.import_pages(pdfium.PdfDocument(str(scanned_pdf)))
    book.import_pages(pdfium.PdfDocument(str(textbook)), [0, 1])
    path = tmp_path / "mixed.pdf"
    book.save(str(path))
    assert precheck(path).source_type == "scanned_pdf"           # 4 of 6 pages are scans


def test_blank_page_is_not_treated_as_a_scan(tmp_path):
    pdf = pdfium.PdfDocument.new()
    pdf.new_page(595, 842)
    path = tmp_path / "blank.pdf"
    pdf.save(str(path))
    assert precheck(path).scanned_pages == []


def test_renamed_file_is_caught(tmp_path):
    fake = tmp_path / "notes.pdf"
    fake.write_bytes(b"PK\x03\x04 actually a zip file")
    result = precheck(fake)
    assert not result.ok
    assert result.reason == messages.TYPE_MISMATCH


def test_broken_image_is_caught(tmp_path):
    broken = tmp_path / "photo.png"
    broken.write_bytes(b"\x89PNG\r\n\x1a\n not really an image")
    assert precheck(broken).reason == messages.UNREADABLE


@pytest.mark.parametrize("name", ["setup.exe", "scan.tif", "scan.tiff", "old.doc", "old.ppt"])
def test_unsupported_types_are_refused(tmp_path, name):
    path = tmp_path / name
    path.write_bytes(b"anything")
    with pytest.raises(UnsupportedFileType):
        precheck(path)


def test_supported_types_match_the_upload_page():
    # If this fails, the list of types changed: update the upload page text too.
    assert set(SUPPORTED_EXTENSIONS) == {".pdf", ".docx", ".pptx", ".png", ".jpg", ".jpeg",
                                         ".mp3", ".m4a", ".wav", ".cpp", ".h", ".hpp", ".txt", ".md"}


def _scan_with_pages(path, pages):
    """A picture-only PDF with this many pages, like a scanner makes."""
    page = Image.new("RGB", (620, 877), "white")
    page.save(path, save_all=True, append_images=[page] * (pages - 1))
    return path


def test_scan_at_the_page_limit_is_accepted(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "INGESTION_MAX_OCR_PAGES", 2)
    result = precheck(_scan_with_pages(tmp_path / "short_scan.pdf", 2))
    assert result.ok and result.scanned_pages == [1, 2]


def test_scan_over_the_page_limit_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "INGESTION_MAX_OCR_PAGES", 2)
    result = precheck(_scan_with_pages(tmp_path / "long_scan.pdf", 3))
    assert not result.ok
    assert result.source_type == "scanned_pdf"
    assert result.reason == messages.too_many_scanned_pages(2)