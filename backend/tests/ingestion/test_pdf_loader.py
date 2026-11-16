"""The PDF loader: Docling's result (faked here, see conftest) becomes a ParsedDocument with page numbers."""
import pytest
from docling_core.types.doc import DoclingDocument

from app.ingestion import messages, registry
from app.ingestion.contract import PrecheckResult, ResourceMeta
from app.ingestion.converter import PARSER_VERSION, Conversion
from app.ingestion.dispatcher import ingest_file
from app.ingestion.loaders import pdf


def _meta(pages_total: int = 3, file_name: str = "dsa_notes.pdf", **precheck) -> ResourceMeta:
    return ResourceMeta(resource_id="r1", course_id="c1", file_name=file_name, file_sha256="a" * 64,
                        precheck=PrecheckResult(source_type="pdf", pages_total=pages_total, **precheck))


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


@pytest.mark.parametrize("file_name, title", [
    ("Pointers.pptx.pdf", "Pointers"),
    ("Linear Transformation -Autosaved-.pptx.pdf", "Linear Transformation"),
    ("Linear Transformation (Autosaved).pptx.pdf", "Linear Transformation"),
    ("BSEF23A018-Binary Analysis and Software Patching Assignment.docx.pdf",
     "BSEF23A018 Binary Analysis and Software Patching Assignment"),
    ("Pointers.pptx (1).pdf", "Pointers"),
    ("Lecture_9_Stack_applications(2).ppt.pdf", "Lecture 9 Stack applications"),
    ("DOC-20260308-WA0027..pdf", "DOC 20260308 WA0027"),
    ("DSA_Presentation_Final.pdf", "DSA Presentation"),                 # title_from_filename() as before
    ("Lecture 9.1 Stacks.pdf", "Lecture 9.1 Stacks"),                   # a dot that is no extension stays
    ("Autosaved.pptx.pdf", "Autosaved.pptx"),                           # nothing else in the name: as before
])
def test_a_pdf_s_title_leaves_out_the_name_of_the_file_it_was_made_from(file_name, title):
    assert pdf.pdf_title(file_name) == title


def test_the_pdf_loader_titles_a_pdf_of_slides_by_its_own_name(digital_pdf):
    assert pdf.load(digital_pdf, _meta(file_name="Pointers.pptx.pdf")).title == "Pointers"


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
    doc = pdf.load(digital_pdf, _meta(pages_total=10, garbage_pages=[2], scanned_pages=[3]))
    assert doc.quality.status == "degraded"
    assert doc.quality.warnings == [messages.PARTIAL, messages.hard_to_read([2]),
                                    messages.no_text_units("Pages", [3])]


def test_a_file_whose_pages_are_mostly_pictures_is_a_problem_the_teacher_sees(digital_pdf):
    """Slides made of screenshots (Linear Transformation: 6 of 7): accepted, but marked, so the teacher knows."""
    doc = pdf.load(digital_pdf, _meta(pages_total=7, scanned_pages=[1, 2, 3, 4, 5, 7]))
    assert doc.quality.status == "degraded"
    assert doc.quality.warnings == ["6 of 7 pages (1 to 5, 7) are pictures with no readable text, so questions "
                                    "about them can't be answered yet."]


def test_a_few_picture_pages_are_only_a_note(digital_pdf):
    doc = pdf.load(digital_pdf, _meta(pages_total=10, scanned_pages=[1, 2]))       # 2 in 10: at the limit
    assert doc.quality.status == "ok"
    assert doc.quality.warnings == [messages.no_text_units("Pages", [1, 2])]


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