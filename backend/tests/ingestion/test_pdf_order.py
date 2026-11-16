"""order_by_position(): what stands higher on a page comes first, as long as it is in the same column."""
from docling_core.types.doc import (BoundingBox, CoordOrigin, DocItemLabel, DoclingDocument, ProvenanceItem,
                                    Size)

from app.ingestion.converter import Conversion
from app.ingestion.dispatcher import ingest_file
from app.ingestion.docling_blocks import to_blocks
from app.ingestion.loaders import pdf
from app.ingestion.pdf_order import heading_paths, order_by_position


def _prov(top: float, bottom: float, left: float = 96, right: float = 470, page: int = 1) -> ProvenanceItem:
    """A box as show_page prints it: points from the page's top-left corner."""
    box = BoundingBox(l=left, t=top, r=right, b=bottom, coord_origin=CoordOrigin.TOPLEFT)
    return ProvenanceItem(page_no=page, bbox=box, charspan=(0, 0))


def _book(*items: tuple) -> DoclingDocument:
    """Docling's result for two pages of the OOP book's size: items (label, text, prov) in Docling's order."""
    doc = DoclingDocument(name="book")
    doc.add_page(page_no=1, size=Size(width=531, height=656))
    doc.add_page(page_no=2, size=Size(width=531, height=656))
    exercises = doc.add_list_group()
    for label, text, prov in items:
        if label == DocItemLabel.LIST_ITEM:
            doc.add_list_item(text, parent=exercises, prov=prov)
        elif label == DocItemLabel.CODE:
            doc.add_code(text, prov=prov)
        else:
            doc.add_text(label, text, prov=prov)
    return doc


def _ordered(doc: DoclingDocument) -> list[str]:
    blocks = order_by_position(to_blocks(doc, "pdf", "Book"), doc)
    assert [b.seq for b in blocks] == list(range(len(blocks)))
    return [b.text for b in blocks]


def test_a_sample_output_docling_put_after_the_next_exercise_comes_back_to_its_own(tmp_path):
    """Book page 184: Docling kept the exercises together, and exercise 1's interaction came after exercise 2."""
    doc = _book((DocItemLabel.LIST_ITEM, "1. Display both numbers. The interchange might look like this:",
                 _prov(196, 270)),
                (DocItemLabel.LIST_ITEM, "2. A point on the two-dimensional plane...", _prov(313, 374)),
                (DocItemLabel.CODE, "My number is (212) 767-8900", _prov(276, 305, left=115, right=385)),
                (DocItemLabel.TEXT, "Interaction with the program might look like this:", _prov(381, 429, left=115)))
    assert _ordered(doc) == ["- 1. Display both numbers. The interchange might look like this:",
                             "My number is (212) 767-8900", "- 2. A point on the two-dimensional plane...",
                             "Interaction with the program might look like this:"]


def test_a_page_already_in_order_stays_as_it_is():
    doc = _book((DocItemLabel.TEXT, "First.", _prov(83, 100)), (DocItemLabel.CODE, "int a;", _prov(110, 120)),
                (DocItemLabel.TEXT, "Last.", _prov(130, 150)))
    blocks = to_blocks(doc, "pdf", "Book")
    assert order_by_position(blocks, doc) == blocks


def test_blocks_side_by_side_keep_docling_s_order():
    """Two columns, or two halves of one line: top to bottom would mix them."""
    doc = _book((DocItemLabel.TEXT, "Left column, lower down.", _prov(300, 320, left=55, right=250)),
                (DocItemLabel.TEXT, "Right column, higher up.", _prov(83, 100, left=280, right=470)))
    assert _ordered(doc) == ["Left column, lower down.", "Right column, higher up."]


def test_blocks_on_different_pages_never_change_places():
    doc = _book((DocItemLabel.TEXT, "End of page 1.", _prov(500, 520)),
                (DocItemLabel.TEXT, "Top of page 2.", _prov(83, 100, page=2)))
    assert _ordered(doc) == ["End of page 1.", "Top of page 2."]


def test_overlapping_blocks_keep_docling_s_order():
    """A block that only partly stands above another is no proof of a wrong order."""
    doc = _book((DocItemLabel.TEXT, "Second.", _prov(100, 140)), (DocItemLabel.TEXT, "First?", _prov(90, 120)))
    assert _ordered(doc) == ["Second.", "First?"]


def test_the_words_of_a_figure_move_together_with_the_figure(tmp_path):
    """Book page 210: the figure stands at the top of the page, but Docling put it last. Its labels, one by one,
    would stop at the narrow code line and end up between the paragraphs."""
    doc = _book((DocItemLabel.CAPTION, "FIGURE 5.7 Passing by reference.", _prov(300, 320, left=55, right=200)),
                (DocItemLabel.CODE, "float& intp", _prov(350, 358, left=55, right=110)),
                (DocItemLabel.TEXT, "means intp is a reference.", _prov(370, 390, left=55)))
    figure = doc.add_picture(prov=_prov(60, 290, left=100, right=470))
    doc.add_text(DocItemLabel.TEXT, "main()", parent=figure, prov=_prov(150, 160, left=170, right=200))
    doc.add_text(DocItemLabel.TEXT, "intfrac()", parent=figure, prov=_prov(150, 160, left=400, right=440))
    assert _ordered(doc) == ["main()", "intfrac()", "FIGURE 5.7 Passing by reference.", "float& intp",
                             "means intp is a reference."]


def test_a_narrow_line_at_the_left_edge_does_not_stop_a_centred_figure(tmp_path):
    """Book page 210 again: the figure stands at the top, centred; "float& intp" at the left edge does not overlap it
    sideways, but the paragraph between them spans the page: one column. The figure's words came out between
    "so float& intp" and "means intp is a reference"."""
    doc = _book((DocItemLabel.CAPTION, "FIGURE 5.7 Passing by reference.", _prov(300, 320, left=91, right=230)),
                (DocItemLabel.TEXT, "The & can be taken to mean reference to, so", _prov(330, 350, left=91)),
                (DocItemLabel.CODE, "float& intp", _prov(360, 368, left=91, right=144)),
                (DocItemLabel.TEXT, "means intp is a reference.", _prov(380, 400, left=91)))
    figure = doc.add_picture(prov=_prov(60, 290, left=148, right=428))
    doc.add_text(DocItemLabel.TEXT, "main()", parent=figure, prov=_prov(150, 160, left=189, right=214))
    assert _ordered(doc) == ["main()", "FIGURE 5.7 Passing by reference.",
                             "The & can be taken to mean reference to, so", "float& intp", "means intp is a reference."]


def _page(*items: tuple, pages: int = 1) -> DoclingDocument:
    """Docling's result for pages of letter size: items (label, text, prov, heading level) in Docling's order."""
    doc = DoclingDocument(name="lab")
    for page in range(1, pages + 1):
        doc.add_page(page_no=page, size=Size(width=612, height=792))
    for label, text, prov, *level in items:
        if label == DocItemLabel.SECTION_HEADER:
            doc.add_heading(text, level=level[0], prov=prov)
        elif label == DocItemLabel.CODE:
            doc.add_code(text, prov=prov)
        else:
            doc.add_text(label, text, prov=prov)
    return doc


def _paths(blocks) -> list[tuple[str, list[str]]]:
    return [(b.text, b.heading_path[1:]) for b in blocks]


def test_a_page_title_over_narrow_labels_goes_first_and_heads_the_tasks_docling_put_before_it():
    """WA0027 page 1, measured from the PDF: "Lab Task 4" is centred at the top, "Name:" and "Task 1:" at the left
    edge, and Docling put the title after Task 3. Moving up, the title stopped at "Task 1:" (they do not overlap
    sideways), and Tasks 1 to 3 were not under it; Tasks 4 to 14 on the next pages were."""
    code = {"left": 72, "right": 540}
    doc = _page((DocItemLabel.TEXT, "Name: Farooq Ahmed", _prov(112, 126, left=73, right=216)),
                (DocItemLabel.TEXT, "Roll no: BS CMAI 008", _prov(143, 154, left=73, right=210)),
                (DocItemLabel.SECTION_HEADER, "Task 1:", _prov(173, 183, left=72, right=111), 2),
                (DocItemLabel.CODE, "import numpy as np", _prov(196, 258, **code)),
                (DocItemLabel.SECTION_HEADER, "Task 2:", _prov(297, 307, left=72, right=111), 2),
                (DocItemLabel.CODE, "A = np.array([[1, -2 , 4]])", _prov(320, 625, **code)),
                (DocItemLabel.SECTION_HEADER, "Task 3:", _prov(649, 659, left=72, right=111), 2),
                (DocItemLabel.CODE, "np.ones((4,4))", _prov(672, 706, **code)),
                (DocItemLabel.SECTION_HEADER, "Lab Task 4", _prov(77, 91, left=265, right=348), 1),
                (DocItemLabel.SECTION_HEADER, "Task 4:", _prov(72, 82, left=72, right=111, page=2), 2),
                (DocItemLabel.CODE, "np.random.rand(3,3)", _prov(95, 120, page=2, **code)), pages=2)
    before = to_blocks(doc, "pdf", "Lab")
    assert _paths(before)[2] == ("Task 1:", ["Task 1:"])
    blocks = order_by_position(before, doc)
    assert [b.seq for b in blocks] == list(range(len(blocks)))
    assert _paths(blocks) == [("Lab Task 4", ["Lab Task 4"]),
                              ("Name: Farooq Ahmed", ["Lab Task 4"]), ("Roll no: BS CMAI 008", ["Lab Task 4"]),
                              ("Task 1:", ["Lab Task 4", "Task 1:"]), ("import numpy as np", ["Lab Task 4", "Task 1:"]),
                              ("Task 2:", ["Lab Task 4", "Task 2:"]),
                              ("A = np.array([[1, -2 , 4]])", ["Lab Task 4", "Task 2:"]),
                              ("Task 3:", ["Lab Task 4", "Task 3:"]), ("np.ones((4,4))", ["Lab Task 4", "Task 3:"]),
                              ("Task 4:", ["Lab Task 4", "Task 4:"]), ("np.random.rand(3,3)", ["Lab Task 4", "Task 4:"])]


def test_a_heading_with_something_beside_it_higher_up_is_no_page_title():
    """Two columns: the right column's heading starts lower than the left column's text, so it stays where it is."""
    doc = _page((DocItemLabel.TEXT, "Left column, from the top.", _prov(80, 300, left=55, right=250)),
                (DocItemLabel.SECTION_HEADER, "Right column", _prov(100, 115, left=300, right=470), 1),
                (DocItemLabel.TEXT, "Right column text.", _prov(120, 200, left=300, right=470)))
    assert [b.text for b in order_by_position(to_blocks(doc, "pdf", "Lab"), doc)] == [
        "Left column, from the top.", "Right column", "Right column text."]


def test_the_words_of_a_figure_moved_up_past_a_heading_are_in_the_section_above_it():
    """Book page 842: Docling put the UML diagram's words after "Listing the Nouns" and its list; the order step
    brought them back under their caption, but they kept the heading path of "Listing the Nouns"."""
    doc = _page((DocItemLabel.SECTION_HEADER, "UML Activity Diagrams", _prov(40, 55), 2),
                (DocItemLabel.CAPTION, "FIGURE 16.8 UML activity diagram.", _prov(60, 75)),
                (DocItemLabel.SECTION_HEADER, "Listing the Nouns", _prov(300, 315), 2),
                (DocItemLabel.TEXT, "Here's the list of nouns.", _prov(320, 350)))
    figure = doc.add_picture(prov=_prov(80, 290, left=150, right=400))
    for text, top in (("Display", 100), ("Add Tenant", 120)):
        doc.add_text(DocItemLabel.TEXT, text, parent=figure, prov=_prov(top, top + 10, left=200, right=260))
    blocks = order_by_position(to_blocks(doc, "pdf", "Book"), doc)
    assert _paths(blocks) == [("UML Activity Diagrams", ["UML Activity Diagrams"]),
                              ("FIGURE 16.8 UML activity diagram.", ["UML Activity Diagrams"]),
                              ("Display", ["UML Activity Diagrams"]), ("Add Tenant", ["UML Activity Diagrams"]),
                              ("Listing the Nouns", ["Listing the Nouns"]),
                              ("Here's the list of nouns.", ["Listing the Nouns"])]


def test_heading_paths_built_again_in_docling_s_order_are_the_ones_to_blocks_gave():
    """Levels with gaps (a level-3 heading right under a level-1 one, a level-2 one before any level 1) and a title
    above every level: built again in the same order, every path is what to_blocks() gave."""
    doc = _page((DocItemLabel.SECTION_HEADER, "Task 1:", _prov(40, 50), 2),
                (DocItemLabel.TEXT, "Before the title.", _prov(55, 65)),
                (DocItemLabel.TITLE, "Lab Manual", _prov(70, 80)),
                (DocItemLabel.SECTION_HEADER, "Chapter 1", _prov(90, 100), 1),
                (DocItemLabel.SECTION_HEADER, "Deep", _prov(110, 120), 3),
                (DocItemLabel.TEXT, "Under deep.", _prov(125, 135)),
                (DocItemLabel.SECTION_HEADER, "Middle", _prov(140, 150), 2),
                (DocItemLabel.TEXT, "Under middle.", _prov(155, 165)))
    blocks = to_blocks(doc, "pdf", "Book")
    assert heading_paths(blocks, doc) == blocks
    assert _paths(blocks)[-1] == ("Under middle.", ["Lab Manual", "Chapter 1", "Middle"])


def test_heading_paths_stay_when_a_heading_s_docling_item_is_unknown():
    doc = _page((DocItemLabel.SECTION_HEADER, "Task 1:", _prov(40, 50), 2), (DocItemLabel.TEXT, "x", _prov(55, 65)))
    blocks = to_blocks(doc, "pdf", "Book")
    lost = [blocks[0].model_copy(update={"extra": {}, "heading_path": ["Book", "Other"]}), blocks[1]]
    assert heading_paths(lost, doc) == lost


def test_the_pdf_loader_puts_blocks_in_page_order(chapter_tab_pdf, monkeypatch, data_dir):
    def docling(path, source_type, file_sha256=None):
        return Conversion(_book((DocItemLabel.TEXT, "Below.", _prov(300, 320)),
                                (DocItemLabel.TEXT, "Above.", _prov(83, 100))))

    monkeypatch.setattr(pdf, "convert", docling)
    doc = ingest_file(chapter_tab_pdf, "r1", "c1")
    assert [b.text for b in doc.blocks] == ["Above.", "Below."]
    assert "order" in doc.quality.seconds_taken
