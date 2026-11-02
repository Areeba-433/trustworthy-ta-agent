import zlib
from types import SimpleNamespace

import pypdfium2 as pdfium
import pytest
from docling_core.types.doc import BoundingBox, CoordOrigin, DocItemLabel, DoclingDocument, ProvenanceItem
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


def write_pdf(path, pages, fonts=("Helvetica",), mediabox=(0, 0, 595, 842), images=()):
    """A PDF written by hand, no extra library. `pages` holds one content stream per page, which names the fonts
    /F1, /F2 ... in the order of `fonts`. Text uses Windows character codes, so curly quotes and apostrophes come
    out as typed. Most PDFs' pages start at (0, 0), but not all: `mediabox` can move the page's corner.
    `images` holds picture objects (dictionary and stream) that every page can draw as /Im0, /Im1 ..."""
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b""]
    objects += [b"<< /Type /Font /Subtype /Type1 /BaseFont /%s /Encoding /WinAnsiEncoding >>" % font.encode()
                for font in fonts]
    font_names = b" ".join(b"/F%d %d 0 R" % (n, n + 2) for n in range(1, len(fonts) + 1))
    resources = b"/Font << %s >>" % font_names
    if images:
        resources += b" /XObject << %s >>" % b" ".join(b"/Im%d %d 0 R" % (n, len(objects) + n + 1)
                                                       for n in range(len(images)))
        objects += list(images)
    kids = []
    for content in pages:
        stream = content.encode("cp1252")
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        objects.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [%s] /Contents %d 0 R /Resources << %s >> >>"
                       % (" ".join(map(str, mediabox)).encode(), len(objects), resources))
        kids.append(b"%d 0 R" % len(objects))
    objects[1] = b"<< /Type /Pages /Kids [" + b" ".join(kids) + b"] /Count %d >>" % len(pages)
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


def write_text_pdf(path, pages):
    """A typed PDF with real text on every page, like a digital book."""
    line = "Page {}: a linked list keeps each value in its own node."
    return write_pdf(path, [f"BT /F1 12 Tf 72 720 Td ({line.format(i + 1)}) Tj ET" for i in range(pages)])


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


def _pdf_string(text):
    """PDF text is written inside (brackets), so brackets and backslashes in it need a backslash first."""
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


@pytest.fixture
def listing_pdf(tmp_path):
    """listing_pdf(lines, by_position=False, corner=(0, 0)): one page like a C++ book: a sentence in Times-Roman,
    `lines` as a code listing in Courier 9 pt (every character exactly 5.4 points wide), then another sentence.
    Indentation is typed as spaces, or by_position: the line simply starts further right, as many books do it.
    A line can also be ("sentence", text): a line of Times-Roman in the listing, as books write between two pieces
    of code; ("note", code, note): code, then 12 columns further a note in Times-Roman beside it; or ("inline",
    text, code): a sentence in Times-Roman that ends with a word of code.
    `corner` is where the page starts in PDF points; one of our real books starts at (54, 55). `tab` adds a chapter
    tab on the page's right edge beside the listing, like the OOP book's odd pages: "9" and "INHERITANCE" turned.
    Returns (path, box): the listing's box in points from the page's corner, as Docling's default reader reports it."""
    def make(lines, by_position=False, corner=(0, 0), tab=False):
        top, step = 700.0, 11.5                                  # first line's baseline; distance between lines
        bottom = top - (len(lines) - 1) * step
        rows = [(72.0, top + 30, "/F2 10", "MULTSHAP draws three shapes:")]       # F1: Courier, F2: Times-Roman
        for n, line in enumerate(lines):
            if isinstance(line, tuple):
                rows.append((72.0, top - n * step, "/F1 9" if line[0] == "note" else "/F2 10", line[1]))
                if line[0] == "note":
                    rows.append((72.0 + 12 * 5.4, top - n * step, "/F2 10", line[2]))
                if line[0] == "inline":                      # after the sentence: Times letters are narrower
                    rows.append((72.0 + len(line[1]) * 5.5, top - n * step, "/F1 9", line[2]))
                continue
            indent = len(line) - len(line.lstrip(" ")) if by_position else 0
            rows.append((72.0 + indent * 5.4, top - n * step, "/F1 9", line[indent:]))
        rows.append((72.0, bottom - 30, "/F2 10", "Because push_front only creates one node, it is fast."))
        dx, dy = corner
        content = "\n".join(f"BT {font} Tf {x + dx} {y + dy} Td ({_pdf_string(text)}) Tj ET"
                            for x, y, font, text in rows if text)
        if tab:                                                  # turned: reads bottom to top
            content += (f"\nBT /F2 12 Tf 0 1 -1 0 {560 + dx} {bottom + dy} Tm (INHERITANCE) Tj ET"
                        f"\nBT /F2 14 Tf {548 + dx} {bottom + 90 + dy} Td (9) Tj ET")
        path = write_pdf(tmp_path / "listing.pdf", [content], fonts=("Courier", "Times-Roman"),
                         mediabox=(dx, dy, dx + 595, dy + 842))
        widest = max((12 + len(line[-1]) if line[0] == "note" else sum(map(len, line[1:]))) if isinstance(line, tuple)
                     else len(line) for line in lines)
        box = BoundingBox(l=71, r=73 + widest * 5.4, t=top + 8, b=bottom - 3,
                          coord_origin=CoordOrigin.BOTTOMLEFT)
        return path, box
    return make


@pytest.fixture
def make_chapter_tab_pdf(tmp_path):
    """make_chapter_tab_pdf(title="INHERITANCE", x=560, corner=(0, 0)): a two-page book. Page 1 has a chapter tab
    on its right edge, like the OOP book's odd pages: the title turned on its side and the chapter's number "9"
    upright above it. Page 2 has none. A smaller x puts the turned text inside the page, like a label in a diagram.
    `corner` moves the page's own corner, like the OOP book whose pages start at (54, 55); the page looks the same."""
    def make(title="INHERITANCE", x=560, corner=(0, 0)):
        dx, dy = corner
        text = f"BT /F1 11 Tf {72 + dx} {700 + dy} Td (Inheritance lets a class reuse another class.) Tj ET"
        tab = (f"BT /F1 12 Tf 0 1 -1 0 {x + dx} {380 + dy} Tm ({title}) Tj ET\n"      # turned: reads bottom to top
               f"BT /F1 14 Tf {x - 12 + dx} {470 + dy} Td (9) Tj ET")
        name = "chapter.pdf" if corner == (0, 0) else "chapter_moved.pdf"
        return write_pdf(tmp_path / name, [text + "\n" + tab, text], mediabox=(dx, dy, dx + 595, dy + 842))
    return make


@pytest.fixture
def chapter_tab_pdf(make_chapter_tab_pdf):
    return make_chapter_tab_pdf()


@pytest.fixture
def figure_pdf(tmp_path):
    """figure_pdf(corner=(0, 0)): one page with a black rectangle where a figure would be: 300 x 200 points, its
    bottom-left corner 100 points from the page's left edge and 300 from its bottom. `corner` moves the page's own
    corner, like the OOP book whose pages start at (54, 55)."""
    def make(corner=(0, 0)):
        dx, dy = corner
        drawing = f"0 0 0 rg {100 + dx} {300 + dy} 300 200 re f"
        return write_pdf(tmp_path / "figure.pdf", [drawing], mediabox=(dx, dy, dx + 595, dy + 842))
    return make


@pytest.fixture
def picture_pdf(tmp_path):
    """picture_pdf(colorspace="DeviceCMYK"): one page with one small picture, Flate-compressed (like PNG) and stored
    in `colorspace`: "DeviceCMYK", the four printing inks, like the pictures on book page 94 that crash docling-parse's
    page drawing; "DeviceRGB" or "DeviceGray", which do not."""
    def make(colorspace="DeviceCMYK"):
        inks = {"DeviceCMYK": 4, "DeviceRGB": 3, "DeviceGray": 1}[colorspace]
        width, height = 80, 48                                         # the first picture on book page 94
        pixels = zlib.compress(bytes((x * 3 + y * 5 + ink * 60) % 256
                                     for y in range(height) for x in range(width) for ink in range(inks)))
        picture = (b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /%s /BitsPerComponent 8"
                   b" /Filter /FlateDecode /Length %d >>\nstream\n" % (width, height, colorspace.encode(), len(pixels))
                   + pixels + b"\nendstream")
        page = "BT /F1 12 Tf 72 720 Td (A page with one small picture.) Tj ET\nq 160 0 0 96 72 580 cm /Im0 Do Q"
        return write_pdf(tmp_path / f"picture_{colorspace}.pdf", [page], mediabox=(0, 0, 612, 792), images=[picture])
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
