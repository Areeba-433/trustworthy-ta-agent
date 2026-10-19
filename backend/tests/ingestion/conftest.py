
from types import SimpleNamespace
import pypdfium2 as pdfium
import pytest
from docling_core.types.doc.base import BoundingBox
from docling_core.types.doc.document import DoclingDocument
from docling_core.types.doc.labels import DocItemLabel
from docling_core.types.doc.common.reference import ProvenanceItem
from PIL import Image, ImageDraw

from app.core.config import settings
from app.ingestion.chunking import tokens
from app.ingestion.converter import Conversion

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


@pytest.fixture
def word_tokens(monkeypatch):
    """count_tokens() counts one token per word: no tokenizer download, and every size is easy to read."""
    class _WordTokenizer:
        def encode(self, text: str, add_special_tokens: bool = True) -> SimpleNamespace:
            return SimpleNamespace(ids=text.split())

    monkeypatch.setattr(tokens, "get_tokenizer", lambda: _WordTokenizer())


@pytest.fixture(autouse=True)
def fake_docling_pdf(monkeypatch):
    """Unit tests never run Docling's PDF models: they are slow and download on first use. The PDF loader gets
    fake_pdf_convert() instead; a test can ask for this fixture to call the fake itself.
    The real models are tested in test_converter.py with DOCLING_PDF_TEST=1."""
    from app.ingestion.loaders import pdf

    monkeypatch.setattr(pdf, "convert", fake_pdf_convert)
    return fake_pdf_convert


def fake_pdf_convert(path, source_type, file_sha256=None) -> Conversion:
    """A stand-in for Docling: each page's text layer becomes one paragraph with its page number."""
    document = DoclingDocument(name=path.stem)
    pdf_file = pdfium.PdfDocument(str(path))
    try:
        for i in range(len(pdf_file)):
            text = pdf_file[i].get_textpage().get_text_range().strip()
            if text:
                box = BoundingBox(l=0, t=0, r=1, b=1)
                document.add_text(DocItemLabel.TEXT, text,
                                  prov=ProvenanceItem(page_no=i + 1, bbox=box, charspan=(0, len(text))))
    finally:
        pdf_file.close()
    return Conversion(document)