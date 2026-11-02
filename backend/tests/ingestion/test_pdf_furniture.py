"""remove_chapter_tabs(): the chapter tab on a page's edge ("9 INHERITANCE") never becomes course content."""
from collections import Counter

from docling_core.types.doc import (BoundingBox, CoordOrigin, DocItemLabel, DoclingDocument, ProvenanceItem,
                                    TableCell, TableData)

from app.ingestion.converter import Conversion
from app.ingestion.dispatcher import ingest_file
from app.ingestion.docling_blocks import to_blocks
from app.ingestion.loaders import pdf
from app.ingestion.pdf_furniture import chapter_tabs, remove_chapter_tabs, tab_characters


# Where Docling puts an item, in points from the page's top-left corner, as it measures
_COLUMN = BoundingBox(l=72, t=130, r=500, b=150, coord_origin=CoordOrigin.TOPLEFT)     # the page's own text


def _prov(page: int, box: BoundingBox = _COLUMN) -> ProvenanceItem:
    return ProvenanceItem(page_no=page, bbox=box, charspan=(0, 0))


def _on_tab(path) -> ProvenanceItem:
    """An item made of the tab: Docling's box is the tab's own."""
    return _prov(1, chapter_tabs(path)[1].box)


def _to_tab(path) -> ProvenanceItem:
    """An item of the text column that Docling merged with the tab: its box reaches from the column to the tab."""
    tab = chapter_tabs(path)[1].box
    return _prov(1, BoundingBox(l=72, t=tab.t, r=tab.r, b=tab.b, coord_origin=CoordOrigin.TOPLEFT))


def _texts(doc: DoclingDocument) -> list[str]:
    return [b.text for b in to_blocks(doc, "pdf", "OOP book")]


def test_the_tab_is_found_on_its_page_only_with_where_it_stands(chapter_tab_pdf):
    tabs = chapter_tabs(chapter_tab_pdf)
    assert list(tabs) == [1] and tabs[1].letters == Counter("9INHERITANCE")
    box = tabs[1].box                                    # the right edge; the turned title and the "9" above it
    assert 540 < box.l < box.r < 565 and 355 < box.t < 375 and 455 < box.b < 470
    assert tabs[1].page_height == 842


def test_where_the_tab_stands_is_measured_from_the_visible_page(make_chapter_tab_pdf):
    """The OOP book's pages start at (54, 55): Docling measures from there, so the tab's box must too."""
    usual = chapter_tabs(make_chapter_tab_pdf())[1].box
    moved = chapter_tabs(make_chapter_tab_pdf(corner=(54, 55)))[1].box
    assert [round(v, 1) for v in (moved.l, moved.t, moved.r, moved.b)] == \
           [round(v, 1) for v in (usual.l, usual.t, usual.r, usual.b)]


def test_turned_text_inside_the_page_is_not_a_tab(make_chapter_tab_pdf):
    """Like the label "Not allowed" turned on its side inside Figure 9.7: part of the content."""
    assert chapter_tabs(make_chapter_tab_pdf(x=300)) == {}


def test_the_tab_as_a_paragraph_or_a_heading_is_left_out_but_only_on_its_page(chapter_tab_pdf):
    doc = DoclingDocument(name="b")
    doc.add_text(DocItemLabel.TEXT, "Inheritance lets a class reuse another class.", prov=_prov(1))
    doc.add_text(DocItemLabel.TEXT, "9", prov=_on_tab(chapter_tab_pdf))
    doc.add_heading("INHERITANCE", level=1, prov=_on_tab(chapter_tab_pdf))
    doc.add_text(DocItemLabel.TEXT, "9 INHERITANCE", prov=_prov(2))         # page 2 has no tab: real text
    assert remove_chapter_tabs(doc, chapter_tab_pdf) == 2
    assert _texts(doc) == ["Inheritance lets a class reuse another class.", "9 INHERITANCE"]


def test_capitals_made_of_the_tab_s_letters_elsewhere_on_the_page_are_content(chapter_tab_pdf):
    """Book page 71: CHARVARS prints "A" and "B", on a page whose tab is "2 C++ PROGRAMMING BASICS". Both letters
    are in the tab, but they stand in the page's own text, not on the tab."""
    doc = DoclingDocument(name="b")
    doc.add_text(DocItemLabel.TEXT, "The output looks like this:", prov=_prov(1))
    doc.add_text(DocItemLabel.TEXT, "I", prov=_prov(1))
    doc.add_text(DocItemLabel.TEXT, "9 INHERITANCE", prov=_prov(1))         # the tab's words, as a line of the text
    assert remove_chapter_tabs(doc, chapter_tab_pdf) == 0
    assert _texts(doc) == ["The output looks like this:", "I", "9 INHERITANCE"]


def test_text_in_ordinary_letters_is_never_taken_for_the_tab(chapter_tab_pdf):
    doc = DoclingDocument(name="b")
    doc.add_text(DocItemLabel.TEXT, "inheritance", prov=_on_tab(chapter_tab_pdf))   # same letters, small ones
    assert remove_chapter_tabs(doc, chapter_tab_pdf) == 0
    assert _texts(doc) == ["inheritance"]


def test_with_a_tab_in_ordinary_letters_a_real_heading_with_its_words_is_kept(make_chapter_tab_pdf):
    """Only text in capitals is taken for a tab: throwing away a real heading would be worse than keeping a tab."""
    path = make_chapter_tab_pdf("Inheritance")
    doc = DoclingDocument(name="b")
    doc.add_heading("Inheritance", level=1, prov=_on_tab(path))
    assert remove_chapter_tabs(doc, path) == 0


def test_a_code_listing_loses_the_tab_at_its_end_and_nothing_else(chapter_tab_pdf):
    doc = DoclingDocument(name="b")
    doc.add_code("class laborer : public employee { }; 9 INHERITANCE", prov=_to_tab(chapter_tab_pdf))
    doc.add_code("#define TITLE A", prov=_to_tab(chapter_tab_pdf))         # one tab letter is not the tab
    remove_chapter_tabs(doc, chapter_tab_pdf)
    assert _texts(doc) == ["class laborer : public employee { };", "#define TITLE A"]


def test_a_separator_line_loses_the_tab_at_its_end(chapter_tab_pdf):
    """Book page 563: "//////// 11 FUNCTIONS". A line with no letters at all cannot be mixed up with the tab."""
    doc = DoclingDocument(name="b")
    doc.add_code("//////////////// 9 INHERITANCE", prov=_to_tab(chapter_tab_pdf))
    remove_chapter_tabs(doc, chapter_tab_pdf)
    assert _texts(doc) == ["////////////////"]


def test_the_tab_s_characters_are_found_for_the_code_lines(chapter_tab_pdf):
    """restore_code_lines() leaves them out of the page: the turned letters and the chapter's number."""
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(str(chapter_tab_pdf))
    try:
        found = []
        for index in range(len(pdf)):
            page = pdf[index]
            textpage = page.get_textpage()
            found.append("".join(sorted(textpage.get_text_range(i, 1) for i in tab_characters(page, textpage))))
            textpage.close()
            page.close()
    finally:
        pdf.close()
    assert found == ["".join(sorted("9INHERITANCE")), ""]


def test_a_paragraph_that_ends_with_the_tab_loses_it_and_only_it(chapter_tab_pdf):
    """Book page 887: the last keyword of a list, "this", came with the chapter tab glued on. A few capitals at the
    end of a sentence are not the tab, even when they are made of its letters."""
    doc = DoclingDocument(name="b")
    doc.add_text(DocItemLabel.TEXT, "this 9 INHERITANCE", prov=_to_tab(chapter_tab_pdf))
    doc.add_text(DocItemLabel.TEXT, "Each node of a TREE", prov=_to_tab(chapter_tab_pdf))
    assert remove_chapter_tabs(doc, chapter_tab_pdf) == 1
    assert _texts(doc) == ["this", "Each node of a TREE"]


def test_a_paragraph_away_from_the_tab_keeps_the_tab_s_words_at_its_end(chapter_tab_pdf):
    """Only Docling's merging puts the tab at the end of a paragraph, and then the paragraph's box reaches it."""
    doc = DoclingDocument(name="b")
    doc.add_text(DocItemLabel.TEXT, "this 9 INHERITANCE", prov=_prov(1))
    assert remove_chapter_tabs(doc, chapter_tab_pdf) == 0


def test_a_heading_in_capitals_keeps_its_words_like_the_tab_s(chapter_tab_pdf):
    """Some books print headings in capitals. In "MULTIPLE INHERITANCE" the tab's words cannot be told from the
    heading's own, so the heading stays whole."""
    doc = DoclingDocument(name="b")
    doc.add_heading("MULTIPLE INHERITANCE", level=2, prov=_to_tab(chapter_tab_pdf))
    assert remove_chapter_tabs(doc, chapter_tab_pdf) == 0
    assert _texts(doc) == ["MULTIPLE INHERITANCE"]


def _cell(text: str, row: int, col: int, cols: int = 1, header: bool = False) -> TableCell:
    return TableCell(text=text, start_row_offset_idx=row, end_row_offset_idx=row + 1, start_col_offset_idx=col,
                     end_col_offset_idx=col + cols, col_span=cols, column_header=header)


def test_a_table_column_made_of_the_tab_is_removed(chapter_tab_pdf):
    """Book page 923: Docling read the tab beside TABLE F.1 as a fourth column."""
    cells = [_cell("Name", 0, 0, header=True), _cell("Arguments", 0, 1, header=True), _cell("", 0, 2, header=True),
             _cell("Mutating Sequence Operations", 1, 0, cols=3),
             _cell("count", 2, 0), _cell("first, last, value, n", 2, 1), _cell("9", 2, 2),
             _cell("count_if", 3, 0), _cell("first, last, predicate, n", 3, 1), _cell("INHERITANCE", 3, 2)]
    doc = DoclingDocument(name="b")
    doc.add_table(data=TableData(num_rows=4, num_cols=3, table_cells=cells), prov=_to_tab(chapter_tab_pdf))
    assert remove_chapter_tabs(doc, chapter_tab_pdf) == 1
    [table] = _texts(doc)
    assert "INHERITANCE" not in table and "| 9" not in table
    assert table.splitlines()[0].count("|") == 3                           # two columns are left
    assert "Mutating Sequence Operations" in table
    [section] = [c for c in doc.tables[0].data.table_cells if c.text == "Mutating Sequence Operations"]
    assert (section.start_col_offset_idx, section.end_col_offset_idx) == (0, 2)        # across what is left


def test_a_real_last_column_stays(chapter_tab_pdf):
    cells = [_cell("Name", 0, 0, header=True), _cell("Random Access", 0, 1, header=True),
             _cell("sort", 1, 0), _cell("X", 1, 1)]
    doc = DoclingDocument(name="b")
    doc.add_table(data=TableData(num_rows=2, num_cols=2, table_cells=cells), prov=_to_tab(chapter_tab_pdf))
    assert remove_chapter_tabs(doc, chapter_tab_pdf) == 0


def _two_columns(*rows: tuple[str, str], prov: ProvenanceItem, last_header: str = "Arguments") -> DoclingDocument:
    cells = [_cell("Name", 0, 0, header=True), _cell(last_header, 0, 1, header=True)]
    for n, (name, last) in enumerate(rows, start=1):
        cells += [_cell(name, n, 0), _cell(last, n, 1)]
    doc = DoclingDocument(name="b")
    doc.add_table(data=TableData(num_rows=len(rows) + 1, num_cols=2, table_cells=cells), prov=prov)
    return doc


def _column(doc: DoclingDocument, col: int) -> list[str]:
    cells = sorted(doc.tables[0].data.table_cells, key=lambda c: c.start_row_offset_idx)
    return [c.text for c in cells if c.start_col_offset_idx == col and not c.column_header]


def test_the_tab_at_the_end_of_cells_in_the_last_column_is_taken_off(chapter_tab_pdf):
    """Book page 925 in ACCURATE mode: the tab's words went to the end of the Arguments cells, spread over rows
    ("first, n, gen F", "first, last, value STL AND"). The other columns are not the tab's neighbours."""
    doc = _two_columns(("generate_n INHERITANCE", "first, n, gen 9"), ("remove", "first, last, value INHERITANCE"),
                       prov=_to_tab(chapter_tab_pdf))
    assert remove_chapter_tabs(doc, chapter_tab_pdf) == 2
    assert _column(doc, 1) == ["first, n, gen", "first, last, value"]
    assert _column(doc, 0) == ["generate_n INHERITANCE", "remove"]


def test_a_few_capitals_at_the_end_of_a_cell_are_not_the_tab(chapter_tab_pdf):
    """ "TEN" is made of the tab's letters, but a quarter of them is not the tab."""
    doc = _two_columns(("fill_n", "first, last, TEN"), prov=_to_tab(chapter_tab_pdf))
    assert remove_chapter_tabs(doc, chapter_tab_pdf) == 0
    assert _column(doc, 1) == ["first, last, TEN"]


def test_a_cell_made_only_of_capitals_is_never_cut(chapter_tab_pdf):
    """Like the Symbol column of an ASCII table: "C" is data. The column has a header, so it is no tab column."""
    doc = _two_columns(("67", "INHERITANCE"), ("57", "9"), last_header="Symbol", prov=_to_tab(chapter_tab_pdf))
    assert remove_chapter_tabs(doc, chapter_tab_pdf) == 0
    assert _column(doc, 1) == ["INHERITANCE", "9"]


def test_with_a_tab_in_ordinary_letters_the_end_of_a_cell_stays(make_chapter_tab_pdf):
    """As with headings: only words in capitals are taken for the tab."""
    path = make_chapter_tab_pdf("Inheritance")
    doc = _two_columns(("sort", "first, last 9 Inheritance"), prov=_to_tab(path))
    assert remove_chapter_tabs(doc, path) == 0


def test_each_of_the_tab_s_letters_is_taken_from_the_cells_once(chapter_tab_pdf):
    doc = _two_columns(("sort", "first, last 9 INHERITANCE"), ("stable_sort", "first, last INHERITANCE"),
                       prov=_to_tab(chapter_tab_pdf))
    assert remove_chapter_tabs(doc, chapter_tab_pdf) == 1
    assert _column(doc, 1) == ["first, last", "first, last INHERITANCE"]


def test_a_table_away_from_the_tab_keeps_its_cells(chapter_tab_pdf):
    doc = _two_columns(("generate_n", "first, n, gen 9"), ("remove", "first, last, value INHERITANCE"), prov=_prov(1))
    assert remove_chapter_tabs(doc, chapter_tab_pdf) == 0


def test_the_pdf_loader_leaves_the_tab_out(chapter_tab_pdf, monkeypatch, data_dir):
    def docling_with_the_tab(path, source_type, file_sha256=None):
        doc = DoclingDocument(name="chapter")
        doc.add_text(DocItemLabel.TEXT, "Inheritance lets a class reuse another class.", prov=_prov(1))
        doc.add_text(DocItemLabel.TEXT, "9 INHERITANCE", prov=_on_tab(chapter_tab_pdf))
        return Conversion(doc)

    monkeypatch.setattr(pdf, "convert", docling_with_the_tab)
    doc = ingest_file(chapter_tab_pdf, "r1", "c1")
    assert [b.text for b in doc.blocks] == ["Inheritance lets a class reuse another class."]
    assert "chapter_tabs" in doc.quality.seconds_taken
