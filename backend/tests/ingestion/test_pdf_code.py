"""restore_code_lines(): a code listing that Docling squashed onto one line gets its lines and indentation back."""
import pytest
from docling_core.types.doc import BoundingBox, CoordOrigin, DocItemLabel, DoclingDocument, ProvenanceItem

from app.ingestion.converter import Conversion
from app.ingestion.dispatcher import ingest_file
from app.ingestion.docling_blocks import to_blocks
from app.ingestion.loaders import pdf
from app.ingestion.pdf_code import _ascii, restore_code_lines

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


def test_a_font_s_drawing_pieces_are_dropped():
    """The OOP book draws a long arrow as "←" and three pieces of the Symbol font (U+F8E7), invisible junk."""
    assert _ascii("c1=0 ←\uf8e7\uf8e7\uf8e7 counts") == "c1=0 ← counts"


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


def test_a_list_item_becomes_code_only_when_it_is_all_code(listing_pdf):
    """Book page 307: the program's output "1: 22" came out as list items. An exercise with code below its
    sentence stays a list item: what belongs to it is for the order rules to sort out."""
    n = len(LISTING)
    path, _ = listing_pdf(LISTING + ["1: 22", ("sentence", "1. Write a program like this:"), "int a = 1;"])
    doc = _book_with_listing((DocItemLabel.LIST_ITEM, "1: 22", n, n),
                             (DocItemLabel.LIST_ITEM, "1. Write a program like this: int a = 1;", n + 1, n + 2))
    kinds = [kind for kind, _ in _after_listing(doc, path)]
    assert kinds == ["code", "list_item"]


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
