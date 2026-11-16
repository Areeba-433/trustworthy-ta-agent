"""Slides saved as PDF: one heading per slide, its title, so a slide is one section; labels stay in the text."""
import pytest
from docling_core.types.doc import BoundingBox, CoordOrigin, DocItemLabel, DoclingDocument, ProvenanceItem, Size

from app.ingestion.contract import Block, Location
from app.ingestion.converter import Conversion
from app.ingestion.dispatcher import ingest_file
from app.ingestion.docling_blocks import to_blocks
from app.ingestion.loaders import pdf
from app.ingestion.pdf_slides import as_slides, is_slides, keep_line_breaks
from conftest import write_pdf

T = "Deck"


def _doc(pages: int, width: float = 960, height: float = 540) -> DoclingDocument:
    doc = DoclingDocument(name="deck")
    for page in range(1, pages + 1):
        doc.add_page(page_no=page, size=Size(width=width, height=height))
    return doc


def _blocks(*items: tuple[int, str, str, int]) -> list[Block]:
    """(page, kind, text, depth): depth is the heading_path's length after the title, as to_blocks() made it."""
    paths: list[str] = []
    blocks = []
    for seq, (page, kind, text, depth) in enumerate(items):
        if kind == "heading":
            paths = paths[:depth - 1] + [text]
        blocks.append(Block(seq=seq, kind=kind, text=text, heading_path=[T, *paths[:depth]], loc=Location(page=page),
                            figure_id=f"fig{seq}" if kind == "figure" else None))
    return blocks


def _box(l, b, r, t):
    return BoundingBox(l=l, b=b, r=r, t=t, coord_origin=CoordOrigin.BOTTOMLEFT)


def _out(blocks: list[Block]) -> list[tuple[int, str, str, list[str]]]:
    return [(b.loc.page, b.kind, b.text, b.heading_path[1:]) for b in blocks]


def test_a_slide_s_labels_become_text_under_its_title():
    """DSA slide 5: Docling made headings of "Programs:", "Advantages:", "Limitations:"."""
    blocks = _blocks((5, "heading", "Array Implementation", 1), (5, "heading", "Programs:", 2),
                     (5, "paragraph", "Array Rotation using Recursion", 2), (5, "heading", "Advantages:", 2),
                     (5, "paragraph", "Fast O(1) access using indexes", 2))
    assert _out(as_slides(blocks, _doc(5))) == [
        (5, "heading", "Array Implementation", ["Array Implementation"]),
        (5, "paragraph", "Programs:", ["Array Implementation"]),
        (5, "paragraph", "Array Rotation using Recursion", ["Array Implementation"]),
        (5, "paragraph", "Advantages:", ["Array Implementation"]),
        (5, "paragraph", "Fast O(1) access using indexes", ["Array Implementation"])]


def test_the_title_is_no_label_and_goes_first():
    """DSA slide 1: "Name:" stands above the deck's title; slide 9: the title is smaller than its labels."""
    blocks = _blocks((1, "heading", "Name:", 1), (1, "heading", "Data Structures and Algorithms Project", 1),
                     (1, "list_item", "- Farooq Ahmed (008)", 1),
                     (9, "heading", "Approach Used:", 1), (9, "heading", "Cracking the Code", 2),
                     (9, "list_item", "1. Understand the problem", 2))
    assert _out(as_slides(blocks, _doc(9))) == [
        (1, "heading", "Data Structures and Algorithms Project", ["Data Structures and Algorithms Project"]),
        (1, "paragraph", "Name:", ["Data Structures and Algorithms Project"]),
        (1, "list_item", "- Farooq Ahmed (008)", ["Data Structures and Algorithms Project"]),
        (9, "heading", "Cracking the Code", ["Cracking the Code"]),
        (9, "paragraph", "Approach Used:", ["Cracking the Code"]),
        (9, "list_item", "1. Understand the problem", ["Cracking the Code"])]


def test_a_slide_with_the_title_before_goes_on_with_it_and_one_without_a_title_too():
    """Pointers slides 8 to 12: "Accessing the Variable Pointed To" five times. Linear Transformation: slides with
    only a picture go on under the title before them."""
    blocks = _blocks((8, "heading", "Accessing the Variable", 1), (8, "list_item", "- Suppose that ...", 1),
                     (9, "heading", "Accessing the Variable", 1), (9, "code", "int main()", 1),
                     (10, "figure", "[Figure]", 1),
                     (11, "heading", "Pointer to void", 1), (11, "list_item", "- The address ...", 1))
    out = as_slides(blocks, _doc(11))
    assert _out(out) == [
        (8, "heading", "Accessing the Variable", ["Accessing the Variable"]),
        (8, "list_item", "- Suppose that ...", ["Accessing the Variable"]),
        (9, "code", "int main()", ["Accessing the Variable"]),
        (10, "figure", "[Figure]", ["Accessing the Variable"]),
        (11, "heading", "Pointer to void", ["Pointer to void"]),
        (11, "list_item", "- The address ...", ["Pointer to void"])]
    assert [b.seq for b in out] == list(range(6))


def test_a_slide_titled_like_the_file_is_under_the_file_s_title_only():
    """Pointers.pptx.pdf: slides 1 and 2 are titled "Pointers", the file's title. No "Pointers > Pointers", and no
    section of its own: Linear Transformation's slide 1 (a picture before the title slide) stays with the rest."""
    blocks = [Block(seq=0, kind="figure", text="[Figure]", heading_path=["Pointers"], loc=Location(page=1),
                    figure_id="fig0"),
              *_blocks((2, "heading", "Pointers", 1), (2, "list_item", "- Pointers are an important feature", 1),
                       (3, "heading", "Pointer Variables", 1), (3, "list_item", "- A variable that holds", 1))]
    blocks = [b.model_copy(update={"seq": n, "heading_path": ["Pointers", *b.heading_path[1:]]})
              for n, b in enumerate(blocks)]
    assert _out(as_slides(blocks, _doc(3))) == [
        (1, "figure", "[Figure]", []), (2, "list_item", "- Pointers are an important feature", []),
        (3, "heading", "Pointer Variables", ["Pointer Variables"]),
        (3, "list_item", "- A variable that holds", ["Pointer Variables"])]


def test_slides_before_the_first_title_stay_under_the_file_s_title():
    blocks = _blocks((1, "figure", "[Figure]", 0), (2, "heading", "Linear Transformation", 1))
    assert _out(as_slides(blocks, _doc(2))) == [(1, "figure", "[Figure]", []),
                                                (2, "heading", "Linear Transformation", ["Linear Transformation"])]


@pytest.mark.parametrize("width, height, slides", [(960, 540, True), (720, 405, True), (612, 792, False),
                                                   (595, 842, False)])
def test_a_pdf_is_slides_when_every_page_is_wider_than_tall(width, height, slides):
    assert is_slides(_doc(3, width, height)) is slides


def test_a_book_s_blocks_are_left_alone():
    blocks = _blocks((5, "heading", "Inheritance", 1), (5, "heading", "Advantages:", 2), (5, "paragraph", "x", 2))
    assert as_slides(blocks, _doc(5, 612, 792)) == blocks


def test_a_bullet_docling_left_in_a_list_item_s_text_is_dropped():
    """Pointers deck: "- ·Pointers are an important feature of C++"."""
    doc = _doc(1)
    group = doc.add_list_group()
    doc.add_list_item("·Pointers are an important feature of C++.", parent=group)
    doc.add_list_item("• Accessing array elements.", parent=group)
    assert [b.text for b in to_blocks(doc, "pdf", T)] == ["- Pointers are an important feature of C++.",
                                                         "- Accessing array elements."]


def test_the_pdf_loader_makes_one_section_of_a_slide(tmp_path, monkeypatch, data_dir):
    path = write_pdf(tmp_path / "deck.pdf", ["BT /F1 28 Tf 50 480 Td (Array Implementation) Tj ET\n"
                                             "BT /F1 18 Tf 50 420 Td (Advantages:) Tj ET\n"
                                             "BT /F1 14 Tf 50 380 Td (Fast access using indexes) Tj ET"],
                     mediabox=(0, 0, 960, 540))
    doc = _doc(1)
    for text, top in (("Array Implementation", 510), ("Advantages:", 440)):
        doc.add_heading(text, level=1, prov=ProvenanceItem(page_no=1, bbox=_box(50, top - 30, 600, top),
                                                          charspan=(0, len(text))))
    doc.add_text(DocItemLabel.TEXT, "Fast access using indexes", prov=ProvenanceItem(
        page_no=1, bbox=_box(50, 375, 600, 395), charspan=(0, 25)))
    monkeypatch.setattr(pdf, "convert", lambda *args, **kwargs: Conversion(doc))
    parsed = ingest_file(path, "r1", "c1")
    assert [(b.kind, b.text) for b in parsed.blocks] == [("heading", "Array Implementation"),
                                                         ("paragraph", "Advantages:"),
                                                         ("paragraph", "Fast access using indexes")]
    assert "slides" in parsed.quality.seconds_taken
    assert "line_breaks" in parsed.quality.seconds_taken


def test_code_on_two_slides_under_one_title_stays_two_listings(tmp_path, monkeypatch, data_dir):
    """Pointers slides 37 and 38, "Sorting Array Elements": order() on one, main() on the next. A book's page break
    can cut a listing in two; a slide break does not, slides are made to hold their code."""
    pages = [f"BT /F1 28 Tf 50 480 Td (Sorting) Tj ET\nBT /F2 12 Tf 50 400 Td ({code}) Tj ET"
             for code in ("void order();", "int main();")]
    path = write_pdf(tmp_path / "deck.pdf", pages, fonts=("Helvetica", "Courier"), mediabox=(0, 0, 960, 540))
    doc = _doc(2)
    for page, code in ((1, "void order();"), (2, "int main();")):
        doc.add_heading("Sorting", level=1, prov=ProvenanceItem(page_no=page, bbox=_box(50, 475, 300, 510),
                                                               charspan=(0, 7)))
        doc.add_code(code, prov=ProvenanceItem(page_no=page, bbox=_box(50, 395, 300, 412), charspan=(0, len(code))))
    monkeypatch.setattr(pdf, "convert", lambda *args, **kwargs: Conversion(doc))
    parsed = ingest_file(path, "r1", "c1")
    assert [(b.kind, b.text, b.loc.page) for b in parsed.blocks] == [
        ("heading", "Sorting", 1), ("code", "void order();", 1), ("code", "int main();", 2)]


# ======================================================================== a slide's lines

def _escaped(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _slide(tmp_path, lines: list[str], docling_text: str, width: float = 960, height: float = 540):
    """A one-page PDF with `lines` at the left, 17 points apart, and Docling's paragraph for them: one item, its text
    `docling_text`, its box around all the lines."""
    content = "\n".join(f"BT /F1 14 Tf 50 {400 - 17 * n} Td ({_escaped(line)}) Tj ET" for n, line in enumerate(lines))
    path = write_pdf(tmp_path / "deck.pdf", [content], mediabox=(0, 0, width, height))
    doc = _doc(1, width, height)
    bottom = 400 - 17 * (len(lines) - 1) - 4
    doc.add_text(DocItemLabel.TEXT, docling_text, prov=ProvenanceItem(page_no=1, bbox=_box(48, bottom, 700, 416),
                                                                      charspan=(0, len(docling_text))))
    return path, doc


def _lines_of(tmp_path, lines: list[str], docling_text: str | None = None, **page) -> Block:
    path, doc = _slide(tmp_path, lines, docling_text or " ".join(lines), **page)
    blocks = keep_line_breaks(to_blocks(doc, "pdf", T), doc, path)
    assert len(blocks) == 1
    return blocks[0]


def test_a_slide_paragraph_gets_its_lines_back_and_a_word_moved_down_goes_on(tmp_path):
    """DSA slide 3: Docling read three points as one sentence. "system" starts with a small letter and did not fit
    at the end of the line above: PowerPoint moved it down, it is no point of its own."""
    block = _lines_of(tmp_path, ["Implementation of 20 DSA problems", "Individual testing and dry runs",
                                               "Integration into a single menu-driven", "system"])
    assert block.text == ("Implementation of 20 DSA problems\nIndividual testing and dry runs\n"
                          "Integration into a single menu-driven system")
    assert block.extra["line_breaks"] == 2


def test_a_small_letter_that_would_have_fitted_above_starts_a_line_of_its_own(tmp_path):
    """"k" would have fitted after "Input: 10 20" (the line above is far shorter than the widest): a new line."""
    block = _lines_of(tmp_path, ["Output: 30 40 50 60 70 10 20", "Input: 10 20", "k = 5"])
    assert block.text == "Output: 30 40 50 60 70 10 20\nInput: 10 20\nk = 5"


def test_docling_s_dash_without_its_space_still_matches_the_pdf_s_dash(tmp_path):
    """DSA slide 10: the PDF has "Insertion – O(log n)", Docling "Insertion -O(log n)". Docling's words stay."""
    block = _lines_of(tmp_path, ["Insertion \u2013 O(log n)", "Deletion \u2013 O(log n)"],
                      "Insertion -O(log n) Deletion -O(log n)")
    assert block.text == "Insertion -O(log n)\nDeletion -O(log n)"


def test_a_line_of_another_item_inside_the_box_is_left_out(tmp_path):
    """DSA slide 7: Docling made an item of the third line, inside the box of the three points around it."""
    block = _lines_of(tmp_path, ["Sort Stack using Recursion", "Bracket Balance Checker",
                                 "Min Stack \u2013 O(1) minimum retrieval", "Stack using Queues"],
                      "Sort Stack using Recursion Bracket Balance Checker Stack using Queues")
    assert block.text == "Sort Stack using Recursion\nBracket Balance Checker\nStack using Queues"


def test_a_paragraph_whose_letters_the_pdf_does_not_have_stays_as_it_is(tmp_path):
    block = _lines_of(tmp_path, ["Easy traversal", "Cache-friendly memory layout"], "Easy traversal Something else")
    assert block.text == "Easy traversal Something else" and "line_breaks" not in block.extra


def test_a_book_s_paragraphs_keep_their_sentences(tmp_path):
    """Pages taller than wide: lines of a book's paragraph are one sentence that goes on."""
    block = _lines_of(tmp_path, ["Pointers are an important feature", "Of C++"], width=612, height=792)
    assert block.text == "Pointers are an important feature Of C++"
