"""The PowerPoint loader, tested three ways.

Part 1 hands load() small Docling documents built by hand (Docling does not run), so each slide rule is tested on
exactly the case it is about. Part 2 runs real Docling on a deck generated here: contract tests that turn red if a
Docling upgrade changes its output. Part 3 sends broken files through ingest_file(), the way an upload arrives.
Every deck is generated in code with python-pptx: the repo is public, so no real course files.
"""
import copy
import hashlib
import io
import logging
import zipfile
from collections import Counter
from collections.abc import Callable, Iterator
from pathlib import Path
from xml.sax.saxutils import escape

import pytest
from docling_core.types.doc import (BoundingBox, ContentLayer, DocItemLabel, DoclingDocument, GroupItem,
                                    GroupLabel, ImageRef, ProvenanceItem, Size)
from lxml import etree
from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import PP_PLACEHOLDER
from pptx.opc.constants import CONTENT_TYPE as CT
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.opc.package import Part
from pptx.opc.packuri import PackURI
from pptx.oxml.ns import qn
from pptx.presentation import Presentation as Deck
from pptx.slide import Slide
from pptx.util import Inches

from app.core.config import settings
from app.ingestion import messages
from app.ingestion.contract import ParsedDocument, PrecheckResult, ResourceMeta
from app.ingestion.dispatcher import ingest_file
from app.ingestion.documents import FileRefused
from app.ingestion.loaders.pptx import extract, load
from app.ingestion.registry import is_heavy
from app.ingestion.storage import parsed_path

FILE_NAME = "Stacks_final.pptx"       # title_from_filename() turns this into TITLE
TITLE = "Stacks"
FOOTER = "CS-201 Data Structures"     # typed in the footer of most slides, like a real lecture deck
SLIDE_SIZE = Size(width=960, height=540)
EMU_PER_POINT = 12700                 # Docling gives PowerPoint positions in EMU, 12,700 per point
# one different sentence per slide: find_repeated_lines() treats digits as equal ("Point 1" = "Point 2")
POINTS = ["Push adds on top.", "Pop removes the top.", "Peek reads the top.", "Empty checks the size."]


def _meta(file_name: str = FILE_NAME, file_sha256: str = "0" * 64) -> ResourceMeta:
    return ResourceMeta(resource_id="r1", course_id="c1", file_name=file_name, file_sha256=file_sha256,
                        precheck=PrecheckResult(source_type="pptx"))


# ================================================================ part 1: hand-built Docling results

def _prov(slide: int, shown: tuple[int, int] = (1, 1)) -> ProvenanceItem:
    width, height = shown
    return ProvenanceItem(page_no=slide, bbox=BoundingBox(l=0, t=0, r=width, b=height), charspan=(0, 0))


class _Slides:
    """What Docling's PowerPoint reader returns, built by hand: one page and one slide group per slide."""

    def __init__(self, count: int) -> None:
        self.doc = DoclingDocument(name="deck")
        self._groups: list[GroupItem] = []
        for slide in range(1, count + 1):
            self.doc.add_page(page_no=slide, size=SLIDE_SIZE)
            self._groups.append(self.doc.add_group(label=GroupLabel.CHAPTER, name=f"slide-{slide - 1}"))

    def title(self, slide: int, text: str) -> "_Slides":
        self.doc.add_title(text, prov=_prov(slide), parent=self._groups[slide - 1])
        return self

    def text(self, slide: int, text: str) -> "_Slides":
        self.doc.add_text(DocItemLabel.PARAGRAPH, text, prov=_prov(slide), parent=self._groups[slide - 1])
        return self

    def notes(self, slide: int, text: str) -> "_Slides":
        self.doc.add_text(DocItemLabel.TEXT, text, prov=_prov(slide), parent=self._groups[slide - 1],
                          content_layer=ContentLayer.NOTES)
        return self

    def picture(self, slide: int, size: tuple[int, int] | None = None) -> "_Slides":
        """A picture shown `size` points wide and high (360 by 202 if not given), placed in EMU like Docling's."""
        image = ImageRef.from_pil(Image.new("RGB", size, "white"), dpi=72) if size else None
        width, height = size or (360, 202)
        shown = (width * EMU_PER_POINT, height * EMU_PER_POINT)
        self.doc.add_picture(prov=_prov(slide, shown), parent=self._groups[slide - 1], image=image)
        return self


@pytest.fixture
def load_slides(monkeypatch) -> Callable[..., ParsedDocument]:
    """load() on a hand-built Docling result: no file is read, Docling never runs, nothing is cached."""
    from app.ingestion import converter            # imported here: it takes seconds to import
    from app.ingestion.loaders import _pptx_shapes as shapes

    def run(slides: _Slides, problems: tuple[str, ...] = ()) -> ParsedDocument:
        conversion = converter.Conversion(slides.doc, problems)
        monkeypatch.setattr(converter, "convert", lambda path, source_type, file_sha256=None: conversion)
        monkeypatch.setattr(shapes, "read_deck", lambda path: shapes.Deck([]))    # no file for python-pptx
        return load(Path("never-read.pptx"), _meta())

    return run


def _rows(doc: ParsedDocument) -> list[tuple[str, str, int | None]]:
    return [(b.kind, b.text, b.loc.slide) for b in doc.blocks]


def test_a_normal_deck_keeps_reading_order_slide_numbers_and_notes(load_slides):
    doc = load_slides(_Slides(2).title(1, "Push").text(1, "Adds on top.").notes(1, "Draw the stack.")
                      .title(2, "Pop").text(2, "Removes the top."))
    assert _rows(doc) == [
        ("heading", "Push", 1), ("paragraph", "Adds on top.", 1), ("slide_notes", "Draw the stack.", 1),
        ("heading", "Pop", 2), ("paragraph", "Removes the top.", 2),
    ]
    assert (doc.title, doc.quality.status, doc.quality.warnings, doc.quality.units_total) == (TITLE, "ok", [], 2)


def test_an_empty_slide_leaves_a_gap_in_slide_numbers_but_not_in_seq(load_slides):
    doc = load_slides(_Slides(3).text(1, "Before the break.").text(3, "After the break."))
    assert [(b.seq, b.loc.slide) for b in doc.blocks] == [(0, 1), (1, 3)]
    assert doc.quality.units_total == 3                        # the empty slide still counts


@pytest.mark.parametrize("second_slide", [
    pytest.param(lambda s: s.text(2, "Pop removes the top."), id="no title"),
    pytest.param(lambda s: s.title(2, "STACKS").text(2, "Pop removes the top."), id="titled with the deck name"),
    pytest.param(lambda s: s.notes(2, "Pop removes the top."), id="speaker notes only"),
])
def test_a_slide_never_inherits_the_previous_slides_title(load_slides, second_slide):
    slides = _Slides(2).title(1, "Push").text(1, "Push adds on top.")
    doc = load_slides(second_slide(slides))
    assert [(b.loc.slide, b.heading_path) for b in doc.blocks] == [
        (1, [TITLE, "Push"]), (1, [TITLE, "Push"]), (2, [TITLE]),
    ]


@pytest.mark.parametrize(("footer_on", "slides", "dropped"), [
    pytest.param((1, 2, 3), 3, True, id="every slide"),
    pytest.param((1, 2, 3), 4, True, id="3 of 4 slides"),
    pytest.param((1, 2), 4, False, id="exactly half: kept"),
    pytest.param((1, 2), 2, False, id="deck too short to tell"),
])
def test_a_paragraph_on_most_slides_is_a_footer_and_is_dropped(load_slides, footer_on, slides, dropped):
    deck = _Slides(slides)
    for slide in range(1, slides + 1):
        deck.text(slide, POINTS[slide - 1])
        if slide in footer_on:
            deck.text(slide, FOOTER)
    texts = [b.text for b in load_slides(deck).blocks]
    assert (FOOTER in texts) is not dropped
    assert [t for t in texts if t != FOOTER] == POINTS[:slides]


def test_a_footer_with_a_changing_number_is_still_a_footer(load_slides):
    deck = _Slides(3)
    for slide in (1, 2, 3):
        deck.text(slide, POINTS[slide - 1]).text(slide, f"Lecture 4, slide {slide} of 3")
    assert [b.text for b in load_slides(deck).blocks] == POINTS[:3]


@pytest.mark.parametrize(("add", "kind"), [
    pytest.param(lambda s, n: s.title(n, "Recap"), "heading", id="title"),
    pytest.param(lambda s, n: s.notes(n, "Ask for questions."), "slide_notes", id="speaker notes"),
])
def test_titles_and_notes_repeated_on_every_slide_are_not_footers(load_slides, add, kind):
    deck = _Slides(3)
    for slide in (1, 2, 3):
        add(deck, slide)
        deck.text(slide, POINTS[slide - 1])
    doc = load_slides(deck)
    assert [b.loc.slide for b in doc.blocks if b.kind == kind] == [1, 2, 3]


def test_slides_with_a_picture_and_no_text_are_named_for_the_teacher(load_slides):
    doc = load_slides(_Slides(4).text(1, "Text only.").picture(2).picture(4).text(4, "Picture and text."))
    assert doc.quality.status == "degraded"
    assert doc.quality.warnings == [messages.no_text_units("Slides", [2])]   # empty slide 3 is not mentioned


def test_a_picture_slide_whose_only_text_is_the_footer_is_named_too(load_slides):
    deck = _Slides(4).picture(4)
    for slide in (1, 2, 3, 4):
        deck.text(slide, FOOTER)
    for slide in (1, 2, 3):
        deck.text(slide, POINTS[slide - 1])
    assert load_slides(deck).quality.warnings == [messages.no_text_units("Slides", [4])]


def test_a_deck_of_pictures_only_keeps_a_figure_block_per_picture_and_names_every_slide(load_slides):
    doc = load_slides(_Slides(2).picture(1).picture(2))
    assert _rows(doc) == [("figure", "[Figure]", 1), ("figure", "[Figure]", 2)]     # contract 2.1: never lost
    assert (doc.quality.status, doc.quality.warnings) == ("degraded", [messages.no_text_units("Slides", [1, 2])])


def test_a_partial_docling_result_is_degraded_and_its_problem_comes_first(load_slides):
    doc = load_slides(_Slides(2).text(1, "Some text.").picture(2), problems=(messages.PARTIAL,))
    assert doc.quality.status == "degraded"
    assert doc.quality.warnings == [messages.PARTIAL, messages.no_text_units("Slides", [2])]


def test_a_title_with_a_picture_is_named_but_a_title_with_an_icon_is_not(load_slides):
    doc = load_slides(_Slides(3).title(1, "Push").picture(1, size=(640, 360)).title(2, "Pop")
                      .picture(2, size=(32, 32)).text(3, "Peek reads the top."))
    assert doc.quality.warnings == [messages.no_text_units("Slides", [1])]   # a title adds no text to a chunk
    assert [b.loc.slide for b in doc.blocks if b.kind == "figure"] == [1]   # an icon leaves no "[Figure]" block


def test_a_deck_whose_only_text_is_titles_is_refused_with_the_no_text_message(load_slides):
    with pytest.raises(FileRefused) as refused:
        load_slides(_Slides(2).title(1, "Push").picture(1, size=(32, 32)).title(2, "Pop"))
    assert refused.value.reason == messages.NO_TEXT_FILE               # an icon is no content: still no chunk


# ================================================================ part 2: real Docling on a generated deck

LAYOUT = {"title": 0, "content": 1, "title_only": 5, "blank": 6}     # python-pptx's default template
SLIDES_IN_LECTURE = 11

# PowerPoint keeps comments in their own XML parts, linked from the slide. python-pptx has no API for them, so these
# helpers write the parts and link them with relate_to(). Office 365 writes "modern" comments; older PowerPoint
# writes "legacy" ones. Docling 2.134.0 reads legacy comments (into a comment section) and ignores modern ones.
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
P188_NS = "http://schemas.microsoft.com/office/powerpoint/2018/8/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PC_NS = "http://schemas.microsoft.com/office/powerpoint/2013/main/command"
XML_HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
AUTHOR_ID = "{2C5A9C2B-7A3D-4C1E-9F00-000000000001}"
MODERN_COMMENTS = ("application/vnd.ms-powerpoint.comments+xml",
                   "http://schemas.microsoft.com/office/2018/10/relationships/comments")
MODERN_AUTHORS = ("application/vnd.ms-powerpoint.authors+xml",
                  "http://schemas.microsoft.com/office/2018/10/relationships/authors")
MODERN_COMMENT_EXT = "{6950BFC3-D8DA-4A85-94F7-54DA5524770B}"   # the slide's own pointer to its modern comments


def _add_part(deck: Deck, owner: Part, name: str, kind: tuple[str, str], xml: str) -> str:
    """Add an XML part to the file and link it from `owner` (a slide or the presentation). Returns the link id."""
    content_type, relationship = kind
    part = Part(PackURI(name), content_type, deck.part.package, xml.encode())
    return owner.relate_to(part, relationship)


def _legacy_comment(deck: Deck, slide: Slide, text: str) -> None:
    _add_part(deck, deck.part, "/ppt/commentAuthors.xml", (CT.PML_COMMENT_AUTHORS, RT.COMMENT_AUTHORS),
              f'{XML_HEAD}<p:cmAuthorLst xmlns:p="{P_NS}"><p:cmAuthor id="0" name="Reviewer" initials="R" '
              f'lastIdx="1" clrIdx="0"/></p:cmAuthorLst>')
    _add_part(deck, slide.part, "/ppt/comments/comment1.xml", (CT.PML_COMMENTS, RT.COMMENTS),
              f'{XML_HEAD}<p:cmLst xmlns:p="{P_NS}"><p:cm authorId="0" dt="2026-10-01T10:00:00.000" idx="1">'
              f'<p:pos x="10" y="10"/><p:text>{escape(text)}</p:text></p:cm></p:cmLst>')


def _modern_comment(deck: Deck, slide: Slide, text: str) -> None:
    _add_part(deck, deck.part, "/ppt/authors.xml", MODERN_AUTHORS,
              f'{XML_HEAD}<p188:authorLst xmlns:p188="{P188_NS}"><p188:author id="{AUTHOR_ID}" name="Reviewer" '
              f'initials="R" userId="Reviewer" providerId="None"/></p188:authorLst>')
    link = _add_part(
        deck, slide.part, "/ppt/comments/modernComment_1.xml", MODERN_COMMENTS,
        f'{XML_HEAD}<p188:cmLst xmlns:a="{A_NS}" xmlns:r="{R_NS}" xmlns:p188="{P188_NS}">'
        f'<p188:cm id="{{8A2B6C1D-0000-4000-8000-000000000002}}" authorId="{AUTHOR_ID}" '
        f'created="2026-10-01T10:00:00.000"><pc:sldMkLst xmlns:pc="{PC_NS}"><pc:docMk/>'
        f'<pc:sldMk cId="0" sldId="{slide.slide_id}"/></pc:sldMkLst><p188:txBody><a:bodyPr/><a:lstStyle/>'
        f'<a:p><a:r><a:t>{escape(text)}</a:t></a:r></a:p></p188:txBody></p188:cm></p188:cmLst>')
    ext = etree.SubElement(etree.SubElement(slide._element, qn("p:extLst")), qn("p:ext"), uri=MODERN_COMMENT_EXT)
    etree.SubElement(ext, f"{{{P188_NS}}}commentRel", nsmap={"p188": P188_NS}).set(qn("r:id"), link)


def _footer(slide: Slide, number: int) -> None:
    """Copy the layout's footer and slide-number placeholders onto the slide and fill them, as PowerPoint does."""
    for placeholder in slide.slide_layout.placeholders:
        kind = placeholder.placeholder_format.type
        if kind not in (PP_PLACEHOLDER.FOOTER, PP_PLACEHOLDER.SLIDE_NUMBER):
            continue
        element = copy.deepcopy(placeholder._element)
        slide.shapes._spTree.append(element)
        if kind == PP_PLACEHOLDER.SLIDE_NUMBER:
            for field_text in element.iter(qn("a:t")):
                field_text.text = str(number)          # PowerPoint saves the real number inside the field
        else:
            body = element.find(qn("p:txBody"))
            for paragraph in body.findall(qn("a:p")):
                body.remove(paragraph)
            run = etree.SubElement(etree.SubElement(body, qn("a:p")), qn("a:r"))
            etree.SubElement(run, qn("a:t")).text = FOOTER


def _png() -> io.BytesIO:
    buffer = io.BytesIO()
    Image.new("RGB", (120, 80), "white").save(buffer, "PNG")
    buffer.seek(0)
    return buffer


def _box(slide: Slide, lines: list[str], top: float, left: float = 1, font: str | None = None) -> None:
    frame = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(4), Inches(1)).text_frame
    for i, line in enumerate(lines):
        paragraph = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
        paragraph.text = line
        for run in paragraph.runs:
            if font is not None:
                run.font.name = font


def _write_lecture(path: Path) -> Path:
    """Eleven slides, one case per slide; the expected blocks are listed in the first test of this part."""
    deck = Presentation()

    def slide(layout: str) -> Slide:
        return deck.slides.add_slide(deck.slide_layouts[LAYOUT[layout]])

    cover = slide("title")                                         # 1: titled with the deck's own name
    cover.shapes.title.text = "Stacks"
    cover.placeholders[1].text = "Lecture 4"
    cover.notes_slide.notes_text_frame.text = "Welcome everyone."
    _legacy_comment(deck, cover, "Reviewer: fix the cover")
    bullets = slide("content")                                     # 2: bullets, notes, a modern comment, footer
    bullets.shapes.title.text = "Push and pop"
    frame = bullets.placeholders[1].text_frame
    frame.text = "Push adds on top"
    second = frame.add_paragraph()
    second.text, second.level = "Pop removes the top", 1
    bullets.notes_slide.notes_text_frame.text = "Mention the call stack."
    _modern_comment(deck, bullets, "Reviewer: tighten this")
    _footer(bullets, 2)
    slide("blank")                                                 # 3: empty
    slide("blank").notes_slide.notes_text_frame.text = "Draw the stack on the board."   # 4: notes only
    untitled = slide("blank")                                      # 5: no title
    _box(untitled, ["A slide without a title."], top=2)
    _footer(untitled, 5)
    costs = slide("title_only")                                    # 6: a table
    costs.shapes.title.text = "Costs"
    table = costs.shapes.add_table(3, 2, Inches(1), Inches(2), Inches(6), Inches(2)).table
    for row, cells in enumerate([("Operation", "Cost"), ("push", "O(1)"), ("search", "O(n)")]):
        for col, text in enumerate(cells):
            table.cell(row, col).text = text
    _footer(costs, 6)
    figure = slide("title_only")                                   # 7: picture, grouped shapes, chart
    figure.shapes.title.text = "Diagram"
    figure.shapes.add_picture(_png(), Inches(1), Inches(2))
    group = figure.shapes.add_group_shape()
    for i, text in enumerate(["head node", "next pointer"]):
        group.shapes.add_textbox(Inches(4), Inches(2 + i), Inches(2), Inches(1)).text_frame.text = text
    chart = CategoryChartData()
    chart.categories = ["push calls", "pop calls"]
    chart.add_series("calls per test", (3, 1))
    figure.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(6), Inches(4), Inches(3), Inches(2), chart)
    _footer(figure, 7)
    recap = slide("content")                                       # 8: a later slide titled like the deck
    recap.shapes.title.text = "STACKS"
    recap.placeholders[1].text = "Recap of the lecture"
    _footer(recap, 8)
    hidden = slide("content")                                      # 9: hidden
    hidden.shapes.title.text = "Hidden extra"
    hidden.placeholders[1].text = "Only shown on request"
    hidden._element.set("show", "0")
    code = slide("title_only")                                     # 10: C++ in a monospace text box
    code.shapes.title.text = "Code"
    _box(code, ["// sum an array", "for (int i = 0; i < n; i++)", "    sum += a[i];"], top=2, font="Courier New")
    _footer(code, 10)
    slide("blank").shapes.add_picture(_png(), Inches(1), Inches(1))  # 11: a picture and nothing else
    deck.save(str(path))
    return path


@pytest.fixture(scope="module")
def module_data_dir(tmp_path_factory) -> Iterator[Path]:
    """One empty data folder for this part, so Docling's cache never touches the real data/ folder."""
    folder = tmp_path_factory.mktemp("data")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(settings, "INGESTION_DATA_DIR", str(folder))
        yield folder


@pytest.fixture(scope="module")
def lecture_file(tmp_path_factory) -> Path:
    return _write_lecture(tmp_path_factory.mktemp("deck") / FILE_NAME)


def _meta_for(path: Path) -> ResourceMeta:
    return _meta(path.name, hashlib.sha256(path.read_bytes()).hexdigest())   # the real hash: the cache key


@pytest.fixture(scope="module")
def lecture(module_data_dir, lecture_file) -> ParsedDocument:
    """The generated deck, read by real Docling once for every test in this part."""
    return load(lecture_file, _meta_for(lecture_file))


def _on(doc: ParsedDocument, slide: int) -> list[str]:
    return [b.text for b in doc.blocks if b.loc.slide == slide]


def _table_cells(markdown: str) -> list[list[str]]:
    """A Markdown table's cells, row by row, without the |---| line: spacing may change between versions."""
    lines = [line for line in markdown.splitlines() if set(line) - set("|-: ")]
    return [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]


def test_real_docling_gives_these_blocks_in_reading_order(lecture):
    rows = _rows(lecture)
    table = next(text for kind, text, slide in rows if kind == "table" and slide == 6)
    chart = next(text for kind, text, slide in rows if kind == "table" and slide == 7)
    assert rows == [
        ("paragraph", "Lecture 4", 1),
        ("slide_notes", "Welcome everyone.", 1),
        ("heading", "Push and pop", 2),
        ("list_item", "- Push adds on top", 2),
        ("list_item", "- Pop removes the top", 2),
        ("slide_notes", "Mention the call stack.", 2),
        ("slide_notes", "Draw the stack on the board.", 4),
        ("paragraph", "A slide without a title.", 5),
        ("heading", "Costs", 6),
        ("table", table, 6),
        ("heading", "Diagram", 7),
        ("figure", "[Figure]", 7),
        ("paragraph", "head node", 7),
        ("paragraph", "next pointer", 7),
        ("figure", "[Figure]", 7),
        ("table", chart, 7),
        ("list_item", "- Recap of the lecture", 8),
        ("heading", "Hidden extra", 9),
        ("list_item", "- Only shown on request", 9),
        ("heading", "Code", 10),
        ("paragraph", "// sum an array", 10),
        ("paragraph", "for (int i = 0; i < n; i++)", 10),
        ("paragraph", "sum += a[i];", 10),
        ("figure", "[Figure]", 11),
    ]
    assert _table_cells(table) == [["Operation", "Cost"], ["push", "O(1)"], ["search", "O(n)"]]


def test_every_block_cites_a_slide_of_the_deck(lecture):
    slides = [b.loc.slide for b in lecture.blocks]
    assert all(s is not None and 1 <= s <= SLIDES_IN_LECTURE for s in slides)
    assert slides == sorted(slides)                              # never back to an earlier slide


def test_seq_counts_up_without_gaps(lecture):
    assert [b.seq for b in lecture.blocks] == list(range(len(lecture.blocks)))


def test_every_heading_path_starts_with_the_title_from_the_file_name(lecture):
    assert lecture.title == TITLE
    assert all(b.heading_path[0] == TITLE for b in lecture.blocks)


def test_speaker_notes_stay_with_their_own_slide(lecture):
    assert [(b.text, b.loc.slide) for b in lecture.blocks if b.kind == "slide_notes"] == [
        ("Welcome everyone.", 1), ("Mention the call stack.", 2), ("Draw the stack on the board.", 4),
    ]


@pytest.mark.parametrize(("part", "words"), [
    pytest.param("ppt/comments/comment1.xml", "fix the cover", id="legacy comment"),
    pytest.param("ppt/comments/modernComment_1.xml", "tighten this", id="modern comment"),
])
def test_reviewers_comments_never_become_content(lecture, lecture_file, part, words):
    with zipfile.ZipFile(lecture_file) as archive:
        assert words in archive.read(part).decode()               # the comment really is in the file
    assert not any(words in b.text for b in lecture.blocks)


def test_footers_and_slide_numbers_never_become_content(lecture):
    assert not any(FOOTER in b.text or b.text.isdigit() for b in lecture.blocks)


@pytest.mark.parametrize("slide", [4, 5, 8], ids=["notes only", "no title", "titled like the deck"])
def test_a_slide_without_its_own_title_is_cited_under_the_deck_title_only(lecture, slide):
    assert {tuple(b.heading_path) for b in lecture.blocks if b.loc.slide == slide} == {(TITLE,)}


def test_empty_and_hidden_slides_keep_the_numbering(lecture):
    assert lecture.quality.units_total == SLIDES_IN_LECTURE
    assert _on(lecture, 3) == []                                  # empty: no blocks, and slide 4 is still slide 4
    assert _on(lecture, 9) == ["Hidden extra", "- Only shown on request"]    # hidden slides are kept on purpose


def test_hidden_slides_are_kept_and_marked_in_extra(lecture):
    assert {b.loc.slide for b in lecture.blocks if b.extra.get("hidden")} == {9}


def test_figure_words_stay_paragraphs_and_chart_data_becomes_a_table(lecture):
    assert not any(b.kind == "figure_text" for b in lecture.blocks)          # Docling puts no words in pictures
    assert _on(lecture, 7)[:4] == ["Diagram", "[Figure]", "head node", "next pointer"]
    chart = next(b for b in lecture.blocks if b.loc.slide == 7 and b.kind == "table")
    figures = [b.figure_id for b in lecture.blocks if b.loc.slide == 7 and b.kind == "figure"]
    assert len(set(figures)) == 2 and chart.figure_id == figures[-1]       # the chart's "[Figure]" and its numbers
    assert chart.extra["ref"].startswith("#/pictures/")                     # Docling's chart, not a real table
    assert _table_cells(chart.text) == [["", "calls per test"], ["push calls", "3"], ["pop calls", "1"]]


def test_code_lines_stay_in_order_but_lose_their_indent(lecture):
    assert _on(lecture, 10)[1:] == ["// sum an array", "for (int i = 0; i < n; i++)", "sum += a[i];"]


def test_a_picture_only_slide_is_named_in_the_warnings(lecture):
    assert lecture.quality.status == "degraded"
    assert lecture.quality.warnings == [messages.no_text_units("Slides", [11])]


def test_every_shape_of_the_lecture_is_accounted_for(module_data_dir, lecture_file):
    found = extract(lecture_file, _meta_for(lecture_file).file_sha256, TITLE)
    assert Counter(e.bucket for e in found.coverage) == Counter({
        "extracted": 18, "skipped:footer": 6, "skipped:slide number": 6,
        "skipped:picture": 2, "skipped:deck title": 2,
    })                                                            # and nothing "unknown"


def test_the_result_passes_the_contract_check_the_dispatcher_runs(lecture):
    assert ParsedDocument.model_validate(lecture.model_dump()) == lecture


def test_loading_twice_gives_identical_output_even_from_the_cache(lecture, lecture_file):
    from app.ingestion.converter import cache_file

    meta = _meta_for(lecture_file)
    assert cache_file(meta.file_sha256, "pptx").exists()         # the second load really reads the cache
    assert load(lecture_file, meta).model_dump_json() == lecture.model_dump_json()


# ================================================================ part 3: broken files through ingest_file()

def _write_small_deck(path: Path) -> None:
    deck = Presentation()
    deck.slides.add_slide(deck.slide_layouts[LAYOUT["title_only"]]).shapes.title.text = "Push"
    deck.save(str(path))


def _write_good_deck(path: Path) -> None:
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[LAYOUT["title_only"]])
    slide.shapes.title.text = "Push"
    _box(slide, ["Adds on top."], top=2)
    deck.save(str(path))


def _write_truncated(path: Path) -> None:
    _write_small_deck(path)
    path.write_bytes(path.read_bytes()[: path.stat().st_size // 2])


def _write_pictures_only(path: Path) -> None:
    deck = Presentation()
    deck.slides.add_slide(deck.slide_layouts[LAYOUT["blank"]]).shapes.add_picture(_png(), Inches(1), Inches(1))
    deck.save(str(path))


def _write_word_file(path: Path) -> None:
    from docx import Document

    document = Document()
    document.add_paragraph("A Word file saved with a .pptx name.")
    document.save(str(path))


def _write_zip(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("notes.txt", "a zip file, but not a presentation")


@pytest.mark.parametrize(("write", "reason"), [
    pytest.param(lambda p: p.write_bytes(b""), messages.TYPE_MISMATCH, id="empty file"),
    pytest.param(lambda p: p.write_bytes(b"not a presentation"), messages.TYPE_MISMATCH, id="plain text"),
    pytest.param(lambda p: Presentation().save(str(p)), messages.UNREADABLE, id="no slides"),
    pytest.param(_write_truncated, messages.UNREADABLE, id="cut off"),
    pytest.param(_write_zip, messages.UNREADABLE, id="zip, not a deck"),
    pytest.param(_write_word_file, messages.TYPE_MISMATCH, id="renamed Word file"),
    pytest.param(_write_small_deck, messages.NO_TEXT_FILE, id="titles only"),
])
def test_a_broken_or_empty_deck_fails_with_a_teacher_message(data_dir, tmp_path, write, reason):
    path = tmp_path / "upload.pptx"
    write(path)
    doc = ingest_file(path, "r1", "c1")
    assert (doc.quality.status, doc.quality.warnings, doc.blocks) == ("failed", [reason], [])
    assert parsed_path("r1").exists()                             # the failure is saved like any result


def test_a_deck_of_pictures_only_goes_through_with_a_figure_block_per_picture(data_dir, tmp_path):
    path = tmp_path / "upload.pptx"
    _write_pictures_only(path)
    doc = ingest_file(path, "r1", "c1")
    assert (doc.quality.status, _rows(doc)) == ("degraded", [("figure", "[Figure]", 1)])     # contract 2.1
    assert doc.quality.warnings == [messages.no_text_units("Slides", [1])]


def test_a_crash_inside_docling_fails_politely_and_logs_the_traceback(data_dir, tmp_path, monkeypatch, caplog):
    from app.ingestion import converter

    def crash(path: Path, source_type: str, file_sha256: str | None = None) -> None:
        raise RuntimeError("Docling broke")

    monkeypatch.setattr(converter, "convert", crash)
    path = tmp_path / "upload.pptx"
    _write_small_deck(path)
    with caplog.at_level(logging.ERROR, logger="tta.ingestion"):
        doc = ingest_file(path, "r1", "c1")
    assert (doc.quality.status, doc.quality.warnings) == ("failed", [messages.INTERNAL])
    assert any(r.exc_info and "Docling broke" in str(r.exc_info[1]) for r in caplog.records)


def test_a_good_deck_goes_all_the_way_through_ingest_file(data_dir, tmp_path):
    path = tmp_path / "upload.pptx"
    _write_good_deck(path)
    doc = ingest_file(path, "r1", "c1")
    assert (doc.quality.status, _rows(doc)) == ("ok", [("heading", "Push", 1), ("paragraph", "Adds on top.", 1)])
    assert is_heavy("pptx")                                       # one Docling file at a time: see register()