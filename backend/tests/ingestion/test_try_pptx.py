"""scripts/try_pptx.py on the fixture decks: it counts correctly and never prints a word from a deck."""
import pytest

from app.core.config import settings
from scripts import try_pptx
from tests.ingestion.pptx_fixtures import BUILDERS, all_texts, write_deck


@pytest.fixture(scope="module")
def reports(tmp_path_factory) -> dict:
    """Every fixture deck measured once: python-pptx and Docling only (no classifier download, no LibreOffice)."""
    folder = tmp_path_factory.mktemp("decks")
    return {name: try_pptx.measure(write_deck(name, folder), classifier=False, libreoffice=False)
            for name in BUILDERS}


@pytest.mark.parametrize("name", sorted(BUILDERS))
def test_the_report_never_contains_slide_text(reports, name):
    printed = "\n".join(try_pptx.lines(reports[name]))
    assert not [text for text in all_texts() if text in printed]


def test_the_mixed_deck_numbers(reports):
    report = reports["mixed_deck"]
    slides = report["slides"]
    assert (len(slides), len(report["pictures"]), sum(s.hidden for s in slides)) == (8, 10, 1)
    assert [s.number for s in slides if s.diagram_rule] == [4, 7]                # the flowchart; the loose shapes
    assert sum(p.in_docling for p in report["pictures"]) == 10                     # every picture matched by pixels
    assert [hit for _, hit in report["docling"]["runs"]] == [False, True]         # the second parse is a cache hit


def test_measuring_leaves_the_data_folder_setting_as_it_was(reports):
    assert "try_pptx_" not in str(settings.INGESTION_DATA_DIR)