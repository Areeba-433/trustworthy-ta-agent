import pytest

from app.ingestion import dispatcher, messages, registry
from app.ingestion.dispatcher import ingest_file
from app.ingestion.documents import FileRefused


def test_a_file_goes_all_the_way_through(digital_pdf, data_dir):
    doc = ingest_file(digital_pdf, "r1", "c1")
    assert doc.source_type == "pdf"
    assert doc.quality.status == "ok"
    assert (data_dir / "r1" / "parsed.json").exists()


def test_a_broken_file_fails_politely(tmp_path, data_dir):
    bad = tmp_path / "broken.pdf"
    bad.write_bytes(b"this is not a pdf")
    doc = ingest_file(bad, "r2", "c1")
    assert doc.quality.status == "failed"
    assert doc.quality.warnings == [messages.TYPE_MISMATCH]


def test_a_scanned_pdf_fails_with_the_scan_message(scanned_pdf, data_dir):
    doc = ingest_file(scanned_pdf, "r4", "c1")
    assert doc.quality.status == "failed"
    assert doc.quality.warnings == [messages.SCANNED_PDF]


def test_a_crashing_department_becomes_a_failed_document(digital_pdf, data_dir, monkeypatch):
    registry.registered()                                   # sign up the real departments first

    def crash(path, meta):
        raise RuntimeError("bug inside a loader")

    monkeypatch.setitem(registry._LOADERS, "pdf", crash)
    doc = ingest_file(digital_pdf, "r3", "c1")
    assert doc.quality.status == "failed"
    assert doc.quality.warnings == [messages.INTERNAL]


def test_a_refused_file_fails_with_the_loaders_own_message(digital_pdf, data_dir, monkeypatch):
    registry.registered()

    def refuse(path, meta):
        raise FileRefused(messages.UNREADABLE)

    monkeypatch.setitem(registry._LOADERS, "pdf", refuse)
    doc = ingest_file(digital_pdf, "r7", "c1")
    assert doc.quality.status == "failed"
    assert doc.quality.warnings == [messages.UNREADABLE]


def test_unsafe_resource_id_is_refused(digital_pdf, data_dir):
    with pytest.raises(ValueError):
        ingest_file(digital_pdf, "../outside", "c1")


class _SlotSpy:
    """Stands in for the heavy slot and counts how many files took it."""
    def __init__(self) -> None:
        self.taken = 0

    def __enter__(self) -> None:
        self.taken += 1

    def __exit__(self, *exc: object) -> bool:
        return False                                         # never hide an exception


def test_a_docling_file_takes_the_heavy_slot(digital_pdf, data_dir, monkeypatch):
    spy = _SlotSpy()
    monkeypatch.setattr(dispatcher, "_heavy_slot", spy)
    ingest_file(digital_pdf, "r5", "c1")
    assert spy.taken == 1


def test_a_light_file_does_not_wait_for_the_heavy_slot(tmp_path, data_dir, monkeypatch):
    spy = _SlotSpy()
    monkeypatch.setattr(dispatcher, "_heavy_slot", spy)
    source = tmp_path / "hello.cpp"
    source.write_text("int main() { return 0; }")
    ingest_file(source, "r6", "c1")
    assert spy.taken == 0

def test_only_the_docling_formats_are_heavy():
    heavy = {st for st in registry.registered() if registry.is_heavy(st)}
    assert heavy == {"pdf", "docx", "pptx"}