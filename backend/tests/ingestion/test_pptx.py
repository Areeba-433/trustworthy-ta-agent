"""The PowerPoint loader, tested three ways.

Part 1 hands load() small Docling documents built by hand (Docling does not run), so each slide rule is tested on
exactly the case it is about. Part 2 runs real Docling on a deck generated here: contract tests that turn red if a
Docling upgrade changes its output. Part 3 sends broken files through ingest_file(), the way an upload arrives.
Every deck is generated in code with python-pptx: the repo is public, so no real course files.
"""
from collections.abc import Callable
from pathlib import Path

import pytest
from docling_core.types.doc import (BoundingBox, ContentLayer, DocItemLabel, DoclingDocument, GroupItem,
                                    GroupLabel, ProvenanceItem, Size)

from app.ingestion import messages
from app.ingestion.contract import ParsedDocument, PrecheckResult, ResourceMeta
from app.ingestion.loaders.pptx import load

FILE_NAME = "Stacks_final.pptx"       # title_from_filename() turns this into TITLE
TITLE = "Stacks"
FOOTER = "CS-201 Data Structures"     # typed in the footer of most slides, like a real lecture deck
SLIDE_SIZE = Size(width=960, height=540)
# one different sentence per slide: find_repeated_lines() treats digits as equal ("Point 1" = "Point 2")
POINTS = ["Push adds on top.", "Pop removes the top.", "Peek reads the top.", "Empty checks the size."]


def _meta(file_name: str = FILE_NAME, file_sha256: str = "0" * 64) -> ResourceMeta:
    return ResourceMeta(resource_id="r1", course_id="c1", file_name=file_name, file_sha256=file_sha256,
                        precheck=PrecheckResult(source_type="pptx"))


# ================================================================ part 1: hand-built Docling results

def _prov(slide: int) -> ProvenanceItem:
    return ProvenanceItem(page_no=slide, bbox=BoundingBox(l=0, t=0, r=1, b=1), charspan=(0, 0))


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

    def picture(self, slide: int) -> "_Slides":
        self.doc.add_picture(prov=_prov(slide), parent=self._groups[slide - 1])
        return self


@pytest.fixture
def load_slides(monkeypatch) -> Callable[..., ParsedDocument]:
    """load() on a hand-built Docling result: no file is read, Docling never runs, nothing is cached."""
    from app.ingestion import converter            # imported here: it takes seconds to import

    def run(slides: _Slides, problems: tuple[str, ...] = ()) -> ParsedDocument:
        conversion = converter.Conversion(slides.doc, problems)
        monkeypatch.setattr(converter, "convert", lambda path, source_type, file_sha256=None: conversion)
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


def test_a_deck_without_any_text_fails_with_the_no_text_message(load_slides):
    doc = load_slides(_Slides(2).picture(1).picture(2))
    assert (doc.quality.status, doc.quality.warnings, doc.blocks) == ("failed", [messages.NO_TEXT_FILE], [])


def test_a_partial_docling_result_is_degraded_and_its_problem_comes_first(load_slides):
    doc = load_slides(_Slides(2).text(1, "Some text.").picture(2), problems=(messages.PARTIAL,))
    assert doc.quality.status == "degraded"
    assert doc.quality.warnings == [messages.PARTIAL, messages.no_text_units("Slides", [2])]