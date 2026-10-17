from typing import Any, get_args

import pytest
from pydantic import ValidationError

from app.ingestion.contract import (MAX_CHUNK_TOKENS, Block, Chunk, ChunkedDocument, Location,
                                    ParsedDocument, QualityReport, SourceType, embedding_text)
from app.ingestion.registry import registered


def _valid(**changes: Any) -> dict[str, Any]:
    data: dict[str, Any] = dict(resource_id="r", course_id="c", file_name="a.pdf", file_sha256="0" * 64,
                source_type="pdf", title="T", parser="p", parser_version="1",
                blocks=[Block(seq=0, kind="paragraph", text="x", heading_path=["T"], loc=Location(page=1))],
                quality=QualityReport(status="ok", units_total=1, chars_total=1))
    return data | changes


def test_a_valid_document_is_accepted():
    ParsedDocument(**_valid())


@pytest.mark.parametrize("changes", [
    {"blocks": [Block(seq=1, kind="paragraph", text="x", heading_path=["T"], loc=Location(page=1))]},
    {"blocks": [Block(seq=0, kind="paragraph", text="x", heading_path=["Other"], loc=Location(page=1))]},
    {"blocks": [Block(seq=0, kind="paragraph", text="x", heading_path=["T"], loc=Location())]},
    {"quality": QualityReport(status="failed", warnings=["w"], units_total=0, chars_total=0)},
    {"blocks": []},
], ids=["seq-gap", "path-without-title", "pdf-without-page", "failed-with-blocks", "ok-without-blocks"])
def test_broken_rules_are_rejected(changes):
    with pytest.raises(ValidationError):
        ParsedDocument(**_valid(**changes))


def test_every_file_type_has_exactly_one_department():
    assert set(get_args(SourceType)) == set(registered())


@pytest.mark.parametrize("kind", ["figure_text", "formula"])
def test_the_new_block_kinds_are_accepted(kind):
    Block(seq=0, kind=kind, text="head -> node", heading_path=["T"], loc=Location(page=1))


def test_a_section_running_onto_the_next_page_is_accepted():
    Location(page=4, page_end=5)


@pytest.mark.parametrize("fields", [{"page": 5, "page_end": 4}, {"page_end": 2}],
                         ids=["end-before-start", "end-without-start"])
def test_a_broken_page_range_is_rejected(fields):
    with pytest.raises(ValidationError):
        Location(**fields)


# --- chunks ---------------------------------------------------------------------------------

def _chunk(seq: int = 0, **changes: Any) -> Chunk:
    data: dict[str, Any] = dict(seq=seq, chunk_id=f"r:{seq}", text="A stack is last in, first out.",
                                heading_path=["T", "Stacks"], loc=Location(page=3),
                                kinds=["paragraph"], block_seqs=[seq], token_count=9)
    return Chunk(**(data | changes))


def _valid_chunked(**changes: Any) -> dict[str, Any]:
    data: dict[str, Any] = dict(resource_id="r", course_id="c", source_type="pdf", title="T",
                                chunker="test/1", chunks=[_chunk(0), _chunk(1)])
    return data | changes


def test_a_valid_chunked_document_is_accepted():
    ChunkedDocument(**_valid_chunked())


@pytest.mark.parametrize("changes", [
    {"chunks": [_chunk(0), _chunk(2)]},
    {"chunks": [_chunk(0, chunk_id="other:0")]},
    {"chunks": [_chunk(0, heading_path=["Other"])]},
    {"chunks": [_chunk(0, loc=Location())]},
    {"chunks": []},
], ids=["seq-gap", "wrong-chunk-id", "path-without-title", "pdf-without-page", "no-chunks"])
def test_broken_chunk_rules_are_rejected(changes):
    with pytest.raises(ValidationError):
        ChunkedDocument(**_valid_chunked(**changes))


def test_a_chunk_may_reach_the_token_limit_but_not_pass_it():
    _chunk(token_count=MAX_CHUNK_TOKENS)
    with pytest.raises(ValidationError):
        _chunk(token_count=MAX_CHUNK_TOKENS + 1)


def test_docx_chunks_cite_their_heading_path_not_a_page():
    ChunkedDocument(**_valid_chunked(source_type="docx", chunks=[_chunk(0, loc=Location())]))


def test_embedding_text_starts_with_the_heading_path():
    assert embedding_text(_chunk(0)) == "T > Stacks\nA stack is last in, first out."