"""chunk_sections(), split_to_fit(), merge_locations() and finish(), on hand-made blocks.

No Docling and no tokenizer: `words` counts one token per word, so every size in these tests is easy to read.
"""
from typing import Any

import pytest
from pydantic import ValidationError

from app.ingestion.chunking.base import Draft, finish, merge_locations
from app.ingestion.chunking.sections import by_slide, chunk_sections
from app.ingestion.chunking.split import split_to_fit
from app.ingestion.contract import (MAX_CHUNK_TOKENS, Block, Location, ParsedDocument, QualityReport, SourceType,
                                    Status)

T = "DSA notes"


def words(text: str) -> int:
    return len(text.split())


def _text(n: int, word: str = "node") -> str:
    return " ".join([word] * n)


def _doc(*specs: dict[str, Any], source_type: SourceType = "pdf", status: Status = "ok") -> ParsedDocument:
    """Blocks from short specs: kind, text, path (after the title) and page; seq is filled in."""
    blocks = [Block(seq=i, kind=s.get("kind", "paragraph"), text=s["text"], heading_path=[T, *s.get("path", [])],
                    loc=Location(**s.get("loc", {"page": 1}))) for i, s in enumerate(specs)]
    return ParsedDocument(resource_id="r1", course_id="c1", file_name="notes.pdf", file_sha256="0" * 64,
                          source_type=source_type, title=T, parser="test", parser_version="1",
                          blocks=[] if status == "failed" else blocks,
                          quality=QualityReport(status=status, warnings=["w"] if status == "failed" else [],
                                                units_total=1, chars_total=1))


def _chunk(doc: ParsedDocument, **options: Any) -> list[Draft]:
    return chunk_sections(doc, count=words, **options)


# ================================================================ sections and packing

def test_small_blocks_of_one_section_share_a_chunk_and_headings_add_no_text():
    drafts = _chunk(_doc(
        {"kind": "heading", "text": "Lists", "path": ["Lists"]},
        {"text": "A list keeps values in order.", "path": ["Lists"]},
        {"text": "Each value sits in a node.", "path": ["Lists"]},
    ))
    assert len(drafts) == 1
    assert drafts[0].text == "A list keeps values in order.\n\nEach value sits in a node."
    assert (drafts[0].heading_path, drafts[0].kinds, drafts[0].block_seqs) == ([T, "Lists"], ["paragraph"], [1, 2])


def test_a_new_section_always_starts_a_new_chunk():
    drafts = _chunk(_doc(
        {"kind": "heading", "text": "Stacks", "path": ["Stacks"]},
        {"text": "Last in, first out.", "path": ["Stacks"]},
        {"kind": "heading", "text": "Queues", "path": ["Queues"]},
        {"text": "First in, first out.", "path": ["Queues"]},
    ))
    assert [(d.heading_path[-1], d.text) for d in drafts] == [("Stacks", "Last in, first out."),
                                                              ("Queues", "First in, first out.")]


def test_two_sections_with_the_same_heading_stay_apart():
    drafts = _chunk(_doc(
        {"kind": "heading", "text": "Example", "path": ["Lists", "Example"]},
        {"text": "Insert 3 at the head.", "path": ["Lists", "Example"]},
        {"kind": "heading", "text": "Example", "path": ["Lists", "Example"]},
        {"text": "Delete the last node.", "path": ["Lists", "Example"]},
    ))
    assert [d.text for d in drafts] == ["Insert 3 at the head.", "Delete the last node."]


def test_a_section_with_only_headings_makes_no_chunk():
    drafts = _chunk(_doc(
        {"kind": "heading", "text": "Lists", "path": ["Lists"]},
        {"kind": "heading", "text": "Arrays", "path": ["Lists", "Arrays"]},
        {"text": "An array stores values side by side.", "path": ["Lists", "Arrays"]},
    ))
    assert [(d.heading_path, d.text) for d in drafts] == [
        ([T, "Lists", "Arrays"], "An array stores values side by side."),
    ]


def test_blocks_are_packed_up_to_the_target_and_a_block_that_does_not_fit_starts_the_next_chunk():
    drafts = _chunk(_doc(*[{"text": _text(100), "path": ["Lists"]} for _ in range(5)]))
    assert [d.block_seqs for d in drafts] == [[0, 1, 2], [3, 4]]
    assert all(words(d.text) <= 384 for d in drafts)


def test_a_block_between_the_target_and_the_limit_stays_whole():
    drafts = _chunk(_doc({"text": _text(450), "path": ["Lists"]}))
    assert [words(d.text) for d in drafts] == [450]


def test_a_small_last_chunk_joins_the_one_before_it_when_both_fit():
    joined = _chunk(_doc({"text": _text(400), "path": ["Lists"]}, {"text": _text(20), "path": ["Lists"]}))
    apart = _chunk(_doc({"text": _text(500), "path": ["Lists"]}, {"text": _text(20), "path": ["Lists"]}))
    assert [d.block_seqs for d in joined] == [[0, 1]]
    assert [d.block_seqs for d in apart] == [[0], [1]]              # 520 would pass the limit


def test_a_chunk_covers_the_pages_of_all_its_blocks():
    drafts = _chunk(_doc(
        {"text": "Starts here.", "path": ["Lists"], "loc": {"page": 4}},
        {"text": "Runs on.", "path": ["Lists"], "loc": {"page": 4, "page_end": 5}},
        {"text": "Ends here.", "path": ["Lists"], "loc": {"page": 5}},
    ))
    assert (drafts[0].loc.page, drafts[0].loc.page_end) == (4, 5)


def test_slides_can_be_the_sections():
    drafts = _chunk(_doc(
        {"kind": "heading", "text": "Stacks", "path": ["Stacks"], "loc": {"slide": 1}},
        {"kind": "list_item", "text": "- push", "path": ["Stacks"], "loc": {"slide": 1}},
        {"kind": "slide_notes", "text": "Mention the call stack.", "path": ["Stacks"], "loc": {"slide": 1}},
        {"kind": "list_item", "text": "- pop", "path": ["Stacks"], "loc": {"slide": 2}},
        source_type="pptx"), section_key=by_slide)
    assert [(d.loc.slide, d.kinds) for d in drafts] == [(1, ["list_item", "slide_notes"]), (2, ["list_item"])]


def test_a_failed_document_is_never_chunked():
    with pytest.raises(ValueError):
        _chunk(_doc({"text": "x"}, status="failed"))


# ================================================================ cutting a block that is too long

def test_a_long_paragraph_is_cut_between_sentences():
    sentences = [f"Sentence {i} explains one more step of the insertion." for i in range(70)]   # 630 words
    drafts = _chunk(_doc({"text": " ".join(sentences), "path": ["Lists"]}))
    assert len(drafts) > 1 and all(words(d.text) <= 384 for d in drafts)
    assert all(d.text.endswith(".") for d in drafts)               # no sentence was cut
    assert " ".join(d.text for d in drafts) == " ".join(sentences)  # nothing lost, nothing repeated
    assert all(d.block_seqs == [0] for d in drafts)


def test_a_long_code_block_is_cut_between_lines_and_keeps_its_indentation():
    lines = [f"    total = total + values[{i}] * weight;" for i in range(120)]                # 720 words
    drafts = _chunk(_doc({"kind": "code", "text": "\n".join(lines), "path": ["Loops"]}))
    assert len(drafts) > 1
    assert all(line in lines for d in drafts for line in d.text.split("\n"))
    assert "\n".join(d.text for d in drafts) == "\n".join(lines)


def test_a_long_table_is_cut_between_rows_and_every_piece_keeps_the_header():
    header = ["| Operation | Cost |", "|---|---|"]
    rows = [f"| insert value {i} at the head of the list | O(1) |" for i in range(80)]         # 960 words
    drafts = _chunk(_doc({"kind": "table", "text": "\n".join(header + rows), "path": ["Costs"]}))
    assert len(drafts) > 1
    assert all(d.text.split("\n")[:2] == header for d in drafts)
    assert [row for d in drafts for row in d.text.split("\n")[2:]] == rows


def test_one_word_longer_than_the_limit_is_cut_by_characters():
    pieces = split_to_fit("x" * 1000, "paragraph", 300, len)        # here a "token" is one character
    assert all(len(p) <= 300 for p in pieces) and "".join(pieces) == "x" * 1000


# ================================================================ locations and finish()

def test_merged_locations_take_the_first_start_and_the_last_end():
    lines = merge_locations([Location(line_start=3, line_end=5), Location(line_start=6, line_end=9)])
    times = merge_locations([Location(t_start=0.0, t_end=60.0), Location(t_start=60.0, t_end=125.5)])
    pages = merge_locations([Location(page=7), Location(page=7)])
    assert (lines.line_start, lines.line_end) == (3, 9)
    assert (times.t_start, times.t_end) == (0.0, 125.5)              # 0.0 is a real start, not "missing"
    assert (pages.page, pages.page_end) == (7, None)                 # one page: no range


def test_finish_numbers_the_chunks_and_counts_their_tokens():
    doc = _doc({"text": "x", "path": ["Lists"]})
    drafts = [Draft(text="A node holds a value.", heading_path=[T, "Lists"], loc=Location(page=1),
                    kinds=["paragraph"], block_seqs=[0]),
              Draft(text="The head is the first node.", heading_path=[T, "Lists"], loc=Location(page=2),
                    kinds=["paragraph"], block_seqs=[0])]
    chunked = finish(doc, drafts, "test/1", count=words)
    assert [(c.seq, c.chunk_id, c.token_count) for c in chunked.chunks] == [(0, "r1:0", 5), (1, "r1:1", 6)]
    assert (chunked.course_id, chunked.chunker) == ("c1", "test/1")


def test_finish_refuses_a_chunk_over_the_limit():
    doc = _doc({"text": "x", "path": ["Lists"]})
    too_long = Draft(text=_text(MAX_CHUNK_TOKENS + 1), heading_path=[T, "Lists"], loc=Location(page=1),
                     kinds=["paragraph"], block_seqs=[0])
    with pytest.raises(ValidationError):
        finish(doc, [too_long], "test/1", count=words)