from app.agents.answering import answer
from app.agents.ingestion import ingest_resource
from app.agents.retrieval import retrieve
from app.agents.types import Answer, Chunk, IngestResult


def test_ingest_resource_returns_ingest_result():
    result = ingest_resource("r1", "c1", "uploads/c1/r1_demo.pdf", "pdf")
    assert isinstance(result, IngestResult)
    assert result.status in ("ready", "failed")
    assert isinstance(result.chunk_count, int)


def test_retrieve_returns_chunks_for_the_given_course():
    chunks = retrieve("c1", "what is polymorphism?", k=5)
    assert isinstance(chunks, list)
    assert all(isinstance(c, Chunk) for c in chunks)
    assert all(c.course_id == "c1" for c in chunks)


def test_answer_returns_answer_with_citations_and_confidence():
    result = answer("c1", "what is polymorphism?")
    assert isinstance(result, Answer)
    assert isinstance(result.text, str) and result.text
    assert 0.0 <= result.confidence <= 1.0
    assert isinstance(result.citations, list)