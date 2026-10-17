"""The fast path for long PDFs (fast_pdf.py). Owner: Areeba.

samples/fast_pdf/textbook.pdf is a 25-page book with everything real textbooks have: chapters,
sections, a bold subsection, book-style paragraphs, bullet and numbered lists, a C++ listing, a fully
ruled table, a table with only horizontal rules, a drawing with labels, a picture, a footnote, a
two-column glossary, running headers and page numbers. textbook.expected.json says what is on each
page. Docling's PDF models aren't needed: where a test needs Docling, a stand-in reads the pages.
"""
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("docling")

import pypdfium2 as pdfium  # noqa: E402
from docling.datamodel.base_models import ConversionStatus  # noqa: E402

from app.ingestion.contract import PrecheckResult, ResourceMeta  # noqa: E402
from app.ingestion.loaders import docs, fast_pdf  # noqa: E402

BOOK = Path(__file__).parent / "samples" / "fast_pdf" / "textbook.pdf"
EXPECTED = json.loads(BOOK.with_suffix(".expected.json").read_text(encoding="utf-8"))
DRAWING_PAGES = {4, 9, 15, 19, 24}     # a drawing with labels (a table with only horizontal rules is read here)


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class StandIn:
    """Plays Docling's part: reads the pages it is given with the fast path's own reader."""

    def __init__(self, fail: bool = False):
        self.calls: list[int] = []
        self.fail = fail

    def convert(self, source, raises_on_error=False, **kwargs):
        pdf = pdfium.PdfDocument(source.stream.read())
        self.calls.append(len(pdf))
        if self.fail:
            return SimpleNamespace(status=ConversionStatus.FAILURE, document=None, errors=["no"])
        scans = [fast_pdf.scan_page(pdf, i) for i in range(len(pdf))]
        book = fast_pdf.Book(scans, [])
        items = {s.number: fast_pdf.read_page(s, book, [0, 1]) for s in scans}
        return SimpleNamespace(status=ConversionStatus.SUCCESS, errors=[],
                               document=fast_pdf._to_document("pages", scans, items))


def make_stand_in():
    """For Docling processes (they import this module afresh and call it by name)."""
    return StandIn()


def read_book(tmp_path, stand_in=None):
    stand_in = stand_in or StandIn()
    doc, complete, report = fast_pdf.convert_pdf(BOOK, lambda: stand_in, lambda key: tmp_path / f"{key}.json")
    blocks = docs.to_blocks(docs.walk(doc, "pdf", docs.document_title(doc, "pdf", BOOK.name)), "pdf")
    return blocks, complete, report, stand_in


@pytest.fixture(scope="module")
def scans():
    pdf = pdfium.PdfDocument(str(BOOK))
    return [fast_pdf.scan_page(pdf, i) for i in range(len(pdf))]


def test_only_unusual_pages_go_to_docling(scans):
    routed = {s.number: s.reason for s in scans if s.route == "docling"}
    assert set(routed) == DRAWING_PAGES
    assert len(scans) == 25 and any(ln.col == 1 for s in scans for ln in s.lines)   # the glossary: two columns


def test_every_block_on_a_fast_page_is_read_and_nothing_else(tmp_path, scans):
    blocks, complete, report, _ = read_book(tmp_path)
    fast = {s.number for s in scans if s.route == "fast"}
    by_page: dict[int, list] = {}
    for b in blocks:
        for page in [b.loc.page] + b.extra.get("pages", []):
            by_page.setdefault(page, []).append(b)
    missing = []
    for kind, text, path, page in EXPECTED:
        if not {page, page + 1} <= fast:      # its page (or the next, where it may carry on) went to Docling
            continue
        near = [b for p in (page - 1, page, page + 1, page + 2) for b in by_page.get(p, [])]
        if kind == "table":
            rows = json.loads(text)
            found = [b for b in near if b.kind == "table" and all(f"| {c}" in b.text for r in rows for c in r)]
        elif kind == "code":
            found = [b for b in near if b.kind == "code" and b.text.strip() == text.strip()]
        else:
            start, end = text if isinstance(text, list) else (text, text)
            want = {"title": "heading", "footnote": "paragraph"}.get(kind, kind)
            found = [b for b in near if b.kind == want and norm(start) in norm(b.text)
                     and norm(end).rstrip("1") in norm(b.text)]
            if kind in ("heading", "title"):
                found = [b for b in found if b.heading_path == path + [text]]
            elif kind in ("paragraph", "list_item"):
                found = [b for b in found if b.heading_path == path]
        if not found:
            missing.append((kind, page, str(text)[:60]))
    assert missing == []
    known = " ".join(norm(t if isinstance(t, str) else " ".join(t)) for _, t, _, _ in EXPECTED)
    on_fast_pages = [b for b in blocks if b.loc.page in fast and b.kind not in ("table", "code")]
    junk = [b.text for b in on_fast_pages if not any(norm(line)[:40] in known for line in b.text.split("\n"))]
    assert junk == []                         # no running headers, page numbers or drawing labels


def test_code_keeps_its_line_breaks_and_indentation(tmp_path):
    blocks, *_ = read_book(tmp_path)
    code = next(b.text for b in blocks if b.kind == "code")
    assert code.splitlines()[:4] == ["int sum(const int a[], int n) {", "    int total = 0;",
                                     "    for (int i = 0; i < n; i++) {", "        if (a[i] > 0) {"]


def test_lists_keep_their_markers_and_tables_their_cells(tmp_path):
    blocks, *_ = read_book(tmp_path)
    steps = [b for b in blocks if b.kind == "list_item" and b.text == "Read the input."]
    assert steps and steps[0].extra["marker"] == "1."
    assert any(b.kind == "list_item" and b.extra.get("marker") == "•" for b in blocks)
    table = next(b.text for b in blocks if b.kind == "table")
    assert table.splitlines()[0].split("|")[1:4] == [" Operator   ", " Meaning   ", " Example   "]


def test_docling_reads_only_its_pages_in_batches_and_each_batch_is_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(fast_pdf, "BATCH_PAGES", 2)
    blocks, complete, report, stand_in = read_book(tmp_path)
    assert complete and report["docling_pages"] == len(DRAWING_PAGES)
    assert stand_in.calls == [2, 2, 1]               # 5 pages, 2 at a time, never the whole book
    pages = [b.loc.page for b in blocks]
    covered = {p for b in blocks for p in [b.loc.page] + b.extra.get("pages", [])}
    assert pages == sorted(pages) and covered == set(range(1, 26))
    again = StandIn()
    read_book(tmp_path, again)
    assert again.calls == []                          # every batch was saved, so nothing is read twice


@pytest.mark.slow                 # starts two Python processes: about a minute on Windows
def test_several_docling_processes_read_the_same_book(tmp_path, monkeypatch):
    monkeypatch.setattr(fast_pdf, "BATCH_PAGES", 2)
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()
    one, _, _, _ = read_book(tmp_path / "one")
    doc, complete, report = fast_pdf.convert_pdf(BOOK, StandIn, lambda key: tmp_path / "two" / f"{key}.json",
                                                 workers=2, converter_name="test_fast_pdf:make_stand_in")
    two = docs.to_blocks(docs.walk(doc, "pdf", docs.document_title(doc, "pdf", BOOK.name)), "pdf")
    assert complete and report["docling_workers"] == 2
    assert [(b.kind, b.text, b.loc.page) for b in two] == [(b.kind, b.text, b.loc.page) for b in one]


def test_if_the_processes_fail_the_batches_are_read_one_by_one(tmp_path, monkeypatch):
    monkeypatch.setattr(fast_pdf, "BATCH_PAGES", 2)
    stand_in = StandIn()
    doc, complete, report = fast_pdf.convert_pdf(BOOK, lambda: stand_in, lambda key: tmp_path / f"{key}.json",
                                                 workers=2, converter_name="no_such_module:nothing")
    assert complete and report["docling_workers"] == 1 and stand_in.calls == [2, 2, 1]


def test_a_failed_batch_marks_the_book_incomplete_and_is_not_saved(tmp_path):
    blocks, complete, _, _ = read_book(tmp_path, StandIn(fail=True))
    assert not complete
    assert not any(b.loc.page in DRAWING_PAGES for b in blocks)
    assert list(tmp_path.glob("*.json")) == []


def test_short_files_and_mostly_unusual_files_go_to_docling_whole(tmp_path, monkeypatch):
    monkeypatch.setattr(fast_pdf, "MIN_PAGES", 30)
    doc, _, report = fast_pdf.convert_pdf(BOOK, StandIn, lambda key: tmp_path / key)
    assert doc is None and "short" in report["mode"]
    monkeypatch.setattr(fast_pdf, "MIN_PAGES", 20)
    monkeypatch.setattr(fast_pdf, "ROUTE_ALL_ABOVE", 0.1)
    doc, _, report = fast_pdf.convert_pdf(BOOK, StandIn, lambda key: tmp_path / key)
    assert doc is None and "most pages" in report["mode"]


def _meta() -> ResourceMeta:
    return ResourceMeta(resource_id="r-book", course_id="c1", file_name=BOOK.name, file_sha256="1" * 64,
                        precheck=PrecheckResult(source_type="pdf", pages_total=25))


def test_the_loader_uses_the_fast_path_and_can_switch_it_off(data_dir, monkeypatch):
    stand_in = StandIn()
    monkeypatch.setattr(docs, "_converter", lambda: stand_in)
    doc = docs.load(BOOK, _meta())
    assert doc.quality.status == "ok" and doc.title == "Programming Fundamentals"
    assert stand_in.calls == [len(DRAWING_PAGES)]

    monkeypatch.setenv("INGESTION_FAST_PDF", "0")
    whole = StandIn()

    def convert_whole(source, raises_on_error=False, **kwargs):      # Docling given the file itself
        whole.calls.append(Path(source).name)
        return SimpleNamespace(status=ConversionStatus.SUCCESS, errors=[], document=fast_pdf._to_document(
            "book", [], {}))

    whole.convert = convert_whole
    monkeypatch.setattr(docs, "_converter", lambda: whole)
    docs.load(BOOK, _meta())
    assert whole.calls == [BOOK.name]
