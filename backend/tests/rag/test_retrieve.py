"""search() with the fake embedder from test_store: no model needed."""
import pytest

from app.ingestion.contract import embedding_text
from app.rag.retrieve import citation_for, search
from app.rag.store import get_client, index_chunks
from tests.rag.test_store import _doc, fake_embed


@pytest.fixture
def client(tmp_path):
    return get_client(str(tmp_path / "chroma"))


def test_a_question_with_a_chunks_exact_words_finds_that_chunk_first(client):
    doc = _doc()
    index_chunks(doc, fake_embed, client)
    hits = search("c1", embedding_text(doc.chunks[1]), embed=fake_embed, client=client)
    assert hits[0].chunk_id == "r1:1" and hits[0].distance < 1e-6
    assert hits[0].figure_ids == ["r1:fig0"] and hits[0].citation == "Notes > Part 1"


def test_results_come_only_from_the_asked_course(client):
    index_chunks(_doc(course_id="c1"), fake_embed, client)
    index_chunks(_doc(resource_id="r2", course_id="c2"), fake_embed, client)
    hits = search("c2", "anything", embed=fake_embed, client=client)
    assert {h.chunk_id for h in hits} == {"r2:0", "r2:1"}


def test_at_most_k_results_and_none_for_an_empty_course_or_question(client):
    index_chunks(_doc(texts=tuple(f"Chunk {i}." for i in range(8)), figures=(None,) * 8), fake_embed, client)
    assert len(search("c1", "chunk", k=5, embed=fake_embed, client=client)) == 5
    assert search("empty_course", "chunk", embed=fake_embed, client=client) == []
    assert search("c1", "   ", embed=fake_embed, client=client) == []


def test_citations_name_the_page_slide_lines_or_heading():
    assert citation_for({"page": 47}) == "p. 47"
    assert citation_for({"page": 47, "page_end": 48}) == "p. 47-48"
    assert citation_for({"slide": 12}) == "slide 12"
    assert citation_for({"line_start": 10, "line_end": 25}) == "lines 10-25"
    assert citation_for({"heading": "Notes > Level 1"}) == "Notes > Level 1"
