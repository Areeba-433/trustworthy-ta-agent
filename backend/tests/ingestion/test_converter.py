"""converter.py: one Docling converter per format, our PDF settings, and Docling's status in our words.

Part 1 needs no files and no AI models. Part 2 runs real Docling on Word and PowerPoint files made here (seconds).
Part 3 runs Docling's PDF models, which download the first time, so it runs only when asked.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from docling.datamodel.base_models import ConversionStatus, DoclingComponentType, ErrorItem
from docling.datamodel.pipeline_options import TableFormerMode
from docling_core.types.doc import DoclingDocument

from app.ingestion import converter, messages
from app.ingestion.documents import FileRefused
from app.ingestion.storage import file_sha256


# ================================================================ part 1: settings and status, no models

def test_pdf_settings_match_the_plan():
    options = converter.pdf_options()
    assert options.do_ocr is False
    assert options.do_table_structure and options.table_structure_options.mode == TableFormerMode.FAST
    assert options.heading_hierarchy_options.enabled
    assert not (options.do_code_enrichment or options.do_formula_enrichment)
    assert not (options.generate_page_images or options.generate_picture_images)
    assert options.document_timeout == converter.PDF_TIMEOUT_SECONDS


def test_each_format_gets_one_converter_that_is_kept():
    assert converter.get_converter("docx") is converter.get_converter("docx")
    assert converter.get_converter("docx") is not converter.get_converter("pptx")


def test_formats_docling_does_not_read_are_refused():
    with pytest.raises(ValueError):
        converter.get_converter("audio")


def _fake_docling(monkeypatch, status, *components):
    """Replace the real converter with one that returns `status`, with one error per component given."""
    errors = [ErrorItem(component_type=c, module_name="test", error_message="boom") for c in components]
    result = SimpleNamespace(status=status, document=DoclingDocument(name="t"), errors=errors)
    fake = SimpleNamespace(convert=lambda path, raises_on_error: result)
    monkeypatch.setattr(converter, "get_converter", lambda source_type: fake)
    return result


def test_a_full_success_has_no_problems(monkeypatch):
    result = _fake_docling(monkeypatch, ConversionStatus.SUCCESS)
    conversion = converter.convert(Path("book.pdf"), "pdf")
    assert conversion.document is result.document
    assert conversion.problems == ()


def test_a_partial_result_is_kept_with_the_partial_warning(monkeypatch):
    _fake_docling(monkeypatch, ConversionStatus.PARTIAL_SUCCESS, DoclingComponentType.PIPELINE)
    assert converter.convert(Path("book.pdf"), "pdf").problems == (messages.PARTIAL,)


def test_a_broken_file_is_refused_as_unreadable(monkeypatch):
    _fake_docling(monkeypatch, ConversionStatus.FAILURE, DoclingComponentType.USER_INPUT)
    with pytest.raises(FileRefused) as refused:
        converter.convert(Path("book.pdf"), "pdf")
    assert refused.value.reason == messages.UNREADABLE


def test_a_crash_inside_docling_is_our_bug_not_the_teachers(monkeypatch):
    _fake_docling(monkeypatch, ConversionStatus.FAILURE, DoclingComponentType.PIPELINE)
    with pytest.raises(RuntimeError):
        converter.convert(Path("book.pdf"), "pdf")


# ================================================================ part 2: real Docling on Word and PowerPoint files

def _word_file(path: Path) -> Path:
    from docx import Document

    d = Document()
    d.add_heading("Stacks", level=1)
    d.add_paragraph("Last in, first out.")
    d.save(path)
    return path


def _slides(path: Path) -> Path:
    from pptx import Presentation

    deck = Presentation()
    deck.slides.add_slide(deck.slide_layouts[5]).shapes.title.text = "Queues"
    deck.save(path)
    return path


def test_a_real_word_file_is_read(tmp_path):
    conversion = converter.convert(_word_file(tmp_path / "notes.docx"), "docx")
    assert conversion.problems == ()
    assert [t.text for t in conversion.document.texts] == ["Stacks", "Last in, first out."]


def test_a_broken_word_file_is_refused_as_unreadable(tmp_path):
    broken = tmp_path / "broken.docx"
    broken.write_bytes(b"PK\x03\x04" + b"not really a Word file" * 20)     # starts like a .docx, isn't one
    with pytest.raises(FileRefused) as refused:
        converter.convert(broken, "docx")
    assert refused.value.reason == messages.UNREADABLE


def test_slides_renamed_to_docx_are_refused_as_a_mismatch(tmp_path):
    renamed = tmp_path / "notes.docx"
    shutil.copy(_slides(tmp_path / "deck.pptx"), renamed)                  # the pre-check can't tell these apart
    with pytest.raises(FileRefused) as refused:
        converter.convert(renamed, "docx")
    assert refused.value.reason == messages.TYPE_MISMATCH

# ================================================================ part 3: the cache of Docling results

def _docling_must_not_run(monkeypatch):
    def fail(source_type):
        raise AssertionError("Docling ran, but the result should have come from the cache")

    monkeypatch.setattr(converter, "get_converter", fail)


def test_a_file_read_once_comes_from_the_cache_the_second_time(tmp_path, data_dir, monkeypatch):
    path = _word_file(tmp_path / "notes.docx")
    first = converter.convert(path, "docx", file_sha256(path))
    _docling_must_not_run(monkeypatch)
    second = converter.convert(path, "docx", file_sha256(path))
    assert (first.from_cache, second.from_cache) == (False, True)
    assert second.document.export_to_dict() == first.document.export_to_dict()


def test_without_the_hash_nothing_is_cached(tmp_path, data_dir):
    path = _word_file(tmp_path / "notes.docx")
    converter.convert(path, "docx")
    assert not converter.cache_file(file_sha256(path), "docx").exists()


def test_a_partial_result_is_not_cached(monkeypatch, data_dir):
    _fake_docling(monkeypatch, ConversionStatus.PARTIAL_SUCCESS, DoclingComponentType.PIPELINE)
    converter.convert(Path("book.pdf"), "pdf", "a" * 64)
    assert not converter.cache_file("a" * 64, "pdf").exists()        # next time Docling may read all of it


def test_a_damaged_cache_file_is_read_again_and_replaced(tmp_path, data_dir):
    path = _word_file(tmp_path / "notes.docx")
    cached = converter.cache_file(file_sha256(path), "docx")
    cached.write_text("{ half a file", encoding="utf-8")
    conversion = converter.convert(path, "docx", file_sha256(path))
    assert not conversion.from_cache
    assert [t.text for t in conversion.document.texts] == ["Stacks", "Last in, first out."]
    assert converter.convert(path, "docx", file_sha256(path)).from_cache


def test_the_cache_name_changes_when_our_settings_change(monkeypatch, data_dir):
    before = converter.cache_file("a" * 64, "pdf")
    monkeypatch.setattr(converter, "PDF_TIMEOUT_SECONDS", 60.0)
    assert converter.cache_file("a" * 64, "pdf") != before
    assert converter.cache_file("a" * 64, "docx") != before
    assert converter.cache_file("a" * 64, "docx") != converter.cache_file("a" * 64, "pptx")


def test_sets_are_sorted_before_hashing():
    assert converter._json_fallback(set("fbdaec")) == list("abcdef")


def test_the_cache_name_is_the_same_in_every_run():
    """Python orders sets differently in each run; a name that changed would never find its cache again."""
    code = "from app.ingestion import converter; print(converter.settings_fingerprint('pdf'))"
    backend = Path(__file__).resolve().parents[2]
    names = {subprocess.run([sys.executable, "-c", code], cwd=backend, capture_output=True, text=True, check=True,
                            env={**os.environ, "PYTHONHASHSEED": seed}).stdout.strip() for seed in ("0", "3")}
    assert len(names) == 1 and len(names.pop()) == 12
    

# ================================================================ part 4: real Docling PDF models (on request)

@pytest.mark.skipif(os.getenv("DOCLING_PDF_TEST") != "1",
                    reason="PDF models test: set DOCLING_PDF_TEST=1 (downloads Docling's models the first time)")
def test_a_real_pdf_is_read_page_by_page(digital_pdf):
    conversion = converter.convert(digital_pdf, "pdf")
    assert conversion.problems == ()
    document = conversion.document
    assert len(document.pages) == 3
    assert "linked list" in " ".join(t.text for t in document.texts)
    assert {t.prov[0].page_no for t in document.texts if t.prov} == {1, 2, 3}
