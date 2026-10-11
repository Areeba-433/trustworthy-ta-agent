from pathlib import Path

import pypdfium2 as pdfium
import pytest

from app.ingestion import messages
from app.ingestion.precheck import UnsupportedFileType, precheck


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


def test_unknown_file_type_is_refused(tmp_path):
    exe = tmp_path / "setup.exe"
    exe.write_bytes(b"MZ")
    with pytest.raises(UnsupportedFileType):
        precheck(exe)