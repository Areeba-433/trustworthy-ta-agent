"""restore_code_lines(): a code listing that Docling squashed onto one line gets its lines and indentation back."""
import pytest
from docling_core.types.doc import BoundingBox, CoordOrigin, DocItemLabel, DoclingDocument, ProvenanceItem

from app.ingestion.converter import Conversion
from app.ingestion.dispatcher import ingest_file
from app.ingestion.docling_blocks import to_blocks
from app.ingestion.loaders import pdf
from app.ingestion.pdf_code import _ascii, _Char, _words, restore_code_lines

LISTING = [
    "struct Node {",
    "    int value;",
    "    Node* next;",
    "};",
    "",
    "void print(Node* p) {",
    "    while (p) {",
    '        std::cout << p->value << " ";',
    "        p = p->next;",
    "    }",
    "}",
]


def squashed(lines: list[str]) -> str:
    """What Docling makes of a listing: every line stripped, all joined with single spaces."""
    return " ".join(line.strip() for line in lines if line.strip())


def book(text: str, box: BoundingBox, page_no: int = 1) -> DoclingDocument:
    """A Docling result with one code item, like the one Docling made from the test page."""
    doc = DoclingDocument(name="book")
    doc.add_code(text, prov=ProvenanceItem(page_no=page_no, bbox=box, charspan=(0, len(text))))
    return doc


def rebuilt(doc: DoclingDocument, path) -> str:
    [block] = restore_code_lines(to_blocks(doc, "pdf", "Book"), doc, path)
    return block.text


@pytest.mark.parametrize("by_position", [False, True], ids=["spaces", "by-position"])
def test_lines_indentation_and_empty_lines_come_back(listing_pdf, by_position):
    path, box = listing_pdf(LISTING, by_position=by_position)
    assert rebuilt(book(squashed(LISTING), box), path) == "\n".join(LISTING)


def test_rebuilt_blocks_are_marked(listing_pdf):
    path, box = listing_pdf(LISTING)
    doc = book(squashed(LISTING), box)
    [block] = restore_code_lines(to_blocks(doc, "pdf", "Book"), doc, path)
    assert block.extra["lines_from"] == "pdf_text"
    assert block.extra["ref"] == doc.texts[0].self_ref          # Docling's id stays


def test_a_box_measured_from_the_top_gives_the_same_listing(listing_pdf):
    path, box = listing_pdf(LISTING)
    from_top = BoundingBox(l=box.l, r=box.r, t=842 - box.t, b=842 - box.b, coord_origin=CoordOrigin.TOPLEFT)
    assert rebuilt(book(squashed(LISTING), from_top), path) == "\n".join(LISTING)


def test_curly_quotes_become_straight_as_docling_makes_them(listing_pdf):
    path, box = listing_pdf(["if (ok) {", "    printf(\u201chi\u201d);", "}"])     # a book typeset with curly quotes
    assert rebuilt(book('if (ok) { printf("hi"); }', box), path) == 'if (ok) {\n    printf("hi");\n}'


@pytest.mark.parametrize("measured_from", ["page corner", "pdf origin"])
def test_a_page_that_does_not_start_at_zero(listing_pdf, measured_from):
    """Like our OOP book, whose pages start at (54, 55). Docling's default reader measures boxes from that corner,
    its pypdfium2 reader from the PDF's origin: both must land on the listing."""
    path, box = listing_pdf(LISTING, corner=(54, 55))
    if measured_from == "pdf origin":
        box = BoundingBox(l=box.l + 54, r=box.r + 54, t=box.t + 55, b=box.b + 55, coord_origin=CoordOrigin.BOTTOMLEFT)
    assert rebuilt(book(squashed(LISTING), box), path) == "\n".join(LISTING)


def test_a_sentence_inside_the_box_that_docling_did_not_put_in_the_listing_is_left_out(listing_pdf):
    path, box = listing_pdf(LISTING)
    too_tall = box.model_copy(update={"t": box.t + 40})          # reaches "MULTSHAP draws three shapes:"
    assert rebuilt(book(squashed(LISTING), too_tall), path) == "\n".join(LISTING)


def test_the_end_of_a_line_that_docling_gave_to_another_item_is_left_out(listing_pdf):
    """In the OOP book Docling gave the end of a long line, after a wide gap, to the next code item."""
    lines = ['cout << "char      -128 to 127" << endl', '     << "long      -2,147,483,648" << endl;', "return 0;"]
    path, box = listing_pdf(lines)
    docling_has = [lines[0], '     << "long', lines[2]]
    assert rebuilt(book(squashed(docling_has), box), path) == "\n".join(docling_has)


def test_a_line_is_never_cut_where_the_pdf_has_no_gap(listing_pdf):
    """Docling's words "a = b" are inside "a = b + c;", but taking them would cut that line: keep Docling's text."""
    path, box = listing_pdf(["a = b + c;", "d = e;"])
    assert rebuilt(book("a = b d = e;", box), path) == "a = b d = e;"


def test_pieces_are_chosen_so_that_all_of_doclings_words_fit(listing_pdf):
    """Docling's words are "f(); g(); h(); m();". Lines 1, 2, 3 fit for a while, but then "m();" alone is nowhere:
    the fix must see that early and take line 1 and line 4. Lines 2 and 3 belong to another item."""
    path, box = listing_pdf(["f();", "g();", "h();", "g(); h(); m();"])
    lines = rebuilt(book("f(); g(); h(); m();", box), path).split("\n")
    assert [line for line in lines if line] == ["f();", "g(); h(); m();"]


def test_a_box_that_misses_part_of_docling_s_own_listing_is_completed_from_the_page(listing_pdf):
    """When Docling merges two overlapping regions it keeps one region's box (book page 431): the box covers only
    the second half of the listing, but Docling's words are all of it."""
    path, box = listing_pdf(LISTING)
    lower_half = box.model_copy(update={"t": box.t - 6 * 11.5})
    assert rebuilt(book(squashed(LISTING), lower_half), path) == "\n".join(LISTING)


def test_on_the_whole_page_the_lines_closest_to_the_box_are_taken(listing_pdf):
    """ "x = 1; y = 2;" is on the page twice; the box only covers "z = 3;". The copy next to it is the right one."""
    path, box = listing_pdf(["x = 1;", "y = 2;", "", "", "", "", "x = 1;", "y = 2;", "z = 3;"])
    last_line = box.model_copy(update={"t": box.b + 9})
    lines = rebuilt(book("x = 1; y = 2; z = 3;", last_line), path)
    assert lines == "x = 1;\ny = 2;\nz = 3;"


def test_a_sentence_that_docling_put_in_the_listing_becomes_a_paragraph_in_its_place(listing_pdf):
    """Book page 431: Docling's code item also holds the sentence above the listing, set in Times-Roman. It comes
    out as a paragraph of its own, before the code, and its wide capitals stay whole ("M ULTSHAP" in the book)."""
    path, box = listing_pdf(LISTING)
    doc = book("MULTSHAP draws three shapes: " + squashed(LISTING), box.model_copy(update={"t": box.t + 40}))
    blocks = restore_code_lines(to_blocks(doc, "pdf", "Book"), doc, path)
    assert [(b.seq, b.kind, b.text) for b in blocks] == [
        (0, "paragraph", "MULTSHAP draws three shapes:"), (1, "code", "\n".join(LISTING))]
    assert blocks[0].extra["split_from"] == "code" and blocks[1].extra["lines_from"] == "pdf_text"
    assert {b.extra["ref"] for b in blocks} == {doc.texts[0].self_ref}      # both come from Docling's one item
    assert blocks[0].loc == blocks[1].loc


def test_sentences_between_two_pieces_of_code_leave_the_listing(listing_pdf):
    """Book page 184: question 18 came out as one code block, "18. State the reason that enum isWord{ NO, YES };
    is better than enum isWord{ YES, NO };". The sentences are in the book's text font."""
    lines = LISTING + [("sentence", "18. State the reason that"), "enum isWord{ NO, YES };",
                       ("sentence", "is better than"), "enum isWord{ YES, NO };"]
    path, box = listing_pdf(lines)       # the code above gives the code font enough letters to be recognised
    words = "18. State the reason that enum isWord{ NO, YES }; is better than enum isWord{ YES, NO };"
    doc = book(squashed(LISTING) + " " + words, box)
    blocks = restore_code_lines(to_blocks(doc, "pdf", "Book"), doc, path)
    assert [(b.kind, b.text) for b in blocks] == [
        ("code", "\n".join(LISTING)), ("paragraph", "18. State the reason that"), ("code", "enum isWord{ NO, YES };"),
        ("paragraph", "is better than"), ("code", "enum isWord{ YES, NO };")]


def test_a_note_beside_program_output_stays_with_it_and_keeps_its_gap(listing_pdf):
    """Book page 348: the output "c1=0" with the author's note beside it, in the text font. The line starts in the
    code font, so it stays code, and the note stays in its column."""
    lines = ['cout << "c1=" << c1.get_count();', "return 0;  // the counters are shown", "",
             ("note", "c1=0", "counts are initially 0"), "c2=0", ("note", "c1=1", "incremented once")]
    path, box = listing_pdf(lines)
    words = 'cout << "c1=" << c1.get_count(); return 0; // the counters are shown c1=0 counts are initially 0 c2=0 ' \
            'c1=1 incremented once'
    text = rebuilt(book(words, box), path)
    assert text.split("\n")[3:] == ["c1=0        counts are initially 0", "c2=0", "c1=1        incremented once"]


def test_a_long_dash_in_the_pdf_matches_docling_s_plain_one(listing_pdf):
    """Book page 168: the PDF has "variable—dining—of", Docling "variable-dining-of". With the long dash the
    words did not match, and Docling's one-line text was kept. (The dash is in the code font here: on Windows the
    test PDF's Times-Roman long dash came out apart from its letters; the real book's dashes do not.)"""
    lines = LISTING + ["int n;   // a variable—dining—of type Room"]
    path, box = listing_pdf(lines)
    doc = book(squashed(LISTING) + " int n; // a variable-dining-of type Room", box)
    assert rebuilt(doc, path) == "\n".join(LISTING + ["int n;   // a variable-dining-of type Room"])


def test_a_paragraph_whose_box_reaches_the_chapter_tab_still_gets_its_code_lines(listing_pdf):
    """Docling's box of an item can reach the chapter tab on the page's edge (book pages 537 and 543). The tab's
    letters are no item's words: remove_chapter_tabs() takes them off Docling's text, and here they are left out
    of the PDF's, so the words still match."""
    n = len(LISTING)
    path, _ = listing_pdf(LISTING + [("sentence", "Here's the loop:"), "for(j=0; j<3; j++)", "   cout << j;"],
                          tab=True)
    doc = _book_with_listing((DocItemLabel.TEXT, "Here's the loop: for(j=0; j<3; j++) cout << j;", n, n + 2))
    doc.texts[-1].prov[0].bbox.r = 575                   # the box reaches the tab
    assert _after_listing(doc, path) == [("paragraph", "Here's the loop:"),
                                         ("code", "for(j=0; j<3; j++)\n   cout << j;")]


def test_a_word_broken_at_the_end_of_a_line_in_a_listing_is_joined_as_docling_joined_it(listing_pdf):
    """Book page 532: "type-" at the end of a line and "compatible" on the next; Docling has "typecompatible"."""
    n = len(LISTING)
    lines = LISTING + ["int a;", ("sentence", "pointers are type-"), ("sentence", "compatible with them.")]
    path, _ = listing_pdf(lines)
    for docling in ("typecompatible", "type-compatible"):
        doc = _book_with_listing((DocItemLabel.CODE, f"int a; pointers are {docling} with them.", n, n + 2))
        assert _after_listing(doc, path) == [("code", "int a;"), ("paragraph", f"pointers are {docling} with them.")]


def test_a_font_s_drawing_pieces_are_dropped():
    """The OOP book draws a long arrow as "←" and three pieces of the Symbol font (U+F8E7), invisible junk."""
    assert _ascii("c1=0 ←\uf8e7\uf8e7\uf8e7 counts") == "c1=0 ← counts"


def test_the_pdf_s_own_space_separates_words_even_where_a_letter_reaches_into_it():
    """pdfium 156 (pypdfium2 5.14) measures the Times "f" wider than pdfium 153: its box reaches into the space of
    "of type", the gap left was too small to count, and "oftype" matched none of Docling's words."""
    of = [_Char("o", 179.20, 184.20, 600, 10, False), _Char("f", 184.20, 188.55, 600, 10, False)]
    type_ = [_Char("t", 190.03, 192.82, 600, 10, False, spaced=True), _Char("y", 192.81, 197.81, 600, 10, False)]
    assert _words(of + type_, width=5.0) == ["of", "ty"]


def test_a_listing_with_no_line_in_a_fixed_width_font_is_never_split(listing_pdf):
    """Some books print code in an ordinary font: then no line can be told from a sentence, and nothing is split."""
    lines = [("sentence", "x = 1;"), ("sentence", "y = 2;")]
    path, box = listing_pdf(lines)
    doc = book("x = 1; y = 2;", box)
    assert [b.kind for b in restore_code_lines(to_blocks(doc, "pdf", "Book"), doc, path)] == ["code"]


def test_a_code_font_with_too_few_letters_to_be_recognised_splits_nothing(listing_pdf):
    """Here the code has only four letters: too few to tell its font is fixed-width. Without that, a line in an
    ordinary font is no proof of a sentence, and the listing stays whole."""
    lines = ["a = b;", ("sentence", "is the same as"), "b = a;"]
    path, box = listing_pdf(lines)
    doc = book("a = b; is the same as b = a;", box)
    assert [b.kind for b in restore_code_lines(to_blocks(doc, "pdf", "Book"), doc, path)] == ["code"]


def test_a_big_gap_becomes_at_most_two_empty_lines(listing_pdf):
    path, box = listing_pdf(["int a;", "", "", "", "", "int b;"])
    assert rebuilt(book("int a; int b;", box), path) == "int a;\n\n\nint b;"


def test_docling_text_stays_when_its_words_differ(listing_pdf):
    path, box = listing_pdf(LISTING)
    assert rebuilt(book("struct Leaf { int value; };", box), path) == "struct Leaf { int value; };"


def test_docling_text_stays_when_the_page_is_not_in_the_file(listing_pdf):
    path, box = listing_pdf(LISTING)
    assert rebuilt(book(squashed(LISTING), box, page_no=5), path) == squashed(LISTING)


def test_without_code_the_pdf_is_not_even_opened(tmp_path):
    doc = DoclingDocument(name="book")
    doc.add_text(DocItemLabel.TEXT, "A paragraph.",
                 prov=ProvenanceItem(page_no=1, bbox=BoundingBox(l=0, t=0, r=1, b=1), charspan=(0, 12)))
    blocks = to_blocks(doc, "pdf", "Book")
    assert restore_code_lines(blocks, doc, tmp_path / "no-such-file.pdf") == blocks


def test_the_pdf_loader_rebuilds_listings(listing_pdf, monkeypatch, data_dir):
    path, box = listing_pdf(LISTING)
    monkeypatch.setattr(pdf, "convert", lambda *args, **kwargs: Conversion(book(squashed(LISTING), box)))
    doc = ingest_file(path, "r1", "c1")
    [code] = [b for b in doc.blocks if b.kind == "code"]
    assert code.text == "\n".join(LISTING)
    assert "code_lines" in doc.quality.seconds_taken


# ======================================================== code-font lines inside Docling's paragraphs and formulas

def _lines_box(first: int, last: int, columns: int = 60) -> BoundingBox:
    """Docling's box around lines first..last of a listing_pdf page (11.5 points apart, the first at 700)."""
    return BoundingBox(l=71, r=73 + columns * 5.4, t=700 - first * 11.5 + 8, b=700 - last * 11.5 - 3,
                       coord_origin=CoordOrigin.BOTTOMLEFT)


def _book_with_listing(*items: tuple) -> DoclingDocument:
    """Docling's result for a page that starts with LISTING, a code item as usual, and then `items`: (label,
    text, first line, last line). A formula's words go to orig, as Docling leaves them."""
    doc = book(squashed(LISTING), _lines_box(0, len(LISTING) - 1))
    for label, text, first, last in items:
        prov = ProvenanceItem(page_no=1, bbox=_lines_box(first, last), charspan=(0, len(text)))
        if label == DocItemLabel.LIST_ITEM:
            doc.add_list_item(text, prov=prov, parent=doc.add_list_group())
        elif label == DocItemLabel.CODE:
            doc.add_code(text, prov=prov)
        else:
            doc.add_text(label, "" if label == DocItemLabel.FORMULA else text, orig=text, prov=prov)
    return doc


def _after_listing(doc: DoclingDocument, path) -> list[tuple[str, str]]:
    blocks = restore_code_lines(to_blocks(doc, "pdf", "Book"), doc, path)
    assert [b.seq for b in blocks] == list(range(len(blocks)))
    return [(b.kind, b.text) for b in blocks[1:]]


def test_a_listing_inside_a_paragraph_comes_out_as_code_between_its_sentences(listing_pdf):
    """Book page 164: the PARTINIT listing, the sentences around it and its output came out as one paragraph."""
    n = len(LISTING)
    lines = LISTING + [("sentence", "Here's the loop:"), "for(j=0; j<3; j++)", "   cout << j;",
                       ("sentence", "It prints three numbers.")]
    path, _ = listing_pdf(lines)
    doc = _book_with_listing((DocItemLabel.TEXT, "Here's the loop: for(j=0; j<3; j++) cout << j; It prints three "
                                                 "numbers.", n, n + 3))
    assert _after_listing(doc, path) == [("paragraph", "Here's the loop:"),
                                         ("code", "for(j=0; j<3; j++)\n   cout << j;"),
                                         ("paragraph", "It prints three numbers.")]


def test_a_paragraph_all_in_the_code_font_is_code(listing_pdf):
    """Book page 177: "enum pets { cat, dog, hamster, canary, ocelot };" came out as a paragraph."""
    path, _ = listing_pdf(LISTING + ["enum pets { cat, dog };"])
    doc = _book_with_listing((DocItemLabel.TEXT, "enum pets { cat, dog };", len(LISTING), len(LISTING)))
    assert _after_listing(doc, path) == [("code", "enum pets { cat, dog };")]


def test_a_formula_in_the_code_font_is_code(listing_pdf):
    """Book page 177: Docling took "day1 = 5;" for a formula; step 7 brought its words back, as a formula."""
    path, _ = listing_pdf(LISTING + ["day1 = 5;"])
    doc = _book_with_listing((DocItemLabel.FORMULA, "day1 = 5;", len(LISTING), len(LISTING)))
    blocks = restore_code_lines(to_blocks(doc, "pdf", "Book"), doc, path)
    assert (blocks[-1].kind, blocks[-1].text, blocks[-1].lang) == ("code", "day1 = 5;", "code")
    assert blocks[-1].extra["split_from"] == "formula"


def test_a_list_item_s_code_lines_become_code_and_its_sentence_stays_a_list_item(listing_pdf):
    """Book page 307: the program's output "1: 22" came out as a list item: all code, so code. Book page 97: an
    exercise with a line of code below its sentence: the code gets its lines, the exercise stays a list item."""
    n = len(LISTING)
    path, _ = listing_pdf(LISTING + ["1: 22", ("sentence", "1. Write a program like this:"), "int a = 1;"])
    doc = _book_with_listing((DocItemLabel.LIST_ITEM, "1: 22", n, n),
                             (DocItemLabel.LIST_ITEM, "1. Write a program like this: int a = 1;", n + 1, n + 2))
    assert _after_listing(doc, path) == [("code", "1: 22"), ("list_item", "- 1. Write a program like this:"),
                                         ("code", "int a = 1;")]


def _book_with_numbered_item(label: DocItemLabel, text: str, first: int, last: int) -> DoclingDocument:
    """LISTING, then a numbered list item as Docling makes it: its number is the marker, not part of its text."""
    doc = book(squashed(LISTING), _lines_box(0, len(LISTING) - 1))
    prov = ProvenanceItem(page_no=1, bbox=_lines_box(first, last), charspan=(0, len(text)))
    if label == DocItemLabel.LIST_ITEM:
        doc.add_list_item(text, enumerated=True, marker="1.", prov=prov, parent=doc.add_list_group())
    else:
        doc.add_text(label, "1. " + text, prov=prov)
    return doc


@pytest.mark.parametrize("label", [DocItemLabel.LIST_ITEM, DocItemLabel.TEXT], ids=["list-item", "paragraph"])
def test_a_numbered_list_read_as_one_item_becomes_one_item_per_number(listing_pdf, label):
    """Book page 950: the answers to chapter 5's questions came out as one list item, code and all."""
    n = len(LISTING)
    lines = LISTING + [("sentence", "1. d (half credit for b)"), ("sentence", "2. definition"), ("sentence", "3."),
                       "void foo()", "   { }", ("sentence", "4. declaration, prototype")]
    path, _ = listing_pdf(lines)
    doc = _book_with_numbered_item(label, "d (half credit for b) 2. definition 3. void foo() { } 4. declaration, "
                                          "prototype", n, n + 5)
    assert _after_listing(doc, path) == [("list_item", "1. d (half credit for b)"), ("list_item", "2. definition"),
                                         ("list_item", "3."), ("code", "void foo()\n   { }"),
                                         ("list_item", "4. declaration, prototype")]


def test_a_numbered_list_without_code_is_cut_into_items_too(listing_pdf):
    """Book page 964: "15. d 16. false if there is a conversion routine 17. b ..." as one paragraph."""
    n = len(LISTING)
    path, _ = listing_pdf(LISTING + [("sentence", "15. d"), ("sentence", "16. false if there is a routine"),
                                     ("sentence", "17. b")])
    doc = _book_with_listing((DocItemLabel.TEXT, "15. d 16. false if there is a routine 17. b", n, n + 2))
    assert _after_listing(doc, path) == [("list_item", "15. d"), ("list_item", "16. false if there is a routine"),
                                         ("list_item", "17. b")]


def test_a_paragraph_whose_lines_do_not_count_on_stays_whole(listing_pdf):
    """Only the next number starts an item: "3." after "1." is part of the sentence, as is "2.0"."""
    n = len(LISTING)
    path, _ = listing_pdf(LISTING + [("sentence", "1. The first rule, and"), ("sentence", "3. not the next one.")])
    doc = _book_with_listing((DocItemLabel.TEXT, "1. The first rule, and 3. not the next one.", n, n + 1))
    assert _after_listing(doc, path) == [("paragraph", "1. The first rule, and 3. not the next one.")]


def test_a_sentence_with_a_little_code_in_it_stays_a_paragraph(listing_pdf):
    """Words of code inside a sentence ("x is true whenever x is not 0") do not make its line code."""
    path, _ = listing_pdf(LISTING + [("note", "x", "is true whenever x is not 0")])
    doc = _book_with_listing((DocItemLabel.TEXT, "x is true whenever x is not 0", len(LISTING), len(LISTING)))
    assert _after_listing(doc, path) == [("paragraph", "x is true whenever x is not 0")]


def test_a_paragraph_whose_words_are_not_all_in_its_box_is_left_alone(listing_pdf):
    path, _ = listing_pdf(LISTING + ["day1 = 5;"])
    doc = _book_with_listing((DocItemLabel.TEXT, "If you say day1 = 5;", len(LISTING), len(LISTING)))
    assert _after_listing(doc, path) == [("paragraph", "If you say day1 = 5;")]


def test_a_word_broken_at_the_end_of_a_line_is_one_of_docling_s_words(listing_pdf):
    """pdfium marks the break of "struc-ture" with U+FFFE; Docling joins the halves."""
    n = len(LISTING)
    path, _ = listing_pdf(LISTING + [("sentence", "the name of the inner struc-"), ("sentence", "ture is"), "Distance"])
    doc = _book_with_listing((DocItemLabel.TEXT, "the name of the inner structure is Distance", n, n + 2))
    assert _after_listing(doc, path) == [("paragraph", "the name of the inner structure is"), ("code", "Distance")]


def test_a_listing_of_only_sentences_is_a_paragraph_in_a_book_with_a_code_font(listing_pdf):
    """Book page 237: Docling took "17. Here's a function:" for code. The book's listings are in a fixed-width
    font, and this line is not."""
    path, _ = listing_pdf(LISTING + [("sentence", "17. Here's a function:")])
    doc = _book_with_listing((DocItemLabel.CODE, "17. Here's a function:", len(LISTING), len(LISTING)))
    assert _after_listing(doc, path) == [("paragraph", "17. Here's a function:")]


def test_paragraphs_stay_whole_in_a_book_whose_listings_are_not_in_a_fixed_width_font(listing_pdf):
    """Docling's listings here are in an ordinary font, so the fixed-width lines elsewhere prove nothing."""
    n = len(LISTING)
    path, _ = listing_pdf(LISTING + [("sentence", "x = 1;"), ("sentence", "y = 2;")])
    doc = DoclingDocument(name="book")
    doc.add_text(DocItemLabel.TEXT, squashed(LISTING), prov=ProvenanceItem(page_no=1, bbox=_lines_box(0, n - 1),
                                                                            charspan=(0, 0)))
    doc.add_code("x = 1; y = 2;", prov=ProvenanceItem(page_no=1, bbox=_lines_box(n, n + 1), charspan=(0, 0)))
    blocks = restore_code_lines(to_blocks(doc, "pdf", "Book"), doc, path)
    assert [b.kind for b in blocks] == ["paragraph", "code"]


# ================================================================= one region that Docling cut into overlapping items

def _box(first: int, last: int, from_column: int = 0, to_column: int = 60) -> BoundingBox:
    """Like _lines_box, but only columns from_column..to_column of the lines."""
    box = _lines_box(first, last, to_column)
    return box.model_copy(update={"l": 71 + from_column * 5.4})


def _book_with_pieces(*pieces: tuple) -> DoclingDocument:
    """LISTING as its own code item, then `pieces`: (label, text, box) one after the other, as Docling cut them."""
    doc = book(squashed(LISTING), _lines_box(0, len(LISTING) - 1))
    for label, text, box in pieces:
        prov = ProvenanceItem(page_no=1, bbox=box, charspan=(0, len(text)))
        if label == DocItemLabel.CODE:
            doc.add_code(text, prov=prov)
        else:
            doc.add_text(label, text, prov=prov)
    return doc


def test_a_line_cut_into_two_code_items_side_by_side_is_one_line(listing_pdf):
    """Book page 174: "if( chosen == prize )" and its comment "//not legal yet" came out as two code blocks."""
    n = len(LISTING)
    path, _ = listing_pdf(LISTING + ["if( chosen == prize )        //not legal yet"])
    doc = _book_with_pieces((DocItemLabel.CODE, "if( chosen == prize )", _box(n, n, 0, 22)),
                            (DocItemLabel.CODE, "//not legal yet", _box(n, n, 29, 45)))
    assert _after_listing(doc, path) == [("code", "if( chosen == prize )        //not legal yet")]


def test_the_end_of_a_long_line_in_the_next_code_item_goes_back_to_its_line(listing_pdf):
    """Book page 189: the line << "long ... 2,147,483,647" << endl; was cut in two, its end in a second code
    item that also held the rest of the listing."""
    n = len(LISTING)
    lines = LISTING + ['cout << "char  -128 to 127" << endl', '     << "long  -2,147,483,648" << endl;', "return 0;"]
    path, _ = listing_pdf(lines)
    doc = _book_with_pieces((DocItemLabel.CODE, 'cout << "char -128 to 127" << endl << "long', _box(n, n + 1)),
                            (DocItemLabel.CODE, '-2,147,483,648" << endl; return 0;', _box(n + 1, n + 2)))
    assert _after_listing(doc, path) == [("code", "\n".join(lines[n:]))]


def test_a_separator_line_given_to_the_paragraph_below_goes_back_into_the_listing(listing_pdf):
    """Book page 205: Docling gave the listing's //----- line to the paragraph under the listing."""
    n = len(LISTING)
    lines = LISTING + ["int a;", "//--------", "int b;", ("sentence", "In main() the variable is gone.")]
    path, _ = listing_pdf(lines)
    doc = _book_with_pieces((DocItemLabel.CODE, "int a; int b;", _box(n, n + 2)),
                            (DocItemLabel.TEXT, "//-------- In main() the variable is gone.", _box(n + 1, n + 3)))
    assert _after_listing(doc, path) == [("code", "int a;\n//--------\nint b;"),
                                         ("paragraph", "In main() the variable is gone.")]


def test_listings_and_sentences_interleaved_by_docling_come_out_in_page_order(listing_pdf):
    """Book page 216: two overlapping code boxes took every other line, a declaration and the sentence about it."""
    n = len(LISTING)
    lines = LISTING + ["void repchar();", ("sentence", "which takes no arguments, and"), "void repchar(char);",
                       ("sentence", "which takes one.")]
    path, _ = listing_pdf(lines)
    doc = _book_with_pieces((DocItemLabel.CODE, "void repchar(); void repchar(char);", _box(n, n + 2)),
                            (DocItemLabel.CODE, "which takes no arguments, and which takes one.", _box(n + 1, n + 3)))
    assert _after_listing(doc, path) == [("code", "void repchar();"), ("paragraph", "which takes no arguments, and"),
                                         ("code", "void repchar(char);"), ("paragraph", "which takes one.")]


def test_a_line_of_code_cut_into_a_formula_and_a_paragraph_is_one_line(listing_pdf):
    """Book page 174 again: the two halves were not code items at all, but a formula and a paragraph."""
    n = len(LISTING)
    path, _ = listing_pdf(LISTING + ["if( chosen == prize )        //not legal yet"])
    doc = _book_with_pieces((DocItemLabel.FORMULA, "if( chosen == prize )", _box(n, n, 0, 22)),
                            (DocItemLabel.TEXT, "//not legal yet", _box(n, n, 29, 45)))
    assert _after_listing(doc, path) == [("code", "if( chosen == prize )        //not legal yet")]


def test_a_paragraph_whose_box_swallowed_the_one_before_comes_out_in_page_order(listing_pdf):
    """Book page 195: "The next call to repchar()", the call itself, then "tells it to print..." and the output.
    Docling made one paragraph of most of it, with a box that also covered the paragraph it put first."""
    n = len(LISTING)
    lines = LISTING + [("sentence", "The next call to repchar()"), "repchar('=', 23);",
                       ("sentence", "tells it to print a line."), "======"]
    path, _ = listing_pdf(lines)
    doc = _book_with_pieces((DocItemLabel.TEXT, "tells it to print a line.", _box(n + 2, n + 2)),
                            (DocItemLabel.TEXT, "The next call to repchar() repchar('=', 23); ======", _box(n, n + 3)))
    assert _after_listing(doc, path) == [("paragraph", "The next call to repchar()"), ("code", "repchar('=', 23);"),
                                         ("paragraph", "tells it to print a line."), ("code", "======")]


def test_an_item_of_leftover_words_overlapping_the_items_before_it_brings_them_all_into_page_order(listing_pdf):
    """Book page 352: Docling's last item on the region held its leftovers ("//display again return Counter(count);
    COUNTPP3. //constructor, one arg"), with a box over the five items before it. The items one after the other do
    not overlap each other; only through the last one are they one region."""
    n = len(LISTING)
    lines = LISTING + ["int main()", ("sentence", "In this program a single statement"), "return Counter(count);",
                       ("sentence", "does what all three did."), "Counter(int c) : count(c)    //one arg"]
    path, _ = listing_pdf(lines)
    doc = _book_with_pieces((DocItemLabel.CODE, "int main() In this program a single statement", _box(n, n + 1)),
                            (DocItemLabel.TEXT, "does what all three did.", _box(n + 3, n + 3)),
                            (DocItemLabel.CODE, "Counter(int c) : count(c)", _box(n + 4, n + 4, 0, 25)),
                            (DocItemLabel.CODE, "return Counter(count); //one arg", _box(n + 1, n + 4)))
    assert _after_listing(doc, path) == [("code", "int main()"), ("paragraph", "In this program a single statement"),
                                         ("code", "return Counter(count);"),
                                         ("paragraph", "does what all three did."),
                                         ("code", "Counter(int c) : count(c)    //one arg")]


def test_a_comment_cut_off_with_the_chapter_tab_goes_back_to_its_line(listing_pdf):
    """Book pages 537 and 543: Docling put a comment and the chapter tab beside it into an item of their own; the
    tab came off (remove_chapter_tabs), and the comment goes back to its line."""
    n = len(LISTING)
    path, _ = listing_pdf(LISTING + ["arr[0]->show();      //execute show()", "return 0;"], tab=True)
    doc = _book_with_pieces((DocItemLabel.CODE, "//execute show()", _box(n, n, 21, 40).model_copy(update={"r": 575})),
                            (DocItemLabel.CODE, "arr[0]->show(); return 0;", _box(n, n + 1, 0, 16)))
    assert _after_listing(doc, path) == [("code", "arr[0]->show();      //execute show()\nreturn 0;")]


def test_numbered_answers_in_a_region_laid_out_again_are_one_list_item_each(listing_pdf):
    """Book page 944: the answers "17. a, c", "18. '\\r'", "19. preceding" came out as one paragraph, because
    Docling's code item of the answers' code overlapped them."""
    n = len(LISTING)
    lines = LISTING + [("sentence", "16."), "if( age > 21 )", ("sentence", "17. a, c"), ("sentence", "18. preceding"),
                       ("sentence", "19."), "switch(ch)"]
    path, _ = listing_pdf(lines)
    doc = _book_with_pieces((DocItemLabel.TEXT, "16. 17. a, c 18. preceding 19.", _box(n, n + 4)),
                            (DocItemLabel.CODE, "if( age > 21 ) switch(ch)", _box(n + 1, n + 5)))
    assert _after_listing(doc, path) == [("list_item", "16."), ("code", "if( age > 21 )"), ("list_item", "17. a, c"),
                                         ("list_item", "18. preceding"), ("list_item", "19."), ("code", "switch(ch)")]


def test_a_wider_gap_between_lines_of_sentences_starts_a_new_paragraph(listing_pdf):
    n = len(LISTING)
    lines = LISTING + ["int a;", ("sentence", "First paragraph,"), ("sentence", "its second line."), "",
                       ("sentence", "Second paragraph.")]
    path, _ = listing_pdf(lines)
    doc = _book_with_pieces((DocItemLabel.CODE, "int a; Second paragraph.", _box(n, n + 4)),
                            (DocItemLabel.TEXT, "First paragraph, its second line.", _box(n + 1, n + 2)))
    assert _after_listing(doc, path) == [("code", "int a;"), ("paragraph", "First paragraph, its second line."),
                                         ("paragraph", "Second paragraph.")]


def test_overlapping_paragraphs_without_a_line_of_code_are_not_touched(listing_pdf):
    """A word of code in a sentence is not enough: only regions with whole lines of code are laid out again."""
    n = len(LISTING)
    path, _ = listing_pdf(LISTING + [("inline", "First words about", "x"), ("sentence", "Second words here.")])
    doc = _book_with_pieces((DocItemLabel.TEXT, "Second words here.", _box(n + 1, n + 1)),
                            (DocItemLabel.TEXT, "First words about x", _box(n, n + 1)))
    assert _after_listing(doc, path) == [("paragraph", "Second words here."), ("paragraph", "First words about x")]


def test_overlapping_items_whose_words_are_not_all_in_the_region_stay_as_they_are(listing_pdf):
    n = len(LISTING)
    path, _ = listing_pdf(LISTING + ["int a;", "int b;"])
    doc = _book_with_pieces((DocItemLabel.CODE, "int a;", _box(n, n + 1)),
                            (DocItemLabel.CODE, "int c;", _box(n, n + 1)))       # Docling's words: not the PDF's
    assert _after_listing(doc, path) == [("code", "int a;"), ("code", "int c;")]


def test_a_listing_of_sentences_with_a_few_code_words_is_a_paragraph(listing_pdf):
    """Book page 216: "which takes one argument of type char": the sentence holds code words, but it is a sentence."""
    path, _ = listing_pdf(LISTING + [("inline", "which takes one argument of type", "char")])
    doc = _book_with_listing((DocItemLabel.CODE, "which takes one argument of type char", len(LISTING), len(LISTING)))
    assert _after_listing(doc, path) == [("paragraph", "which takes one argument of type char")]


def test_a_sentence_full_of_code_words_is_still_a_sentence(listing_pdf):
    """Book page 700: "tions master_tick() and get_floor_requests() over and over. The wait() function" has more
    letters in the code font than in Times, but it is a sentence: a line of code has no Times words at all."""
    path, _ = listing_pdf(LISTING + [("inline", "calls the ", "get_floor_requests()")])
    doc = _book_with_listing((DocItemLabel.CODE, "calls the get_floor_requests()", len(LISTING), len(LISTING)))
    assert _after_listing(doc, path) == [("paragraph", "calls the get_floor_requests()")]


def test_program_output_with_a_note_after_an_arrow_stays_code(listing_pdf):
    """Book page 256: "someClass() : m1(7), m2(33) <- initializer list". The arrow's font is not known."""
    path, _ = listing_pdf(LISTING + [("note", "m1(7), m2(33), m3(4)", "<- initializer list")])
    doc = _book_with_listing((DocItemLabel.CODE, "m1(7), m2(33), m3(4) <- initializer list", len(LISTING),
                              len(LISTING)))
    assert _after_listing(doc, path)[0][0] == "code"


def test_a_cut_line_is_found_on_a_page_that_does_not_start_at_zero(listing_pdf):
    """Book page 174 itself: the OOP book's pages start at (54, 55). Docling's box, taken as pdfium's, lands on
    an empty part of the page; the box measured from the page's corner is the right one, and it must be tried."""
    n = len(LISTING)
    path, _ = listing_pdf(LISTING + ["if( chosen == prize )        //not legal yet"], corner=(54, 55))
    doc = _book_with_pieces((DocItemLabel.CODE, "if( chosen == prize )", _box(n, n, 0, 22)),
                            (DocItemLabel.CODE, "//not legal yet", _box(n, n, 29, 45)))
    assert _after_listing(doc, path) == [("code", "if( chosen == prize )        //not legal yet")]
