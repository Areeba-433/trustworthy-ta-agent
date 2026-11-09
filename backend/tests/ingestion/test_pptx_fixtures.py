"""The script-made PowerPoint fixtures: every deck builds, opens again in python-pptx, and holds what it should."""
import io

import pytest
from PIL import Image
from pptx import Presentation
from pptx.shapes.group import GroupShape
from pptx.shapes.picture import Picture

from tests.ingestion.pptx_fixtures import (BUILDERS, ICON_PX, LOGO_PX, MIXED_SLIDES, TEXTS, Census, all_texts,
                                           census, deck_bytes)

EXPECTED: dict[str, Census] = {
    "title_bullets": Census(slides=1),
    "with_notes": Census(slides=1, notes=1),
    "picture_only": Census(slides=1, pictures=1),
    "picture_caption": Census(slides=1, pictures=1, textboxes=1),
    "flowchart": Census(slides=1, connectors=2, glued_ends=4, autoshapes=3),
    "loose_shapes": Census(slides=1, autoshapes=3),
    "grouped": Census(slides=1, textboxes=3, groups=2),
    "table": Census(slides=1, tables=1),
    "chart": Census(slides=1, charts=1),
    "no_title": Census(slides=1, textboxes=1),
    "empty_slide": Census(slides=1),
    "hidden_slide": Census(slides=1, notes=1, hidden=1),
    "repeated_logo": Census(slides=4, pictures=4, notes=4),
    "tiny_icon": Census(slides=1, pictures=1),
    "reading_order": Census(slides=1, textboxes=3),
    "mixed_deck": Census(slides=8, pictures=10, connectors=2, glued_ends=4, autoshapes=6, textboxes=7, groups=2,
                         tables=1, charts=1, notes=1, hidden=1),
}


def _open(name: str):
    return Presentation(io.BytesIO(deck_bytes(name)))


def _all_text(deck) -> list[str]:
    """Every text in a deck: shapes (groups included), tables, chart labels and speaker notes."""
    found = []

    def shapes(items):
        for shape in items:
            if isinstance(shape, GroupShape):
                shapes(shape.shapes)
            if shape.has_text_frame:
                found.extend(p.text for p in shape.text_frame.paragraphs if p.text)
            if getattr(shape, "has_table", False):
                found.extend(cell.text for row in shape.table.rows for cell in row.cells)
            if getattr(shape, "has_chart", False):
                found.extend([*shape.chart.plots[0].categories, *(s.name for s in shape.chart.series)])

    for slide in deck.slides:
        shapes(slide.shapes)
        if slide.has_notes_slide:
            found.extend(p.text for p in slide.notes_slide.notes_text_frame.paragraphs if p.text)
    return found


def test_every_builder_has_an_expected_census():
    assert set(BUILDERS) == set(EXPECTED)


@pytest.mark.parametrize("name", sorted(BUILDERS))
def test_each_deck_opens_again_and_holds_what_it_should(name):
    assert census(_open(name)) == EXPECTED[name]


@pytest.mark.parametrize("name", sorted(BUILDERS))
def test_no_deck_holds_any_text_but_the_made_up_labels(name):
    assert set(_all_text(_open(name))) <= all_texts()            # the repo is public: no real course text


def test_pictures_have_the_sizes_the_rules_are_about():
    def sizes(name: str) -> set[tuple[int, int]]:
        return {Image.open(io.BytesIO(shape.image.blob)).size for slide in _open(name).slides
                for shape in slide.shapes if isinstance(shape, Picture)}

    assert sizes("tiny_icon") == {ICON_PX}
    assert sizes("repeated_logo") == {LOGO_PX}


def test_the_repeated_logo_is_the_same_picture_on_every_slide():
    blobs = {shape.image.sha1 for slide in _open("repeated_logo").slides for shape in slide.shapes
             if isinstance(shape, Picture)}
    assert len(blobs) == 1


def test_reading_order_shapes_are_added_out_of_order_but_placed_top_to_bottom():
    shapes = list(_open("reading_order").slides[0].shapes)
    by_xml = [TEXTS["order"].index(shape.text_frame.text) for shape in shapes]
    by_position = [TEXTS["order"].index(shape.text_frame.text) for shape in sorted(shapes, key=lambda s: s.top)]
    assert (by_xml, by_position) == ([2, 0, 1], [0, 1, 2])


def test_the_mixed_deck_has_one_slide_per_entry_and_the_logo_on_all_but_the_last():
    deck = _open("mixed_deck")
    logo_slides = [n for n, slide in enumerate(deck.slides, start=1)
                   if any(isinstance(s, Picture) and Image.open(io.BytesIO(s.image.blob)).size == LOGO_PX
                          for s in slide.shapes)]
    assert len(deck.slides) == len(MIXED_SLIDES) == 8
    assert logo_slides == list(range(1, 8))                   # 7 of 8 slides: more than half