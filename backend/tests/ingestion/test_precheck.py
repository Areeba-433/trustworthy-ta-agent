import pypdfium2 as pdfium
import pytest

from app.ingestion import messages
from app.ingestion.precheck import UnsupportedFileType, precheck


def test_scanned_pdf_goes_to_ocr(scanned_pdf):
    result = precheck(scanned_pdf)
    assert result.ok
    assert result.source_type == "scanned_pdf"
    assert result.scanned_pages == [1]


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