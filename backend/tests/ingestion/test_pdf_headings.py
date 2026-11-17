"""split_long_headings(): a heading Docling made of a whole region is cut back to the heading itself."""
from docling_core.types.doc import BoundingBox, CoordOrigin, DoclingDocument, ProvenanceItem, Size

from app.ingestion.docling_blocks import to_blocks
from app.ingestion.pdf_code import restore_code_lines
from app.ingestion.pdf_headings import split_long_headings
from conftest import write_pdf

# (font, baseline, text): F1 Courier (code), F2 Times-Roman (sentences), F3 Helvetica-Bold (headings)
PAGE = [("/F1 9", 700, "c2=2"),
        ("/F3 11", 680, "Nameless Temporary Objects"),
        ("/F2 10", 664, "In COUNTPP2 we created a temporary object of type Counter, named temp, whose"),
        ("/F2 10", 652, "sole purpose was to provide a return value for the operator."),
        ("/F1 9", 638, "Counter temp;"),
        ("/F3 11", 610, "Postfix Notation"),
        ("/F2 10", 594, "So far we have shown the prefix form.")]
LISTING = ["int main()", "   {", "   Counter counter1, counter2;     //define counters",
           "   ++counter1;                     //increment", "   return 0;", "   }"]       # the book's code font


def _page_pdf(tmp_path):
    content = "\n".join(f"BT {font} Tf 72 {y} Td ({text}) Tj ET" for font, y, text in PAGE)
    content += "\n" + "\n".join(f"BT /F1 9 Tf 72 {560 - 11 * n} Td ({line}) Tj ET" for n, line in enumerate(LISTING))
    return write_pdf(tmp_path / "heading.pdf", [content], fonts=("Courier", "Times-Roman", "Helvetica-Bold"))


def _prov(first: int, last: int) -> ProvenanceItem:
    """Docling's box around PAGE's lines first..last, measured from the page's bottom."""
    top, bottom = PAGE[first][1] + 10, PAGE[last][1] - 3
    return ProvenanceItem(page_no=1, bbox=BoundingBox(l=70, r=500, t=top, b=bottom,
                                                      coord_origin=CoordOrigin.BOTTOMLEFT), charspan=(0, 0))


def _doc() -> DoclingDocument:
    """Docling's result: one heading made of the first five lines, a short heading, a paragraph, and a listing
    below (its letters show which font is the code font)."""
    doc = DoclingDocument(name="book")
    doc.add_page(page_no=1, size=Size(width=595, height=842))
    doc.add_heading(" ".join(text for _, _, text in PAGE[:5]), level=2, prov=_prov(0, 4))
    doc.add_heading("Postfix Notation", level=2, prov=_prov(5, 5))
    doc.add_text("text", PAGE[6][2], prov=_prov(6, 6))
    box = BoundingBox(l=70, r=500, t=570, b=500, coord_origin=CoordOrigin.BOTTOMLEFT)
    doc.add_code(" ".join(line.strip() for line in LISTING), prov=ProvenanceItem(page_no=1, bbox=box, charspan=(0, 0)))
    return doc


def test_a_heading_made_of_a_whole_region_is_cut_back_to_its_heading_line(tmp_path):
    """Book page 351: "c2=2 Nameless Temporary Objects In COUNTPP2 we created ..." was one heading, 164 words."""
    path, doc = _page_pdf(tmp_path), _doc()
    assert split_long_headings(doc, path) == 1
    blocks = restore_code_lines(to_blocks(doc, "pdf", "Book"), doc, path)
    assert [(b.kind, b.text) for b in blocks][:4] == [
        ("code", "c2=2"), ("heading", "Nameless Temporary Objects"),
        ("paragraph", "In COUNTPP2 we created a temporary object of type Counter, named temp, whose sole purpose "
                      "was to provide a return value for the operator."),
        ("code", "Counter temp;")]
    assert blocks[2].heading_path == ["Book", "Nameless Temporary Objects"]


def test_short_headings_are_left_alone(tmp_path):
    path, doc = _page_pdf(tmp_path), DoclingDocument(name="book")
    doc.add_page(page_no=1, size=Size(width=595, height=842))
    doc.add_heading("Postfix Notation", level=2, prov=_prov(5, 5))
    assert split_long_headings(doc, path) == 0
    assert doc.texts[0].text == "Postfix Notation"


def test_a_long_heading_whose_words_are_not_the_pdf_s_stays_as_it_is(tmp_path):
    path, doc = _page_pdf(tmp_path), _doc()
    doc.texts[0].text = doc.texts[0].text.replace("temporary", "temporal")
    assert split_long_headings(doc, path) == 0
