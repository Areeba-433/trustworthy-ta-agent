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