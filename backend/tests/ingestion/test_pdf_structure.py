"""A book's structure: heading levels from heading sizes, chapter names from bookmarks, bullet points Docling took for
headings, and code listings that a page break cut in two."""
from docling_core.types.doc import BoundingBox, CoordOrigin, DocItemLabel, DoclingDocument, ProvenanceItem, Size

from app.ingestion.contract import Block, Location
from app.ingestion.converter import Conversion
from app.ingestion.dispatcher import ingest_file
from app.ingestion.docling_blocks import to_blocks
from app.ingestion.loaders import pdf
from app.ingestion.pdf_structure import join_page_listings, list_headings, name_chapters, set_heading_levels
from conftest import write_pdf


def _prov(size: float, y: float, text: str, page: int = 1) -> ProvenanceItem:
    """Docling's box around one line of `size`-point text at baseline `y`, measured from the page's bottom."""
    box = BoundingBox(l=70, r=72 + 0.7 * size * len(text), t=y + size, b=y - 0.3 * size,
                      coord_origin=CoordOrigin.BOTTOMLEFT)
    return ProvenanceItem(page_no=page, bbox=box, charspan=(0, len(text)))


def _paths(doc: DoclingDocument) -> list[tuple[str, list[str]]]:
    return [(b.text, b.heading_path[1:]) for b in to_blocks(doc, "pdf", "Book") if b.kind != "heading"]


# ======================================================================== heading levels from heading sizes

# (point size, baseline, text): a chapter page like the OOP book's, headings in Helvetica-Bold.
# Three section headings and four subsection headings make those two sizes common; the rest are rare.
HEADINGS = [(26, 800, "Inheritance"),                # far bigger than any common size: a chapter
            (17, 760, "IN THIS CHAPTER"),            # a little bigger than the sections: still one of them
            (16, 720, "Derived Class"), (13, 680, "Protected Members"), (13, 640, "Access"),
            (16, 600, "Constructors"), (13, 560, "Arguments"), (10, 520, "Output of COUNTEN"),
            (16, 480, "Overriding"), (13, 440, "Calls")]


def _sized_pdf(tmp_path):
    lines = "\n".join(f"BT /F1 {size} Tf 72 {y} Td ({text}) Tj ET" for size, y, text in HEADINGS)
    return write_pdf(tmp_path / "sizes.pdf", [lines], fonts=("Helvetica-Bold",))


def _sized_doc() -> DoclingDocument:
    """Docling's result: every heading at the same level, a short paragraph under each."""
    doc = DoclingDocument(name="book")
    doc.add_page(page_no=1, size=Size(width=595, height=842))
    for size, y, text in HEADINGS:
        doc.add_heading(text, level=1, prov=_prov(size, y, text))
        doc.add_text(DocItemLabel.TEXT, f"About {text}.", prov=_prov(10, y - 20, f"About {text}."))
    return doc


def test_each_heading_sits_under_the_bigger_headings_before_it(tmp_path):
    doc = _sized_doc()
    assert set_heading_levels(doc, _sized_pdf(tmp_path)) == len(HEADINGS)
    assert [h.level for h in doc.texts if h.label == DocItemLabel.SECTION_HEADER] == [1, 2, 2, 3, 3, 2, 3, 4, 2, 3]
    paths = dict(_paths(doc))
    assert paths["About Inheritance."] == ["Inheritance"]
    assert paths["About IN THIS CHAPTER."] == ["Inheritance", "IN THIS CHAPTER"]
    assert paths["About Derived Class."] == ["Inheritance", "Derived Class"]          # not under IN THIS CHAPTER
    assert paths["About Access."] == ["Inheritance", "Derived Class", "Access"]
    assert paths["About Output of COUNTEN."] == ["Inheritance", "Constructors", "Arguments", "Output of COUNTEN"]
    assert paths["About Calls."] == ["Inheritance", "Overriding", "Calls"]


def test_a_heading_whose_words_are_not_in_the_pdf_gets_the_lowest_level(tmp_path):
    """Not measured, it must not end a section early: below every common size, it only names its own lines."""
    doc = _sized_doc()
    doc.add_heading("Not in the PDF", level=1, prov=_prov(16, 300, "Not in the PDF"))
    doc.add_text(DocItemLabel.TEXT, "After it.", prov=_prov(10, 280, "After it."))
    set_heading_levels(doc, _sized_pdf(tmp_path))
    assert doc.texts[-2].level == 4                       # two common sizes: below both
    assert dict(_paths(doc))["After it."] == ["Inheritance", "Overriding", "Calls", "Not in the PDF"]


def test_nothing_changes_when_no_heading_can_be_measured(tmp_path):
    doc = DoclingDocument(name="book")
    doc.add_page(page_no=1, size=Size(width=595, height=842))
    doc.add_heading("Somewhere Else", level=1, prov=_prov(16, 300, "Somewhere Else"))
    assert set_heading_levels(doc, _sized_pdf(tmp_path)) == 0
    assert doc.texts[0].level == 1


# ======================================================================== chapter names from the bookmarks

def _bookmarked_pdf(tmp_path):
    return write_pdf(tmp_path / "chapters.pdf", ["", "", "", ""],
                     bookmarks=[("Contents", 0), ("9 Inheritance", 1), ("4 Structures", 2), ("A ASCII Chart", 3)])


def _chapter_doc() -> DoclingDocument:
    """Page 2: a chapter's first page as in the OOP book (title, the IN THIS CHAPTER list, the printed label and
    number, then the chapter's own text). Page 3: a title Docling read as a paragraph. Page 4: a title it missed."""
    doc = DoclingDocument(name="book")
    for page in range(1, 5):
        doc.add_page(page_no=page, size=Size(width=595, height=842))
    doc.add_heading("Inheritance", level=1, prov=_prov(26, 780, "Inheritance", 2))
    doc.add_heading("IN THIS CHAPTER", level=2, prov=_prov(17, 740, "IN THIS CHAPTER", 2))
    group = doc.add_list_group()
    doc.add_list_item("Derived Class and Base Class 373", parent=group, prov=_prov(10, 720, "Derived", 2))
    doc.add_text(DocItemLabel.TEXT, "CHAPTER", prov=_prov(13, 600, "CHAPTER", 2))
    doc.add_text(DocItemLabel.TEXT, "9", prov=_prov(40, 560, "9", 2))
    doc.add_text(DocItemLabel.TEXT, "Inheritance is probably the most powerful feature.", prov=_prov(10, 500, "x", 2))
    doc.add_text(DocItemLabel.TEXT, "Structures", prov=_prov(26, 780, "Structures", 3))
    doc.add_text(DocItemLabel.TEXT, "A structure is a collection of variables.", prov=_prov(10, 700, "x", 3))
    doc.add_text(DocItemLabel.TEXT, "ASCII Chart APPENDIX", prov=_prov(26, 780, "x", 4))
    doc.add_text(DocItemLabel.TEXT, "A", prov=_prov(40, 740, "A", 4))
    doc.add_text(DocItemLabel.TEXT, "Table A.1 shows the IBM character codes.", prov=_prov(10, 700, "x", 4))
    return doc


def test_chapters_are_named_after_the_pdf_s_bookmarks(tmp_path):
    doc = _chapter_doc()
    assert name_chapters(doc, _bookmarked_pdf(tmp_path)) == 3
    blocks = to_blocks(doc, "pdf", "Book")
    assert [(b.text, b.heading_path[1:]) for b in blocks] == [
        ("Chapter 9: Inheritance", ["Chapter 9: Inheritance"]),
        ("IN THIS CHAPTER", ["Chapter 9: Inheritance", "IN THIS CHAPTER"]),
        ("- Derived Class and Base Class 373", ["Chapter 9: Inheritance", "IN THIS CHAPTER"]),
        # the printed label starts the chapter's own text again: it is not part of the IN THIS CHAPTER list,
        # and the big "9" under it is left out
        ("Chapter 9: Inheritance", ["Chapter 9: Inheritance"]),
        ("Inheritance is probably the most powerful feature.", ["Chapter 9: Inheritance"]),
        # Docling read this title as a paragraph: it becomes the heading
        ("Chapter 4: Structures", ["Chapter 4: Structures"]),
        ("A structure is a collection of variables.", ["Chapter 4: Structures"]),
        # Docling missed this title: a heading goes before the page's first item
        ("Appendix A: ASCII Chart", ["Appendix A: ASCII Chart"]),
        ("ASCII Chart APPENDIX", ["Appendix A: ASCII Chart"]),
        ("Table A.1 shows the IBM character codes.", ["Appendix A: ASCII Chart"]),
    ]
    assert all(b.loc.page == 4 for b in blocks[-3:])


def test_a_heading_with_a_chapter_s_words_on_another_page_keeps_its_name(tmp_path):
    doc = DoclingDocument(name="book")
    for page in range(1, 5):
        doc.add_page(page_no=page, size=Size(width=595, height=842))
    doc.add_heading("Inheritance", level=2, prov=_prov(16, 700, "Inheritance", 1))     # bookmark points to page 2
    doc.add_text(DocItemLabel.TEXT, "Inheritance makes new classes from old ones.", prov=_prov(10, 600, "x", 2))
    name_chapters(doc, _bookmarked_pdf(tmp_path))
    assert [(b.kind, b.text) for b in to_blocks(doc, "pdf", "Book")][:3] == [
        ("heading", "Inheritance"), ("heading", "Chapter 9: Inheritance"),
        ("paragraph", "Inheritance makes new classes from old ones.")]


def test_a_pdf_without_bookmarks_names_no_chapter(tmp_path):
    doc = _chapter_doc()
    assert name_chapters(doc, write_pdf(tmp_path / "plain.pdf", ["", "", "", ""])) == 0
    assert doc.texts[0].text == "Inheritance"


# ======================================================================== bullet points Docling took for headings

def test_a_heading_that_starts_with_a_bullet_becomes_a_list_item():
    """Book page 43: "· Physical objects" and six more were headings, each the section name of the next."""
    doc = DoclingDocument(name="book")
    doc.add_page(page_no=1, size=Size(width=595, height=842))
    doc.add_heading("Real-World Modeling", level=2, prov=_prov(13, 700, "x"))
    doc.add_heading("· Physical objects", level=2, prov=_prov(10, 680, "x"))
    doc.add_heading("• Human entities", level=2, prov=_prov(10, 660, "x"))
    doc.add_text(DocItemLabel.TEXT, "Objects match real things.", prov=_prov(10, 640, "x"))
    assert list_headings(doc) == 2
    assert [(b.kind, b.text, b.heading_path[1:], b.loc.page) for b in to_blocks(doc, "pdf", "Book")] == [
        ("heading", "Real-World Modeling", ["Real-World Modeling"], 1),
        ("list_item", "- Physical objects", ["Real-World Modeling"], 1),
        ("list_item", "- Human entities", ["Real-World Modeling"], 1),
        ("paragraph", "Objects match real things.", ["Real-World Modeling"], 1)]


# ======================================================================== listings cut by a page break

def _block(seq: int, kind: str, text: str, page: int, path: str = "Arrays") -> Block:
    return Block(seq=seq, kind=kind, text=text, heading_path=["Book", path], loc=Location(page=page),
                 extra={"ref": f"#/texts/{seq}"})


def test_a_listing_cut_by_page_breaks_becomes_one_block():
    blocks = [_block(0, "paragraph", "Here's the listing:", 5),
              _block(1, "code", "// sales.cpp\nint main()\n   {", 5),
              _block(2, "code", "   float sales[SIZE];", 6),
              _block(3, "code", "   return 0;\n   }", 7),
              _block(4, "paragraph", "The output:", 7)]
    joined = join_page_listings(blocks)
    assert [(b.seq, b.kind) for b in joined] == [(0, "paragraph"), (1, "code"), (2, "paragraph")]
    assert joined[1].text == "// sales.cpp\nint main()\n   {\n   float sales[SIZE];\n   return 0;\n   }"
    assert (joined[1].loc.page, joined[1].loc.page_end) == (5, 7)
    assert joined[1].extra == {"ref": "#/texts/1", "joined": ["#/texts/2", "#/texts/3"]}


def test_listings_are_not_joined_across_a_new_file_a_new_section_or_a_skipped_page():
    blocks = [_block(0, "code", "int a;", 5),
              _block(1, "code", "//fileA.cpp\nint gloVar;", 6),           # a new file: book page 670
              _block(2, "code", "int b;", 7, path="Strings"),               # a new section
              _block(3, "code", "int c;", 9, path="Strings"),               # not the next page
              _block(4, "code", "int d;", 9, path="Strings")]               # the same page: two listings
    assert join_page_listings(blocks) == blocks


# ======================================================================== the loader

def test_the_pdf_loader_builds_the_book_s_structure(tmp_path, monkeypatch, data_dir):
    path = write_pdf(tmp_path / "book.pdf", ["BT /F1 26 Tf 72 780 Td (Inheritance) Tj ET\n"
                                             "BT /F1 10 Tf 72 700 Td (A derived class adds to its base.) Tj ET"],
                     fonts=("Helvetica-Bold",), bookmarks=[("9 Inheritance", 0)])
    doc = DoclingDocument(name="book")
    doc.add_page(page_no=1, size=Size(width=595, height=842))
    doc.add_heading("Inheritance", level=1, prov=_prov(26, 780, "Inheritance"))
    doc.add_text(DocItemLabel.TEXT, "A derived class adds to its base.", prov=_prov(10, 700, "x"))
    monkeypatch.setattr(pdf, "convert", lambda *args, **kwargs: Conversion(doc))
    parsed = ingest_file(path, "r1", "c1")
    assert parsed.blocks[-1].heading_path == [parsed.title, "Chapter 9: Inheritance"]
    assert {"list_headings", "heading_levels", "chapters", "page_listings"} <= set(parsed.quality.seconds_taken)
