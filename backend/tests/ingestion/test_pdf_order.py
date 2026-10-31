"""order_by_position(): what stands higher on a page comes first, as long as it is in the same column."""
from docling_core.types.doc import (BoundingBox, CoordOrigin, DocItemLabel, DoclingDocument, ProvenanceItem,
                                    Size)

from app.ingestion.converter import Conversion
from app.ingestion.dispatcher import ingest_file
from app.ingestion.docling_blocks import to_blocks
from app.ingestion.loaders import pdf
from app.ingestion.pdf_order import order_by_position


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


def test_the_pdf_loader_puts_blocks_in_page_order(chapter_tab_pdf, monkeypatch, data_dir):
    def docling(path, source_type, file_sha256=None):
        return Conversion(_book((DocItemLabel.TEXT, "Below.", _prov(300, 320)),
                                (DocItemLabel.TEXT, "Above.", _prov(83, 100))))

    monkeypatch.setattr(pdf, "convert", docling)
    doc = ingest_file(chapter_tab_pdf, "r1", "c1")
    assert [b.text for b in doc.blocks] == ["Above.", "Below."]
    assert "order" in doc.quality.seconds_taken
