import pypdfium2 as pdfium
import pytest
from PIL import Image, ImageDraw

from app.core.config import settings


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Every test writes into its own empty temporary folder."""
    monkeypatch.setattr(settings, "INGESTION_DATA_DIR", str(tmp_path / "data"))
    return tmp_path / "data"


@pytest.fixture
def scanned_pdf(tmp_path):
    """A picture-only PDF, made fresh for each test, like a scanner produces."""
    page = Image.new("RGB", (1240, 1754), "white")
    ImageDraw.Draw(page).text((100, 100), "Third normal form removes transitive dependencies.", fill="black")
    path = tmp_path / "scanned.pdf"
    page.save(path)
    return path


def write_text_pdf(path, pages):
    """A typed PDF with real text on every page, like a digital book. Written by hand: no extra library."""
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for i in range(pages):
        text = f"BT /F1 12 Tf 72 720 Td (Page {i + 1}: a linked list keeps each value in its own node.) Tj ET".encode()
        objects.append(b"<< /Length %d >>\nstream\n" % len(text) + text + b"\nendstream")
        objects.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents %d 0 R "
                       b"/Resources << /Font << /F1 3 0 R >> >> >>" % len(objects))
        kids.append(b"%d 0 R" % len(objects))
    objects[1] = b"<< /Type /Pages /Kids [" + b" ".join(kids) + b"] /Count %d >>" % pages
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref_at = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref_at)
    path.write_bytes(bytes(out))
    return path


@pytest.fixture
def digital_pdf(tmp_path):
    """A 3-page typed PDF: the normal case for a digital book."""
    return write_text_pdf(tmp_path / "digital.pdf", 3)


@pytest.fixture
def make_pdf(tmp_path):
    """make_pdf(scanned=1, text=4): picture-only pages first (like a book cover), then typed pages."""
    def make(scanned, text):
        typed = pdfium.PdfDocument(str(write_text_pdf(tmp_path / "typed.pdf", text)))
        picture = Image.new("RGB", (620, 877), "white")
        picture.save(tmp_path / "pictures.pdf", save_all=True, append_images=[picture] * (scanned - 1))
        mixed = pdfium.PdfDocument(str(tmp_path / "pictures.pdf"))
        mixed.import_pages(typed)
        out = tmp_path / f"mixed_{scanned}_{text}.pdf"
        mixed.save(str(out))
        mixed.close()
        typed.close()
        return out
    return make