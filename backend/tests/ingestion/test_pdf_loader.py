"""The PDF loader: Docling's result (faked here, see conftest) becomes a ParsedDocument with page numbers."""
from docling_core.types.doc import DoclingDocument

from app.ingestion import messages, registry
from app.ingestion.contract import PrecheckResult, ResourceMeta
from app.ingestion.converter import PARSER_VERSION, Conversion
from app.ingestion.dispatcher import ingest_file
from app.ingestion.loaders import pdf


def _meta(**precheck) -> ResourceMeta:
    return ResourceMeta(resource_id="r1", course_id="c1", file_name="dsa_notes.pdf", file_sha256="a" * 64,
                        precheck=PrecheckResult(source_type="pdf", pages_total=3, **precheck))


def test_the_pdf_loader_is_the_one_registered_for_pdf():
    assert registry.get_loader("pdf") is pdf.load


def test_a_book_becomes_blocks_with_page_numbers(digital_pdf, data_dir):
    doc = ingest_file(digital_pdf, "r1", "c1")
    assert doc.quality.status == "ok"
    assert [(b.kind, b.loc.page) for b in doc.blocks] == [("paragraph", 1), ("paragraph", 2), ("paragraph", 3)]
    assert doc.blocks[0].text.startswith("Page 1: a linked list")
    assert (doc.title, doc.parser, doc.parser_version) == ("digital", "docling", PARSER_VERSION)
    assert doc.quality.units_total == 3
    assert {"docling", "blocks"} <= set(doc.quality.seconds_taken)


def test_a_picture_cover_is_a_note_and_the_status_stays_ok(make_pdf, data_dir):
    doc = ingest_file(make_pdf(scanned=1, text=4), "r2", "c1")
    assert doc.quality.status == "ok"
    assert doc.quality.warnings == [messages.no_text_units("Pages", [1])]
    assert [b.loc.page for b in doc.blocks] == [2, 3, 4, 5]


def test_garbled_pages_are_a_problem_and_lower_the_status(digital_pdf):
    doc = pdf.load(digital_pdf, _meta(garbage_pages=[2]))
    assert doc.quality.status == "degraded"
    assert doc.quality.warnings == [messages.hard_to_read([2])]


def test_docling_problems_come_first(digital_pdf, monkeypatch, fake_docling_pdf):
    def partial(path, source_type, file_sha256=None):
        return Conversion(fake_docling_pdf(path, source_type).document, (messages.PARTIAL,))

    monkeypatch.setattr(pdf, "convert", partial)
    doc = pdf.load(digital_pdf, _meta(garbage_pages=[2], scanned_pages=[3]))
    assert doc.quality.status == "degraded"
    assert doc.quality.warnings == [messages.PARTIAL, messages.hard_to_read([2]),
                                    messages.no_text_units("Pages", [3])]


def test_a_cached_result_is_timed_under_its_own_name(digital_pdf, monkeypatch, fake_docling_pdf):
    def cached(path, source_type, file_sha256=None):
        return Conversion(fake_docling_pdf(path, source_type).document, from_cache=True)

    monkeypatch.setattr(pdf, "convert", cached)
    seconds = pdf.load(digital_pdf, _meta()).quality.seconds_taken
    assert "docling_cache" in seconds and "docling" not in seconds


def test_the_file_hash_is_passed_on_so_the_cache_can_work(digital_pdf, monkeypatch, fake_docling_pdf):
    seen = {}

    def spy(path, source_type, file_sha256=None):
        seen.update(source_type=source_type, file_sha256=file_sha256)
        return fake_docling_pdf(path, source_type)

    monkeypatch.setattr(pdf, "convert", spy)
    pdf.load(digital_pdf, _meta())
    assert seen == {"source_type": "pdf", "file_sha256": "a" * 64}


def test_a_book_with_no_text_at_all_fails_with_the_no_text_message(digital_pdf, monkeypatch):
    def empty(path, source_type, file_sha256=None):
        return Conversion(DoclingDocument(name="empty"))

    monkeypatch.setattr(pdf, "convert", empty)
    doc = pdf.load(digital_pdf, _meta())
    assert (doc.quality.status, doc.quality.warnings) == ("failed", [messages.NO_TEXT_FILE])