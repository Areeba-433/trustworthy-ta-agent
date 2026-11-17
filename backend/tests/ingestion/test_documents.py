"""parsed_document() and failed_document(): the one place loaders build their answer."""
import pytest

from app.ingestion import messages
from app.ingestion.contract import Block, Location, PrecheckResult, ResourceMeta
from app.ingestion.documents import document_title, failed_document, parsed_document, picture_findings

TITLE = "DSA notes"


def _meta(source_type="pdf") -> ResourceMeta:
    return ResourceMeta(resource_id="r1", course_id="c1", file_name="dsa_notes.pdf", file_sha256="a" * 64,
                        precheck=PrecheckResult(source_type=source_type, pages_total=3))


def _block(seq: int, text: str, page: int = 1) -> Block:
    return Block(seq=seq, kind="paragraph", text=text, heading_path=[TITLE], loc=Location(page=page))


def _build(blocks, **kwargs):
    return parsed_document(_meta(), title=TITLE, blocks=blocks, parser="test", parser_version="1",
                           units_total=3, **kwargs)


def test_a_clean_result_is_ok_and_counts_its_characters():
    doc = _build([_block(0, "abc"), _block(1, "defg", page=2)])
    assert doc.quality.status == "ok"
    assert doc.quality.warnings == []
    assert (doc.quality.chars_total, doc.quality.units_total) == (7, 3)
    assert (doc.resource_id, doc.source_type, doc.parser) == ("r1", "pdf", "test")


def test_blocks_are_numbered_again_after_a_rule_drops_some():
    doc = _build([_block(0, "kept"), _block(5, "also kept")])         # blocks 1 to 4 were removed
    assert [b.seq for b in doc.blocks] == [0, 1]


def test_a_problem_lowers_the_status_and_a_note_does_not():
    assert _build([_block(0, "x")], problems=[messages.PARTIAL]).quality.status == "degraded"
    assert _build([_block(0, "x")], notes=["A long file."]).quality.status == "ok"


def test_problems_come_first_and_repeats_are_dropped():
    doc = _build([_block(0, "x")], problems=[messages.PARTIAL, messages.PARTIAL], notes=["A note."])
    assert doc.quality.warnings == [messages.PARTIAL, "A note."]


def test_no_blocks_means_the_file_had_no_readable_text():
    doc = _build([], problems=[messages.PARTIAL])
    assert doc.quality.status == "failed"
    assert doc.quality.warnings == [messages.NO_TEXT_FILE]
    assert doc.blocks == []


def test_one_message_instead_of_a_list_is_refused():
    with pytest.raises(TypeError):
        _build([_block(0, "x")], problems=messages.PARTIAL)          # would split into single letters


def test_a_failed_document_carries_the_reason_and_a_title_from_the_file_name():
    doc = failed_document(_meta(), "pdf", messages.UNREADABLE)
    assert doc.quality.status == "failed"
    assert doc.quality.warnings == [messages.UNREADABLE]
    assert doc.title and doc.blocks == []

@pytest.mark.parametrize("file_name, source_type, title", [
    ("stack.cpp", "code", "stack.cpp"), ("stack.h", "code", "stack.h"),       # .cpp and .h stay apart
    ("notes.md", "text", "notes.md"), ("readme.txt", "text", "readme.txt"),
    ("Lecture 5.pptx.pdf", "pdf", "Lecture 5"), ("Vectors (Autosaved).pptx", "pptx", "Vectors"),
    ("L4_normalization_final.docx", "docx", "L4 normalization"),
])
def test_a_document_s_title_depends_on_its_format(file_name, source_type, title):
    assert document_title(file_name, source_type) == title


def test_a_failed_file_has_the_title_it_would_have_had():
    meta = ResourceMeta(resource_id="r1", course_id="c1", file_name="empty.cpp", file_sha256="a" * 64,
                        precheck=PrecheckResult(source_type="code", pages_total=1))
    assert failed_document(meta, "code", messages.NO_TEXT_FILE).title == "empty.cpp"
    assert failed_document(_meta(), "pdf", messages.NO_TEXT_FILE).title == "dsa notes"


def test_a_few_picture_pages_are_a_note_and_more_than_one_in_five_a_problem():
    assert picture_findings("Slides", [], 20) == ([], [])
    assert picture_findings("Slides", [4, 4], 20) == ([], [messages.no_text_units("Slides", [4])])
    problems, notes = picture_findings("Slides", [1, 2, 3, 4, 5], 20)                    # 5 of 20: one in four
    assert (problems, notes) == ([messages.mostly_pictures("Slides", [1, 2, 3, 4, 5], 20)], [])
    assert picture_findings("Pages", [1, 2, 3, 4], 20)[0] == []                           # 4 of 20: exactly 1 in 5
