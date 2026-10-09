"""Pre-check, routing and saving. Owner: Minahil."""

import re
from pathlib import Path

import pytest

from app.ingestion import storage
from app.ingestion.contract import ResourceMeta
from app.ingestion.dispatcher import (
    PDF_PASSWORD,
    dispatch,
    garbage_share,
    is_supported,
    precheck_pdf,
)

DAY0 = Path(__file__).parent / "samples" / "day0"


@pytest.fixture(autouse=True)
def parsed_root(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PARSED_ROOT", tmp_path / "parsed")


def meta(name: str) -> ResourceMeta:
    resource_id = "test-" + re.sub(r"\W+", "-", Path(name).stem)
    return ResourceMeta(resource_id=resource_id, course_id="c1", file_name=name)


@pytest.mark.parametrize("name,route,reason", [
    ("digital_two_pages.pdf", "pdf", "digital"),
    ("digital_with_picture.pdf", "pdf", "digital"),
    ("scanned_page.pdf", "scanned_pdf", "scanned pages"),
    ("garbled_text_layer.pdf", "scanned_pdf", "garbled text layer"),
])
def test_precheck_routes_each_pdf_to_one_track(name, route, reason):
    result = precheck_pdf(DAY0 / name)
    assert (result["route"], result["reason"]) == (route, reason)


def test_large_pictures_on_digital_pages_are_flagged_for_track_1():
    assert precheck_pdf(DAY0 / "digital_with_picture.pdf")["large_image_pages"] == [1]
    assert precheck_pdf(DAY0 / "digital_two_pages.pdf")["large_image_pages"] == []


def test_loader_receives_the_precheck():
    doc = dispatch(DAY0 / "scanned_page.pdf", meta("scanned_page.pdf"))
    assert doc.source_type == "scanned_pdf"


def test_password_pdf_fails_with_a_readable_message():
    doc = dispatch(DAY0 / "password_protected.pdf", meta("password_protected.pdf"))
    assert doc.quality.status == "failed"
    assert doc.quality.warnings == [PDF_PASSWORD]


def test_dispatch_saves_parsed_json_and_times_the_stages():
    doc = dispatch(DAY0 / "digital_two_pages.pdf", meta("digital_two_pages.pdf"))
    assert storage.load_parsed(doc.resource_id) == doc
    assert {"precheck", "dispatch_total"} <= set(doc.quality.seconds_taken)


def test_a_crashing_loader_becomes_a_failed_document(monkeypatch):
    def explode(path, meta):
        raise RuntimeError("bug in a loader")
    monkeypatch.setattr("app.ingestion.dispatcher.get_loader", lambda source_type: explode)
    doc = dispatch(DAY0 / "stack.cpp", meta("stack.cpp"))
    assert doc.quality.status == "failed" and doc.quality.warnings


def test_original_file_name_is_kept_when_the_stored_file_is_renamed():
    doc = dispatch(DAY0 / "reading_list.txt", meta("Week 1 reading list.txt"))
    assert doc.file_name == "Week 1 reading list.txt"


def test_garbage_share():
    assert garbage_share("Normalization removes redundancy.") == 0.0
    assert garbage_share("ÚÛÝ Þßà") == 1.0
    assert garbage_share("") == 0.0


@pytest.mark.parametrize("name,ok", [("L4.PDF", True), ("lab.cpp", True), ("talk.m4a", True),
                                     ("notes.xyz", False), ("archive.zip", False)])
def test_is_supported(name, ok):
    assert is_supported(name) is ok


def test_unsafe_resource_ids_are_refused():
    with pytest.raises(ValueError):
        storage.resource_dir("../../etc")


def test_a_precheck_bug_falls_back_to_track_1(monkeypatch):
    def broken_precheck(path):
        raise KeyError("bug in the pre-check")
    monkeypatch.setattr("app.ingestion.dispatcher.precheck_pdf", broken_precheck)
    doc = dispatch(DAY0 / "digital_two_pages.pdf", meta("digital_two_pages.pdf"))
    assert doc.source_type == "pdf" and doc.quality.status != "failed"
