"""scripts/ingest_check.py: the report, the citations and the exit codes. count_tokens() counts words here."""
from pathlib import Path
from typing import Any

import pytest

from app.ingestion.chunking.base import finish
from app.ingestion.chunking.sections import chunk_sections
from app.ingestion.contract import Block, Chunk, ChunkedDocument, Location, ParsedDocument, QualityReport
from scripts import ingest_check


def _chunk(**loc: Any) -> Chunk:
    return Chunk(seq=0, chunk_id="r:0", text="A stack is last in, first out.", heading_path=["T", "Stacks", "Push"],
                 loc=Location(**loc), kinds=["paragraph"], block_seqs=[0], token_count=7)


@pytest.mark.parametrize("loc, expected", [
    ({"page": 4}, "p. 4"),
    ({"page": 4, "page_end": 5}, "pp. 4–5"),
    ({"slide": 3}, "slide 3"),
    ({"t_start": 760.0, "t_end": 845.5}, "12:40–14:05"),
    ({"t_start": 3700.0, "t_end": 3790.0}, "1:01:40–1:03:10"),
    ({"line_start": 10, "line_end": 24}, "lines 10–24"),
    ({"line_start": 7}, "line 7"),
    ({}, "Stacks > Push"),
], ids=["page", "pages", "slide", "minutes", "hours", "lines", "one-line", "docx"])
def test_citations_read_the_way_an_answer_would_cite_them(loc, expected):
    assert ingest_check.citation(_chunk(**loc)) == expected


def test_resource_ids_are_safe_folder_names():
    assert ingest_check.resource_id_for(Path("Data Structures (3rd ed).pdf")) == "check_Data-Structures-3rd-ed-"


def test_a_good_file_is_reported_and_previewed(digital_pdf, data_dir, word_tokens):
    assert ingest_check.main([str(digital_pdf)]) == 0
    folder = data_dir / "check_digital"
    assert (folder / "chunks.json").exists()
    assert (folder / "preview.md").read_text(encoding="utf-8").startswith("# digital.pdf: 1 chunk (pdf-sections/1)")


def test_a_refused_file_exits_with_1_and_has_no_preview(scanned_pdf, data_dir):
    assert ingest_check.main([str(scanned_pdf)]) == 1
    assert not (data_dir / "check_scanned" / "preview.md").exists()


def test_an_unsupported_file_type_is_a_usage_error(tmp_path, data_dir):
    sheet = tmp_path / "marks.xlsx"
    sheet.write_bytes(b"PK")
    with pytest.raises(SystemExit) as exit_info:
        ingest_check.main([str(sheet)])
    assert exit_info.value.code == 2                            # argparse's code for "used the wrong way"


# --- the figures line: the image check after every change ---------------------------------------

def _words(text: str) -> int:
    return len(text.split())


def _parsed(*figure_ids: str | None) -> ParsedDocument:
    blocks = [Block(seq=i, kind="figure" if name and i % 2 else "caption" if name else "paragraph",
                    text="[Figure]" if name and i % 2 else f"FIGURE 1.{i} A list", heading_path=["T"],
                    loc=Location(page=i + 1), figure_id=name) for i, name in enumerate(figure_ids)]
    return ParsedDocument(resource_id="r", course_id="c", file_name="a.pdf", file_sha256="0" * 64,
                          source_type="pdf", title="T", parser="p", parser_version="1", blocks=blocks,
                          quality=QualityReport(status="ok", units_total=len(blocks), chars_total=40))


def test_the_figures_line_counts_figures_and_placeholders_and_finds_none_lost():
    doc = _parsed("fig0", "fig1")                        # a caption of fig0, then fig1 as [Figure]
    chunked = finish(doc, chunk_sections(doc, count=_words), "test/1", count=_words)
    assert ingest_check.figures_line(doc, chunked) == "figures: 2 (1 shown as [Figure]), 2 in chunks, 0 lost"


def test_the_figures_line_names_a_figure_that_never_reached_a_chunk():
    doc = _parsed("fig0", "fig1")
    chunked = ChunkedDocument(resource_id="r", course_id="c", source_type="pdf", title="T", chunker="test/1",
                              chunks=[_chunk(page=1).model_copy(update={"figure_ids": ["r:fig0"]})])
    assert ingest_check.figures_line(doc, chunked) == "figures: 2 (1 shown as [Figure]), 1 in chunks, 1 lost (fig1)"


def test_the_figures_line_says_none_for_a_file_without_pictures():
    assert ingest_check.figures_line(_parsed(None), None) == "figures: none"
