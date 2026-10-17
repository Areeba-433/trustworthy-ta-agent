"""Formulas in digital PDFs (app/ingestion/loaders/pdf_math.py): symbols with no Unicode named by their
shape, and formulas set on their own lines rebuilt as LaTeX from where each glyph sits."""
import ctypes
import io

import pytest

pdfium = pytest.importorskip("pypdfium2")
import pypdfium2.raw as pdfium_c  # noqa: E402

from app.ingestion.loaders import fast_pdf, pdf_math  # noqa: E402
from app.ingestion.loaders.pdf_math import Bar, Glyph, to_latex  # noqa: E402


def g(ch: str, x: float, base: float, size: float = 10.0, height: float | None = None) -> Glyph:
    h = height if height is not None else 0.7 * size
    return Glyph(ch, x, base, x + 0.5 * size, base + h, base, size)


def test_a_fraction_and_scripts():
    glyphs = [g("y", 0, 100), g("=", 8, 100), g("a", 16, 106), g("b", 16, 92), g("x", 26, 100),
              g("i", 31, 98.5, 7), g("2", 31, 104, 7)]
    assert to_latex(glyphs, [Bar(15, 22, 103)]) == "y = \\frac{a}{b} x_i^2"


def test_a_sum_with_limits_and_a_root():
    big = Glyph("∑", 0, 96, 13, 110, 96, 10)                          # a display sum: 1.4 times as tall
    glyphs = [big, g("i", 2, 89, 7), g("=", 5, 89, 7), g("1", 9, 89, 7), g("n", 5, 112, 7),
              g("x", 16, 100), g("+", 23, 100), g("√", 30, 97, 10, 10), g("n", 36, 100)]
    assert to_latex(glyphs, [Bar(35, 42, 107)]) == "\\sum_{i=1}^{n} x + \\sqrt{n}"


def test_half_a_fraction_keeps_the_pdf_text():
    glyphs = [g("x", 0, 100), g("=", 8, 100), g("1", 16, 92)]       # the numerator is not in the formula
    assert to_latex(glyphs, [Bar(15, 22, 99)]) is None


def test_a_glyph_never_goes_missing():
    glyphs = [g("x", 0, 100), g("?", 8, 100)]                          # a symbol not recognised
    assert to_latex(glyphs, []) is None


def _page_with(objects, lines=()):
    """A PDF page drawn with pdfium's own fonts: objects are (font, text, x, y, size); lines are (x0, x1, y)."""
    doc = pdfium.PdfDocument.new()
    page = doc.new_page(400, 300)
    fonts = {}
    for font_name, text, x, y, size in objects:
        font = fonts.setdefault(font_name, pdfium_c.FPDFText_LoadStandardFont(doc.raw, font_name.encode()))
        obj = pdfium_c.FPDFPageObj_CreateTextObj(doc.raw, font, ctypes.c_float(size))
        buf = ctypes.create_string_buffer((text + "\0").encode("utf-16-le"))
        pdfium_c.FPDFText_SetText(obj, ctypes.cast(buf, pdfium_c.FPDF_WIDESTRING))
        pdfium_c.FPDFPageObj_Transform(obj, 1, 0, 0, 1, x, y)
        pdfium_c.FPDFPage_InsertObject(page.raw, obj)
    for x0, x1, y in lines:
        path = pdfium_c.FPDFPageObj_CreateNewPath(ctypes.c_float(x0), ctypes.c_float(y))
        pdfium_c.FPDFPath_LineTo(path, ctypes.c_float(x1), ctypes.c_float(y))
        pdfium_c.FPDFPath_SetDrawMode(path, 0, 1)
        pdfium_c.FPDFPageObj_SetStrokeWidth(path, ctypes.c_float(0.5))
        pdfium_c.FPDFPage_InsertObject(page.raw, path)
    pdfium_c.FPDFPage_GenerateContent(page.raw)
    out = io.BytesIO()
    doc.save(out)
    return pdfium.PdfDocument(out.getvalue())


def test_a_formula_on_its_own_line_is_rebuilt():
    text = [("Helvetica", line, 40, 250 - 14 * k, 10) for k, line in enumerate([
        "The mean of the values is their sum over how many there are,",
        "which is written as follows in this book, for every sample:"])]
    formula = [("Helvetica", "y", 120, 180, 10), ("Helvetica", "=", 130, 180, 10),
               ("Symbol", "∑", 142, 186, 10), ("Helvetica", "a", 150, 186, 10),
               ("Helvetica", "n", 146, 172, 10), ("Helvetica", "(1.1)", 330, 180, 10)]
    after = [("Helvetica", "This is the next paragraph of the book, going on as usual.", 40, 150, 10)]
    pdf = _page_with(text + formula + after, lines=[(140, 158, 183)])
    scan = fast_pdf.scan_page(pdf, 0)
    assert [latex for _, latex, _ in scan.formulas] == ["y = \\frac{\\sum a}{n} (1.1)"]
    assert any(ln.formula and "∑" in ln.source for ln in scan.lines)
    assert sum(1 for ln in scan.lines if "next paragraph" in ln.text) == 1      # the text around it is untouched


@pytest.mark.parametrize("symbol", ["∑", "=", "×", "−", "√", "("])
def test_a_symbol_is_named_by_its_shape(symbol):
    pdf = _page_with([("Symbol", symbol, 100, 100, 20)])
    page = pdf[0]
    textpage = page.get_textpage()
    l, r, b, t = (ctypes.c_double() for _ in range(4))
    pdfium_c.FPDFText_GetCharBox(textpage.raw, 0, ctypes.byref(l), ctypes.byref(r), ctypes.byref(b), ctypes.byref(t))
    assert pdf_math.recognise(page, (l.value, b.value, r.value, t.value), (0.0, 300.0)) == symbol


def test_a_rebuilt_formula_keeps_the_pdf_reading_beside_it():
    from docling_core.types.doc import DocItemLabel, DoclingDocument

    from app.ingestion.loaders import docs

    d = DoclingDocument(name="notes")
    d.add_text(label=DocItemLabel.FORMULA, text="\\frac{1}{n}", orig="1\nn")
    block = docs.walk(d, "pdf", "notes")[0]
    assert (block["kind"], block["text"]) == ("paragraph", "\\frac{1}{n}")
    assert block["extra"]["formula"] and block["extra"]["pdf_text"] == "1\nn"
