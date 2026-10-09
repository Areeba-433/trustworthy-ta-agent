import pytest

from app.ingestion import messages, registry
from app.ingestion.dispatcher import ingest_file


def test_a_file_goes_all_the_way_through(scanned_pdf, data_dir):
    doc = ingest_file(scanned_pdf, "r1", "c1")
    assert doc.source_type == "scanned_pdf"
    assert doc.quality.status == "ok"
    assert (data_dir / "r1" / "parsed.json").exists()


def test_a_broken_file_fails_politely(tmp_path, data_dir):
    bad = tmp_path / "broken.pdf"
    bad.write_bytes(b"this is not a pdf")
    doc = ingest_file(bad, "r2", "c1")
    assert doc.quality.status == "failed"
    assert doc.quality.warnings == [messages.TYPE_MISMATCH]


def test_a_crashing_department_becomes_a_failed_document(scanned_pdf, data_dir, monkeypatch):
    registry.registered()                                   # sign up the real departments first

    def crash(path, meta):
        raise RuntimeError("bug inside a loader")

    monkeypatch.setitem(registry._LOADERS, "scanned_pdf", crash)
    doc = ingest_file(scanned_pdf, "r3", "c1")
    assert doc.quality.status == "failed"
    assert doc.quality.warnings == [messages.INTERNAL]


def test_unsafe_resource_id_is_refused(scanned_pdf, data_dir):
    with pytest.raises(ValueError):
        ingest_file(scanned_pdf, "../outside", "c1")