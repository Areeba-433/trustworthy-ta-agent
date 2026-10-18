"""process(): file -> parsed.json -> chunks.json.
The PDF loader is still a stub here, and count_tokens() counts words (word_tokens)."""
from app.ingestion import messages
from app.ingestion.chunking import registry as chunker_registry
from app.ingestion.contract import ChunkedDocument
from app.ingestion.pipeline import process


def test_a_file_goes_all_the_way_to_chunks_json(digital_pdf, data_dir, word_tokens):
    result = process(digital_pdf, "r1", "c1")
    saved = ChunkedDocument.model_validate_json((data_dir / "r1" / "chunks.json").read_text(encoding="utf-8"))
    assert (result.status, result.warnings) == ("ok", [])
    assert saved == result.chunked
    assert saved.chunker == "pdf-sections/1" and saved.chunks[0].chunk_id == "r1:0"
    assert (data_dir / "r1" / "parsed.json").exists()


def test_a_refused_file_gets_no_chunks(scanned_pdf, data_dir):
    result = process(scanned_pdf, "r2", "c1")
    assert (result.status, result.warnings, result.chunked) == ("failed", [messages.SCANNED_PDF], None)
    assert not (data_dir / "r2" / "chunks.json").exists()


def test_a_failed_reupload_removes_the_old_chunks(digital_pdf, scanned_pdf, data_dir, word_tokens):
    process(digital_pdf, "r3", "c1")
    assert (data_dir / "r3" / "chunks.json").exists()
    process(scanned_pdf, "r3", "c1")                           # same resource, now a file we refuse
    assert not (data_dir / "r3" / "chunks.json").exists()       # no stale chunks for the retriever to find


def test_a_crashing_chunker_becomes_a_failed_result_and_old_chunks_go(digital_pdf, data_dir, monkeypatch,
                                                                        word_tokens):
    process(digital_pdf, "r4", "c1")                            # a good first run leaves chunks.json behind

    def crash(doc):
        raise RuntimeError("bug inside a chunker")

    monkeypatch.setitem(chunker_registry._CHUNKERS, "pdf", crash)
    result = process(digital_pdf, "r4", "c1")
    assert (result.status, result.warnings, result.chunked) == ("failed", [messages.INTERNAL], None)
    assert (data_dir / "r4" / "parsed.json").exists()           # kept, to look into the bug
    assert not (data_dir / "r4" / "chunks.json").exists()


def test_chunks_changed_after_they_were_made_are_checked_again(digital_pdf, data_dir, monkeypatch, word_tokens):
    real = chunker_registry.get_chunker("pdf")

    def sloppy(doc):
        chunked = real(doc)
        chunked.chunks[0].token_count = 9999                    # Pydantic does not re-check plain assignments
        return chunked

    monkeypatch.setitem(chunker_registry._CHUNKERS, "pdf", sloppy)
    assert process(digital_pdf, "r6", "c1").status == "failed"


def test_processing_the_same_file_twice_gives_the_same_chunks(digital_pdf, data_dir, word_tokens):
    process(digital_pdf, "r5", "c1")
    first = (data_dir / "r5" / "chunks.json").read_bytes()
    process(digital_pdf, "r5", "c1")
    assert (data_dir / "r5" / "chunks.json").read_bytes() == first