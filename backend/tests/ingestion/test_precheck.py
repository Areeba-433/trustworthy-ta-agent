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