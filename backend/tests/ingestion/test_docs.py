"""Track 1: digital PDF, DOCX and PPTX through Docling. Owner: Areeba.

The DOCX and PPTX files are built fresh in each test with python-docx and
python-pptx (both come with Docling), so no big files are committed. Reading a
PDF needs Docling's layout models, so the PDF rules are tested on a Docling
document built by hand; real PDFs run only in the slow test at the end.
"""
import re
import zipfile
from pathlib import Path

import pytest

pytest.importorskip("docling")      # installed from requirements.txt; until then these tests are skipped

import docx  # noqa: E402
from docling_core.types.doc import (BoundingBox, ContentLayer, DocItemLabel, DoclingDocument,  # noqa: E402
                                    ProvenanceItem, Size, TableCell, TableData)
from pptx import Presentation  # noqa: E402
from pptx.util import Inches  # noqa: E402

from app.ingestion import messages  # noqa: E402
from app.ingestion.contract import PrecheckResult, ResourceMeta  # noqa: E402
from app.ingestion.dispatcher import ingest_file  # noqa: E402
from app.ingestion.loaders import docs  # noqa: E402

SAMPLES = Path(__file__).parent / "samples" / "docs"


# ---------------------------------------------------------------------------
# Test files
# ---------------------------------------------------------------------------

@pytest.fixture
def normalization_docx(tmp_path) -> Path:
    d = docx.Document()
    d.add_heading("Normalization", level=0)                       # Word's "Title" style
    d.add_heading("First Normal Form", level=1)
    d.add_paragraph("A table is in 1NF when every cell holds one value.")
    d.add_paragraph("No repeating groups", style="List Bullet")
    d.add_heading("Example", level=2)
    table = d.add_table(rows=3, cols=2)
    for r, row in enumerate([("Student", "Course"), ("Ali", "DB"), ("Sara", "OOP")]):
        for c, value in enumerate(row):
            table.cell(r, c).text = value
    d.add_heading("Third Normal Form", level=1)
    d.add_paragraph("Remove transitive depen-\ndencies between non-key columns.")
    d.add_paragraph("Find the key", style="List Number")
    d.add_paragraph("Split the table", style="List Number")
    path = tmp_path / "normalization.docx"
    d.save(path)
    return path


@pytest.fixture
def stacks_pptx(tmp_path) -> Path:
    p = Presentation()
    s = p.slides.add_slide(p.slide_layouts[0])                    # title slide
    s.shapes.title.text = "Stacks"
    s.placeholders[1].text = "Data Structures, Lecture 6"
    s = p.slides.add_slide(p.slide_layouts[1])                    # title and bullets
    s.shapes.title.text = "Push and pop"
    s.placeholders[1].text_frame.text = "push adds on top"
    s.notes_slide.notes_text_frame.text = "Ask what happens when you pop an empty stack."
    s = p.slides.add_slide(p.slide_layouts[5])                    # title and a table
    s.shapes.title.text = "Operations and cost"
    table = s.shapes.add_table(3, 2, Inches(1), Inches(2), Inches(6), Inches(1.5)).table
    for r, row in enumerate([("Operation", "Cost"), ("push", "O(1)"), ("pop", "O(1)")]):
        for c, value in enumerate(row):
            table.cell(r, c).text = value
    s = p.slides.add_slide(p.slide_layouts[6])                    # blank slide, no title
    s.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(1)).text_frame.text = "Questions?"
    path = tmp_path / "stacks.pptx"
    p.save(path)
    return path


def lecture_pdf() -> DoclingDocument:
    """What Docling returns for a 4-page digital lecture PDF, built by hand (no models needed)."""
    d = DoclingDocument(name="lecture5")

    def on(page: int) -> ProvenanceItem:
        return ProvenanceItem(page_no=page, bbox=BoundingBox(l=50, t=50, r=500, b=80), charspan=(0, 0))

    for page in range(1, 5):
        d.add_page(page_no=page, size=Size(width=595, height=842))
    d.add_title("Lecture 5: Joins", prov=on(1))
    d.add_heading("Inner join", level=1, prov=on(1))
    d.add_text(DocItemLabel.TEXT, "An inner join keeps rows that match in both tables.", prov=on(1))
    d.add_heading("Example", level=2, prov=on(2))
    cells = [TableCell(text=value, start_row_offset_idx=r, end_row_offset_idx=r + 1,
                       start_col_offset_idx=c, end_col_offset_idx=c + 1, column_header=r == 0)
             for r, row in enumerate([("id", "name"), ("1", "Ali")]) for c, value in enumerate(row)]
    d.add_table(TableData(num_rows=2, num_cols=2, table_cells=cells), prov=on(2))
    d.add_heading("Outer join", level=1, prov=on(3))
    d.add_text(DocItemLabel.TEXT, "An outer join also keeps rows without a match.", prov=on(3))
    for page in range(1, 4):
        d.add_text(DocItemLabel.TEXT, f"Database Systems | Page {page}", prov=on(page))   # a footer Docling missed
        d.add_text(DocItemLabel.PAGE_FOOTER, str(page), prov=on(page),
                   content_layer=ContentLayer.FURNITURE)                                  # one it caught
    d.add_picture(prov=on(4))                                                             # page 4: a picture only
    return d


def pdf_meta() -> ResourceMeta:
    return ResourceMeta(resource_id="r-pdf", course_id="c1", file_name="lecture5.pdf", file_sha256="0" * 64,
                        precheck=PrecheckResult(source_type="pdf", pages_total=4))


def text_of(doc, start: str):
    return next(b for b in doc.blocks if b.text.startswith(start))


# ---------------------------------------------------------------------------
# DOCX (real Docling, fast)
# ---------------------------------------------------------------------------

def test_docx_headings_become_the_heading_path(normalization_docx, data_dir):
    doc = ingest_file(normalization_docx, "r-docx", "c1")
    assert doc.quality.status == "ok" and doc.parser == "docling"
    assert doc.title == "Normalization"
    assert text_of(doc, "A table is in 1NF").heading_path == ["Normalization", "First Normal Form"]
    assert text_of(doc, "Remove transitive").heading_path == ["Normalization", "Third Normal Form"]
    assert all(b.loc.page is None for b in doc.blocks)              # DOCX has no pages


def test_text_is_cleaned_but_tables_are_not(normalization_docx, data_dir):
    doc = ingest_file(normalization_docx, "r-docx", "c1")
    assert text_of(doc, "Remove transitive").text == "Remove transitive dependencies between non-key columns."
    tables = [b for b in doc.blocks if b.kind == "table"]
    assert len(tables) == 1
    assert tables[0].text.startswith("| Student") and "| Sara" in tables[0].text
    assert tables[0].heading_path == ["Normalization", "First Normal Form", "Example"]


def test_numbered_list_markers_are_kept(normalization_docx, data_dir):
    doc = ingest_file(normalization_docx, "r-docx", "c1")
    assert [b.extra.get("marker") for b in doc.blocks if b.text in ("Find the key", "Split the table")] == ["1.", "2."]


# ---------------------------------------------------------------------------
# PPTX (real Docling, fast)
# ---------------------------------------------------------------------------

def test_pptx_path_is_deck_title_then_slide_title(stacks_pptx, data_dir):
    doc = ingest_file(stacks_pptx, "r-pptx", "c1")
    assert doc.quality.status == "ok" and doc.quality.units_total == 4
    assert all(b.loc.slide is not None for b in doc.blocks)
    assert {b.loc.slide: b.heading_path for b in doc.blocks} == {
        1: ["stacks", "Stacks"], 2: ["stacks", "Push and pop"],
        3: ["stacks", "Operations and cost"], 4: ["stacks", "Slide 4"]}


def test_speaker_notes_become_slide_notes(stacks_pptx, data_dir):
    doc = ingest_file(stacks_pptx, "r-pptx", "c1")
    notes = [b for b in doc.blocks if b.kind == "slide_notes"]
    assert [(b.loc.slide, b.text) for b in notes] == [(2, "Ask what happens when you pop an empty stack.")]


# ---------------------------------------------------------------------------
# Never twice, never crash
# ---------------------------------------------------------------------------

def test_the_same_file_is_converted_only_once(normalization_docx, data_dir, monkeypatch):
    first = ingest_file(normalization_docx, "r-first", "c1")

    def no_second_conversion():
        raise AssertionError("Docling ran again on a file it already read")

    monkeypatch.setattr(docs, "_converter", no_second_conversion)
    second = ingest_file(normalization_docx, "r-second", "c1")      # same file, uploaded again
    assert second.quality.status == "ok"
    assert [b.model_dump() for b in second.blocks] == [b.model_dump() for b in first.blocks]
    assert (data_dir / "r-first" / "raw" / "docling.json").exists()
    assert (data_dir / "r-second" / "raw" / "docling.json").exists()


def test_a_file_docling_cannot_read_fails_politely(tmp_path, data_dir):
    fake = tmp_path / "notes.docx"                     # a real zip, so it passes the pre-check, but not a Word file
    with zipfile.ZipFile(fake, "w") as z:
        z.writestr("hello.txt", "not a Word document")
    doc = ingest_file(fake, "r-fake", "c1")
    assert doc.quality.status == "failed"
    assert doc.quality.warnings == [messages.UNREADABLE]


# ---------------------------------------------------------------------------
# PDF rules, on a Docling document built by hand
# ---------------------------------------------------------------------------

def pdf_blocks():
    d = lecture_pdf()
    return docs.to_blocks(docs.walk(d, "pdf", docs.document_title(d, "pdf", "lecture5.pdf")), "pdf")


def test_pdf_blocks_carry_their_page_and_heading_path():
    blocks = pdf_blocks()
    assert [(b.loc.page, b.kind, b.heading_path) for b in blocks] == [
        (1, "heading", ["Lecture 5: Joins"]),
        (1, "heading", ["Lecture 5: Joins", "Inner join"]),
        (1, "paragraph", ["Lecture 5: Joins", "Inner join"]),
        (2, "heading", ["Lecture 5: Joins", "Inner join", "Example"]),
        (2, "table", ["Lecture 5: Joins", "Inner join", "Example"]),
        (3, "heading", ["Lecture 5: Joins", "Outer join"]),
        (3, "paragraph", ["Lecture 5: Joins", "Outer join"]),
    ]
    assert [b.seq for b in blocks] == list(range(len(blocks)))


def test_pdf_headers_and_footers_are_dropped():
    assert not any("Database Systems" in b.text or b.text.strip() in {"1", "2", "3"} for b in pdf_blocks())


def test_pdf_quality_report(monkeypatch, data_dir):
    monkeypatch.setattr(docs, "convert", lambda path, meta: (lecture_pdf(), True))
    doc = docs.load(Path("lecture5.pdf"), pdf_meta())
    assert doc.title == "Lecture 5: Joins"
    assert doc.quality.status == "ok" and doc.quality.units_total == 4
    assert doc.quality.warnings == [messages.no_text_units("Pages", [4])]
    assert doc.quality.chars_total == sum(len(b.text) for b in doc.blocks)


def test_a_partly_read_file_is_marked_degraded(monkeypatch, data_dir):
    monkeypatch.setattr(docs, "convert", lambda path, meta: (lecture_pdf(), False))
    doc = docs.load(Path("lecture5.pdf"), pdf_meta())
    assert doc.quality.status == "degraded"
    assert messages.PARTIAL in doc.quality.warnings


# ---------------------------------------------------------------------------
# Your own sample files in samples/docs/ (PDFs need Docling's models: slow)
# ---------------------------------------------------------------------------

def _samples():
    files = sorted(p for p in SAMPLES.glob("*") if p.suffix.lower() in {".pdf", ".docx", ".pptx"})
    return [pytest.param(p, id=p.name, marks=[pytest.mark.slow] if p.suffix.lower() == ".pdf" else [])
            for p in files]


@pytest.mark.parametrize("path", _samples())
def test_my_sample_files(path, data_dir):
    doc = ingest_file(path, "sample-" + re.sub(r"[^A-Za-z0-9_-]+", "-", path.stem)[:50], "c1")
    assert doc.quality.status != "failed", doc.quality.warnings
    assert all(b.heading_path[0] == doc.title for b in doc.blocks)
    if doc.source_type == "pdf":
        assert all(1 <= b.loc.page <= doc.quality.units_total for b in doc.blocks)