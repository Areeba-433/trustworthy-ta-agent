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
from pptx_fixtures import BUILDERS, TEXTS, all_texts, write_deck


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