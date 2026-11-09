"""Phase 1 of the PowerPoint loader on the script-made fixture decks (pptx_fixtures.py): refusals, chart data,
hidden slides and the coverage audit. Every deck is built in code; no real course file is used."""
import hashlib
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.core.config import settings
from app.ingestion import messages
from app.ingestion.cleaning.common import title_from_filename
from app.ingestion.contract import PrecheckResult, ResourceMeta
from app.ingestion.documents import FileRefused
from app.ingestion.loaders.pptx import Extraction, extract, load
from tests.ingestion.pptx_fixtures import BUILDERS, TEXTS, all_texts, write_deck


@pytest.fixture(scope="module")
def decks(tmp_path_factory) -> Iterator[dict[str, Path]]:
    """Every fixture deck, written once; Docling's cache goes to a temporary folder for the whole module."""
    folder = tmp_path_factory.mktemp("phase1")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(settings, "INGESTION_DATA_DIR", str(folder / "data"))
        yield {name: write_deck(name, folder / "decks") for name in BUILDERS}


@pytest.fixture(scope="module")
def extracted(decks) -> dict[str, Extraction]:
    return {name: extract(path, _sha(path), title_from_filename(path.name)) for name, path in decks.items()}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _meta(path: Path) -> ResourceMeta:
    return ResourceMeta(resource_id="r1", course_id="c1", file_name=path.name, file_sha256=_sha(path),
                        precheck=PrecheckResult(source_type="pptx"))


# ================================================================ 1.2: refusal and the picture-only warning

@pytest.mark.parametrize("name", ["picture_only", "tiny_icon"])
def test_a_deck_whose_only_text_is_titles_is_refused(decks, name):
    with pytest.raises(FileRefused) as refused:
        load(decks[name], _meta(decks[name]))
    assert refused.value.reason == messages.NO_TEXT_FILE


def test_the_mixed_deck_names_its_title_and_picture_slide(decks):
    doc = load(decks["mixed_deck"], _meta(decks["mixed_deck"]))
    assert (doc.quality.status, doc.quality.warnings) == ("degraded", [messages.no_text_units("Slides", [2])])


# ================================================================ 1.3: chart data from Docling

def test_a_chart_becomes_one_table_block_and_the_deck_is_ok(decks, extracted):
    heading, chart = extracted["chart"].blocks
    assert (heading.kind, chart.kind, chart.loc.slide) == ("heading", "table", 1)
    assert all(word in chart.text for word in TEXTS["chart"]["categories"] + TEXTS["chart"]["series"])
    assert chart.extra["ref"].startswith("#/pictures/") and chart.heading_path == heading.heading_path
    doc = load(decks["chart"], _meta(decks["chart"]))
    assert (doc.quality.status, [b.seq for b in doc.blocks]) == ("ok", [0, 1])     # seq numbered again


def test_the_chart_table_ends_its_slide_in_the_mixed_deck(extracted):
    kinds = [b.kind for b in extracted["mixed_deck"].blocks if b.loc.slide == 7]
    assert kinds == ["heading", "paragraph", "paragraph", "paragraph", "table"]


# ================================================================ 1.4: hidden slides

def test_every_block_of_a_hidden_slide_says_so(extracted):
    assert [b.extra.get("hidden") for b in extracted["hidden_slide"].blocks] == [True, True, True]
    assert not any("hidden" in b.extra for b in extracted["with_notes"].blocks)   # the same slide, shown


def test_only_the_hidden_slide_of_the_mixed_deck_is_marked(extracted):
    assert extracted["mixed_deck"].deck.hidden_slides == {6}
    assert {b.loc.slide for b in extracted["mixed_deck"].blocks if b.extra.get("hidden")} == {6}


# ================================================================ 1.5: coverage audit

@pytest.mark.parametrize("name", sorted(BUILDERS))
def test_every_shape_of_every_fixture_is_accounted_for(extracted, name):
    found = extracted[name]
    expected = sum(len(slide.shapes) + bool(slide.notes) for slide in found.deck.slides)
    assert len(found.coverage) == expected                       # exactly one bucket per shape (and notes)
    assert all(e.bucket in ("extracted", "unknown") or e.bucket.startswith("skipped:") for e in found.coverage)
    assert [e for e in found.coverage if e.bucket == "unknown"] == []


def test_the_mixed_deck_coverage_in_numbers(extracted):
    assert Counter(e.bucket for e in extracted["mixed_deck"].coverage) == Counter(
        {"extracted": 23, "skipped:picture": 10, "skipped:connector": 2})


def test_a_shape_whose_text_the_blocks_lost_is_unknown(extracted):
    from app.ingestion.loaders import _pptx_shapes as shapes

    found = extracted["grouped"]
    lost = [b for b in found.blocks if TEXTS["grouped"][2] not in b.text]
    entries = shapes.audit(found.deck, lost, [], found.title)
    assert [(e.slide, e.tag) for e in entries if e.bucket == "unknown"] == [(1, "sp (text box)")]


@pytest.mark.parametrize("name", sorted(BUILDERS))
def test_the_coverage_summary_holds_numbers_and_shape_types_only(extracted, name):
    from app.ingestion.loaders import _pptx_shapes as shapes

    printed = "\n".join(shapes.summary(extracted[name].coverage))
    assert not [text for text in all_texts() if text in printed]


# ================================================================ 1.7: slide titles typed in text boxes

def test_a_text_box_title_becomes_the_slide_heading(extracted):
    texts = TEXTS["box_titles"]
    assert [(b.loc.slide, b.kind, b.text) for b in extracted["text_box_titles"].blocks] == [
        (1, "heading", texts["first"]), (1, "paragraph", texts["body"]),
        (2, "paragraph", texts["kicker"]), (2, "heading", texts["second"]),
        (2, "paragraph", texts["formula"]), (2, "paragraph", texts["body2"]),
    ]                                                            # the 90 pt star has no words: never a title


def test_every_block_is_cited_under_its_own_slides_title(extracted):
    found = extracted["text_box_titles"]
    titles = {1: TEXTS["box_titles"]["first"], 2: TEXTS["box_titles"]["second"]}
    assert all(b.heading_path == [found.title, titles[b.loc.slide]] for b in found.blocks)


@pytest.mark.parametrize("name", ["no_title", "reading_order", "picture_caption"])
def test_a_lone_box_boxes_of_one_size_or_a_low_caption_are_no_title(extracted, name):
    assert not any(b.kind == "heading" for b in extracted[name].blocks)


def test_font_sizes_come_from_the_paragraph_or_the_run(extracted):
    first, second = extracted["text_box_titles"].deck.slides
    assert [sorted(round(s.size) for s in slide.shapes) for slide in (first, second)] == [
        [18, 29], [12, 14, 28, 30, 90]]


@pytest.mark.parametrize(("body", "points"), [
    pytest.param('<a:lstStyle><a:lvl1pPr><a:defRPr sz="2400"/></a:lvl1pPr></a:lstStyle>'
                 '<a:p><a:r><a:t>x</a:t></a:r></a:p>', 24.0, id="the shape's list style"),
    pytest.param('<a:p><a:r><a:t>x</a:t></a:r></a:p>', 20.0, id="the presentation's default"),
    pytest.param('<a:bodyPr><a:normAutofit fontScale="50000"/></a:bodyPr>'
                 '<a:p><a:pPr><a:defRPr sz="3000"/></a:pPr><a:r><a:t>x</a:t></a:r></a:p>', 15.0,
                 id="shrunk to fit"),
])
def test_a_size_set_nowhere_on_the_run_is_inherited_like_powerpoint(body, points):
    from lxml import etree

    from app.ingestion.loaders._pptx_shapes import NS, font_size

    shape = etree.fromstring(f'<p:sp xmlns:p="{NS["p"]}" xmlns:a="{NS["a"]}"><p:txBody>{body}</p:txBody></p:sp>')
    assert font_size(shape, {1: 20.0}) == points


def _box(text: str, points: float, top: float, placeholder: str | None = None):
    from app.ingestion.loaders._pptx_shapes import Paragraph, Shape

    return Shape(1, "sp (text box)", "text", placeholder, (Paragraph(text),), top=top, size=points)


@pytest.mark.parametrize(("boxes", "title"), [
    pytest.param([("Title words", 28, 0.1), ("Body words here", 14, 0.4)], "Title words", id="clear title"),
    pytest.param([("Kicker words", 12, 0.05), ("Title words", 28, 0.1), ("Formula words", 30, 0.35),
                  ("Body words", 14, 0.6)], "Title words", id="a bigger formula below"),
    pytest.param([("Title words", 30, 0.04), ("Body words", 13, 0.22, "obj")], "Title words",
                 id="body text in a placeholder"),
    pytest.param([("Only words", 28, 0.1)], None, id="a lone box"),
    pytest.param([("One words", 18, 0.1), ("Two words", 18, 0.3)], None, id="one size"),
    pytest.param([("Low title", 28, 0.6), ("Body words", 14, 0.2)], None, id="starts in the lower half"),
])
def test_which_text_box_is_the_title(boxes, title):
    from app.ingestion.loaders import pptx as loader
    from app.ingestion.loaders._pptx_shapes import Slide

    assert loader._slide_title(Slide(1, shapes=[_box(*box) for box in boxes])) == title