"""The chunker registry and the six chunkers, one per file type. count_tokens() counts words here (word_tokens)."""
from typing import Any, get_args

import pytest

from app.ingestion.chunking import registry
from app.ingestion.contract import Block, Location, ParsedDocument, QualityReport, SourceType

T = "DSA notes"
_FIRST_LOCATION: dict[str, dict[str, Any]] = {
    "pdf": {"page": 1}, "docx": {}, "pptx": {"slide": 1}, "audio": {"t_start": 0.0, "t_end": 75.0},
    "code": {"line_start": 1, "line_end": 3}, "text": {"line_start": 1, "line_end": 2},
}
_FIRST_KIND = {"audio": "transcript", "code": "code"}


def _doc(source_type: SourceType, *specs: tuple[str, str, list[str], dict[str, Any]]) -> ParsedDocument:
    """Blocks from (kind, text, path after the title, location) tuples; seq is filled in."""
    blocks = [Block(seq=i, kind=kind, text=text, heading_path=[T, *path], loc=Location(**loc))
              for i, (kind, text, path, loc) in enumerate(specs)]
    return ParsedDocument(resource_id="r1", course_id="c1", file_name="notes", file_sha256="0" * 64,
                          source_type=source_type, title=T, parser="test", parser_version="1", blocks=blocks,
                          quality=QualityReport(status="ok", units_total=1, chars_total=1))


def test_every_file_type_has_exactly_one_chunker():
    assert set(get_args(SourceType)) == set(registry.registered_chunkers())


def test_two_chunkers_cannot_claim_the_same_file_type(monkeypatch):
    monkeypatch.setattr(registry, "_CHUNKERS", {})               # an empty registry, just for this test
    registry.register_chunker("pdf")(lambda doc: doc)
    with pytest.raises(RuntimeError, match="two chunkers claim 'pdf'"):
        registry.register_chunker("pdf")(lambda doc: doc)


def test_an_unknown_file_type_has_no_chunker():
    with pytest.raises(LookupError):
        registry.get_chunker("xlsx")


@pytest.mark.parametrize("source_type", list(get_args(SourceType)))
def test_each_chunker_turns_a_parsed_document_into_valid_chunks(source_type, word_tokens):
    doc = _doc(source_type, (_FIRST_KIND.get(source_type, "paragraph"), "A stack is last in, first out.",
                             ["Stacks"], _FIRST_LOCATION[source_type]))
    chunked = registry.get_chunker(source_type)(doc)
    assert [(c.chunk_id, c.text, c.token_count) for c in chunked.chunks] == [
        ("r1:0", "A stack is last in, first out.", 7)]
    assert chunked.chunker.startswith(f"{source_type}-")           # e.g. "pdf-sections/1"


def test_slides_never_share_a_chunk(word_tokens):
    doc = _doc("pptx",
               ("heading", "Stacks", ["Stacks"], {"slide": 1}),
               ("list_item", "- push adds on top", ["Stacks"], {"slide": 1}),
               ("list_item", "- pop takes from the top", ["Stacks"], {"slide": 2}))    # a slide without a title
    chunked = registry.get_chunker("pptx")(doc)
    assert [(c.loc.slide, c.text) for c in chunked.chunks] == [(1, "- push adds on top"),
                                                               (2, "- pop takes from the top")]


def test_transcript_windows_never_merge(word_tokens):
    doc = _doc("audio",
               ("transcript", "Today we start with stacks.", [], {"t_start": 0.0, "t_end": 62.5}),
               ("transcript", "A stack is last in, first out.", [], {"t_start": 62.5, "t_end": 130.0}))
    chunked = registry.get_chunker("audio")(doc)
    assert [(c.loc.t_start, c.loc.t_end) for c in chunked.chunks] == [(0.0, 62.5), (62.5, 130.0)]