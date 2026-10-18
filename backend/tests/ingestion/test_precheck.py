import pypdfium2 as pdfium
import pytest

from app.ingestion import messages
from app.ingestion.precheck import SUPPORTED_EXTENSIONS, UnsupportedFileType, precheck


def test_digital_pdf_is_accepted(digital_pdf):
    result = precheck(digital_pdf)
    assert result.ok
    assert result.source_type == "pdf"
    assert result.pages_total == 3
    assert result.scanned_pages == []


def test_scanned_pdf_is_refused_with_a_clear_message(scanned_pdf):
    result = precheck(scanned_pdf)
    assert not result.ok
    assert result.reason == messages.SCANNED_PDF


def test_book_with_a_picture_cover_is_accepted(make_pdf):
    result = precheck(make_pdf(scanned=1, text=4))      # 1 page in 5 has no text: exactly at the limit
    assert result.ok
    assert result.scanned_pages == [1]                  # listed, so the loader can skip it and say so


def test_mostly_scanned_pdf_is_refused(make_pdf):
    result = precheck(make_pdf(scanned=2, text=3))      # 2 pages in 5 have no text: over the limit
    assert not result.ok
    assert result.reason == messages.SCANNED_PDF


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


@pytest.mark.parametrize("name", ["setup.exe", "scan.tif", "scan.tiff", "old.doc", "old.ppt",
                                  "photo.png", "photo.jpg", "photo.jpeg"])
def test_unsupported_types_are_refused(tmp_path, name):
    path = tmp_path / name
    path.write_bytes(b"anything")
    with pytest.raises(UnsupportedFileType):
        precheck(path)


def test_supported_types_match_the_upload_page():
    # If this fails, the list of types changed: update the upload page text too.
    assert set(SUPPORTED_EXTENSIONS) == {".pdf", ".docx", ".pptx", ".mp3", ".m4a", ".wav",
                                         ".cpp", ".h", ".hpp", ".txt", ".md"}