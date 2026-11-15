"""Where blocks stand on a slide (loaders/_pptx_layout.py): reading order, number cells, code, footers by place,
section labels and figure places, on the script-made slide_layout deck and on hand-made boxes. Every deck is built
in code; no real course file is used."""
import hashlib
from collections.abc import Iterator
from pathlib import Path
import pytest

from app.core.config import settings
from app.ingestion.cleaning.common import title_from_filename
from app.ingestion.contract import PrecheckResult, ResourceMeta
from app.ingestion.loaders import _pptx_layout as layout
from app.ingestion.loaders.pptx import Extraction, extract, load
from tests.ingestion.pptx_fixtures import TEXTS, write_deck

LAYOUT = TEXTS["layout"]
DECKS = ["slide_layout", "picture_only", "chart"]


@pytest.fixture(scope="module")
def decks(tmp_path_factory) -> Iterator[dict[str, Path]]:
    """The decks these tests read, written once; Docling's cache goes to a temporary folder for the whole module."""
    folder = tmp_path_factory.mktemp("layout")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(settings, "INGESTION_DATA_DIR", str(folder / "data"))
        yield {name: write_deck(name, folder / "decks") for name in DECKS}


@pytest.fixture(scope="module")
def extracted(decks) -> dict[str, Extraction]:
    return {name: extract(path, _sha(path), title_from_filename(path.name)) for name, path in decks.items()}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _texts(found: Extraction, slide: int) -> list[str]:
    return [b.text for b in found.blocks if b.loc.slide == slide and b.kind != "heading"]


# ================================================================ reading order on the fixture deck

def test_a_row_of_number_cells_is_one_line_between_its_label_and_the_sentence_under_it(extracted):
    assert _texts(extracted["slide_layout"], 1) == [LAYOUT["row_label"], " ".join(LAYOUT["cells"]), LAYOUT["under"]]


def test_each_half_reads_its_label_then_its_own_boxes(extracted):
    left, right = LAYOUT["halves"]
    assert _texts(extracted["slide_layout"], 2) == [left, *LAYOUT["pairs"][:2], right, *LAYOUT["pairs"][2:],
                                                    LAYOUT["columns_note"]]


def test_each_card_reads_its_case_then_its_value(extracted):
    pairs = zip(LAYOUT["cases"], LAYOUT["values"])
    assert _texts(extracted["slide_layout"], 3) == [text for pair in pairs for text in pair]


def test_a_map_is_read_before_the_step_panel_beside_it_and_its_lone_numbers_stay_out(extracted):
    texts = _texts(extracted["slide_layout"], 5)
    assert texts[-3:] == LAYOUT["panel"] and sorted(texts[:-3]) == sorted(LAYOUT["nodes"])


def test_two_boards_side_by_side_are_read_board_by_board(extracted):
    one, two = (LAYOUT["tiles"][0], LAYOUT["tiles"][1])
    assert _texts(extracted["slide_layout"], 6) == [LAYOUT["boards"][0], " ".join(one[:2]), " ".join(one[2:]),
                                                    LAYOUT["boards"][1], " ".join(two[:2]), " ".join(two[2:])]


# ================================================================ code, footers, section labels

def test_indented_lines_or_a_fixed_width_font_make_one_code_block_each(extracted):
    blocks = [b for b in extracted["slide_layout"].blocks if b.loc.slide == 4 and b.kind != "heading"]
    assert [(b.kind, b.lang, b.text) for b in blocks] == [
        ("code", "code", "\n".join(LAYOUT["code"])), ("code", "code", LAYOUT["mono"])]
    assert blocks[0].extra["lines_from"] == "pptx_text" and len(blocks[0].extra["merged_from"]) == 4


def test_a_footer_whose_words_change_is_dropped_by_its_place(extracted):
    found = extracted["slide_layout"]
    assert not any("footer" in b.text for b in found.blocks)
    assert sum(e.bucket == "skipped:repeated footer" for e in found.coverage) == 6       # one on every slide


def test_a_label_above_the_title_on_neighbouring_slides_joins_the_heading_path(extracted):
    found = extracted["slide_layout"]
    paths = {b.loc.slide: b.heading_path for b in found.blocks if b.kind == "heading"}
    sections = [LAYOUT["sections"][0]] * 2 + [LAYOUT["sections"][1]] * 2
    assert [paths[n] for n in range(1, 5)] == [[found.title, s, t] for s, t in zip(sections, LAYOUT["titles"])]
    assert [paths[n] for n in (5, 6)] == [[found.title, t] for t in LAYOUT["titles"][4:]]
    assert not any(b.text in LAYOUT["sections"] for b in found.blocks)                 # in the path, not the text


def test_numbers_that_came_back_count_as_extracted_and_lone_ones_do_not(extracted):
    cells = [e.bucket for e in extracted["slide_layout"].coverage if e.slide == 1 and e.tag == "sp (shape)"]
    assert cells == ["extracted"] * 6
    lone = [e for e in extracted["slide_layout"].coverage if e.slide == 5 and e.bucket == "skipped:no words"]
    assert len(lone) == 4                                           # the three numbers beside map nodes, a counter


def test_each_slide_is_one_chunk_in_reading_order(decks):
    from app.ingestion.chunking.registry import get_chunker

    path = decks["slide_layout"]
    meta = ResourceMeta(resource_id="r1", course_id="c1", file_name=path.name, file_sha256=_sha(path),
                        precheck=PrecheckResult(source_type="pptx"))
    chunks = get_chunker("pptx")(load(path, meta)).chunks
    assert [c.loc.slide for c in chunks] == [1, 2, 3, 4, 5, 6]
    assert chunks[0].text.split("\n\n") == [LAYOUT["row_label"], " ".join(LAYOUT["cells"]), LAYOUT["under"]]
    assert (chunks[3].kinds, chunks[3].heading_path[1]) == (["code"], LAYOUT["sections"][1])


# ================================================================ figure places, as the PDF loader writes them

def test_a_picture_gets_its_place_on_the_slide_as_fractions_from_the_top_left(extracted):
    [figure] = [b for b in extracted["picture_only"].blocks if b.kind == "figure"]
    place = figure.extra["figure"]
    assert place["page"] == 1 and place["box"][:3] == [0.1, 0.24, 0.6]           # 1, 1.8 and 6 inches of 10 x 7.5


def test_a_charts_table_carries_the_charts_place_too(extracted):
    figure, table = [b for b in extracted["chart"].blocks if b.kind in ("figure", "table")]
    assert table.extra["figure"] == figure.extra["figure"] and table.figure_id == figure.figure_id


# ================================================================ the rules on hand-made boxes

def _unit(name: str, left: float, top: float, right: float, bottom: float, index: int) -> layout.Unit:
    return layout.Unit((left, top, right, bottom), [name], index)


def _order(boxes: list[tuple]) -> list[str]:
    units = [_unit(*box, index=i) for i, box in enumerate(boxes)]
    return [unit.blocks[0] for unit in layout.xy_cut(units, (1000.0, 1000.0))]


def test_cards_read_column_by_column_when_columns_stand_farther_apart_than_their_rows():
    cards = [("A1", 0, 100, 250, 150), ("B1", 350, 100, 600, 150),
             ("A2", 0, 170, 250, 250), ("B2", 350, 170, 600, 250)]
    assert _order(cards) == ["A1", "A2", "B1", "B2"]


def test_a_list_of_labels_and_values_reads_row_by_row_when_rows_stand_farther_apart():
    rows = [(f"{name}{n}", left, 100 + 100 * n, right, 140 + 100 * n)
            for n in range(3) for name, left, right in (("L", 0, 300), ("V", 320, 900))]
    assert _order(rows) == ["L0", "V0", "L1", "V1", "L2", "V2"]


def test_a_full_width_title_and_sentence_keep_their_rows_around_the_columns():
    boxes = [("title", 0, 0, 1000, 80), ("left", 0, 120, 400, 300), ("right", 600, 120, 1000, 200),
             ("right2", 600, 220, 1000, 300), ("end", 0, 400, 1000, 450)]
    assert _order(boxes) == ["title", "left", "right", "right2", "end"]


@pytest.mark.parametrize(("lines", "monospace", "code"), [
    pytest.param(["def f(x):", "    if x:", "        return 1"], False, True, id="indented, code-like"),
    pytest.param(["First point", "    more words here", "    and more words"], False, False, id="indented prose"),
    pytest.param(["x = 1", "y = 2"], False, False, id="flat lines"),
    pytest.param(["print(total)"], True, True, id="one line in a fixed-width font"),
])
def test_what_counts_as_code(lines, monospace, code):
    assert layout.is_code(lines, monospace) is code


def test_code_text_keeps_relative_indent_and_one_empty_line_at_most():
    assert layout.code_text(["", "    a:", "        b", "", "", "    c", ""]) == "a:\n    b\n\nc"


def _cell(text: str, left: float, top: float, size: float = 50.0):
    return layout._Cell((left, top, left + size, top + size), text, text)


@pytest.mark.parametrize(("cells", "runs"), [
    pytest.param([_cell("1", 0, 0), _cell("2", 60, 0), _cell("3", 120, 0)], [["1", "2", "3"]], id="a row of three"),
    pytest.param([_cell("1", 0, 0), _cell("2", 60, 0)], [], id="a lone pair"),
    pytest.param([_cell("1", 0, 0), _cell("2", 60, 0), _cell("3", 0, 60), _cell("4", 60, 60)],
                 [["1", "2"], ["3", "4"]], id="stacked pairs: a board"),
    pytest.param([_cell(str(n), x, 0) for n, x in enumerate((0, 60, 120, 400, 460, 520))],
                 [["0", "1", "2"], ["3", "4", "5"]], id="two boards side by side"),
    pytest.param([_cell("7", 0, 0), _cell("9", 60, 30)], [], id="not in line"),
])
def test_which_numbers_form_rows_of_cells(cells, runs):
    assert [[c.text for c in run] for run in layout.cell_runs(cells)] == runs