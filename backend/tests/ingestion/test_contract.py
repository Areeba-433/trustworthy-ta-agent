"""Level 1: every registered loader follows the contract. Owner: Minahil.

Runs on every pull request. Every sample file in samples/<track>/ goes through
the real dispatcher, so this tests routing and the loader together.
Samples whose name contains "password" or "broken" must fail politely.
"""

from pathlib import Path

import pytest

from app.ingestion import storage
from app.ingestion.contract import SOURCE_TYPES, ParsedDocument, ResourceMeta, contract_violations
from app.ingestion.dispatcher import EXTENSIONS, UnsupportedFileType, dispatch, source_type_for
from app.ingestion.loaders import MISSING
from app.ingestion.registry import registered

SAMPLES = Path(__file__).parent / "samples"
SAMPLE_FILES = sorted(p for p in SAMPLES.rglob("*") if p.is_file() and source_type_for(p)
                      and p.name != "README.md")
MUST_FAIL = ("password", "broken")


@pytest.fixture(autouse=True)
def parsed_root(tmp_path, monkeypatch):
    """Keep test output out of the real parsed/ folder."""
    monkeypatch.setattr(storage, "PARSED_ROOT", tmp_path / "parsed")


def meta_for(path: Path) -> ResourceMeta:
    return ResourceMeta(resource_id=f"contract-{path.parent.name}-{path.stem}",
                        course_id="contract-test", file_name=path.name)


def test_every_source_type_has_a_loader():
    missing = sorted(set(SOURCE_TYPES) - set(registered()))
    assert not missing, f"No loader for {missing}. Tracks that failed to import: {MISSING}"


@pytest.mark.parametrize("path", SAMPLE_FILES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_sample_follows_contract(path):
    doc = dispatch(path, meta_for(path))
    assert contract_violations(doc) == []
    # Every field survives a save and a reload (what the chunker will read).
    assert ParsedDocument.model_validate_json(doc.model_dump_json()) == doc
    if any(word in path.name.lower() for word in MUST_FAIL):
        assert doc.quality.status == "failed"


@pytest.mark.parametrize("path", SAMPLE_FILES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_same_output_twice(path):
    first, second = dispatch(path, meta_for(path)), dispatch(path, meta_for(path))
    timings = {"quality": {"seconds_taken"}}
    assert first.model_dump(exclude=timings) == second.model_dump(exclude=timings)


@pytest.mark.parametrize("suffix", sorted(EXTENSIONS))
def test_empty_file_fails_politely(tmp_path, suffix):
    path = tmp_path / f"empty{suffix}"
    path.write_bytes(b"")
    doc = dispatch(path, meta_for(path))
    assert doc.quality.status == "failed"
    assert contract_violations(doc) == []


@pytest.mark.parametrize("suffix", [".pdf", ".docx", ".pptx", ".png", ".mp3"])
def test_corrupt_file_never_crashes(tmp_path, suffix):
    path = tmp_path / f"broken{suffix}"
    path.write_bytes(b"this is not really a file " * 40)
    doc = dispatch(path, meta_for(path))   # must not raise
    assert contract_violations(doc) == []
    if doc.parser_version != "stub":       # stubs don't parse, so they can't notice
        assert doc.quality.status == "failed"


def test_unknown_type_is_rejected_before_any_work(tmp_path):
    path = tmp_path / "notes.xyz"
    path.write_text("hello")
    with pytest.raises(UnsupportedFileType):
        dispatch(path, meta_for(path))


def test_the_rules_catch_a_bad_document():
    """Guards the checker itself: a document breaking each rule must be reported."""
    good = dispatch(SAMPLES / "day0" / "stacks.pptx", meta_for(SAMPLES / "day0" / "stacks.pptx"))
    bad = good.model_copy(deep=True)
    bad.blocks[0].seq = 5
    bad.blocks[0].heading_path = ["Some other title"]
    bad.blocks[0].loc.slide = None
    bad.quality.chars_total += 1
    problems = " | ".join(contract_violations(bad))
    for expected in ("seq", "heading_path", "loc.slide", "chars_total"):
        assert expected in problems
