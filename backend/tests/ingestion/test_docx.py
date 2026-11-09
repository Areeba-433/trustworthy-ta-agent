import shutil
from collections import Counter

import pytest
from docx import Document
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Pt
from PIL import Image, ImageDraw
from app.ingestion import messages
from app.ingestion.contract import Block, Location
from app.ingestion.loaders.docx import (_add_flowcharts, _drop_word_extras, _link_captions, _mark_captions,
                                        _mark_code, _promote_titles)
from app.ingestion.loaders.docx_flowchart import HEADER as FLOWCHART_HEADER
from app.ingestion.loaders.docx_flowchart import Flowchart, read_flowcharts
from app.ingestion.pipeline import process

@pytest.fixture
def make_docx(tmp_path):
    def make(name="week1.docx", build=None):
        doc = Document()
        if build:
            build(doc)
        path = tmp_path / name
        doc.save(path)
        return path
    return make


def _lecture(doc):
    doc.add_heading("Intro", 1)
    doc.add_paragraph("Hello world paragraph.")
    doc.add_paragraph("Figure 1: a diagram", style="Caption")
    doc.add_heading("Details", 2)
    doc.add_paragraph("More text here.")


def _block(text, kind="paragraph"):
    return Block(seq=0, kind=kind, text=text, heading_path=["t"], loc=Location(), lang="en")


def test_a_word_file_goes_all_the_way_to_chunks_json(make_docx, data_dir, word_tokens):
    result = process(make_docx(build=_lecture), "w1", "c1")
    assert (result.status, result.warnings) == ("ok", [])
    assert (data_dir / "w1" / "parsed.json").exists() and (data_dir / "w1" / "chunks.json").exists()
    assert result.chunked.chunker == "docx-sections/2"
    assert all(b.heading_path[0] == result.parsed.title for b in result.parsed.blocks)
    assert all(b.loc == Location() for b in result.parsed.blocks)


def test_a_caption_paragraph_becomes_a_caption_block(make_docx, data_dir, word_tokens):
    result = process(make_docx(build=_lecture), "w2", "c1")
    captions = [b for b in result.parsed.blocks if b.kind == "caption"]
    assert [b.text for b in captions] == ["Figure 1: a diagram"]


def test_header_and_footer_stay_out(make_docx, data_dir, word_tokens):
    def build(doc):
        doc.sections[0].header.paragraphs[0].text = "RUNNING HEADER"
        doc.sections[0].footer.paragraphs[0].text = "RUNNING FOOTER"
        _lecture(doc)

    result = process(make_docx(build=build), "w3", "c1")
    text = " ".join(b.text for b in result.parsed.blocks)
    assert "RUNNING HEADER" not in text and "RUNNING FOOTER" not in text


def test_a_table_becomes_one_markdown_block(make_docx, data_dir, word_tokens):
    def build(doc):
        doc.add_heading("Data", 1)
        table = doc.add_table(rows=2, cols=2)
        for cell, value in zip(table._cells, ["Key", "Value", "a", "1"]):
            cell.text = value
        doc.add_paragraph("After the table.")

    result = process(make_docx(build=build), "w4", "c1")
    tables = [b for b in result.parsed.blocks if b.kind == "table"]
    assert len(tables) == 1 and "|" in tables[0].text and "Key" in tables[0].text


def test_each_heading_section_gets_its_own_chunks(make_docx, data_dir, word_tokens):
    result = process(make_docx(build=_lecture), "w5", "c1")
    paths = [tuple(c.heading_path) for c in result.chunked.chunks]
    assert len(paths) == 2 and paths[0] != paths[1]
    assert paths[1][-1] == "Details"


def test_a_file_without_text_fails_politely(make_docx, data_dir, word_tokens):
    result = process(make_docx(name="empty.docx"), "w6", "c1")
    assert (result.status, result.warnings, result.chunked) == ("failed", [messages.NO_TEXT_FILE], None)
    assert not (data_dir / "w6" / "chunks.json").exists()


def test_a_broken_file_fails_without_chunks(tmp_path, data_dir, word_tokens):
    path = tmp_path / "broken.docx"
    path.write_bytes(b"PK\x03\x04 this is not a real zip")
    result = process(path, "w7", "c1")
    assert result.status == "failed" and result.chunked is None
    assert not (data_dir / "w7" / "chunks.json").exists()


def test_a_pdf_renamed_to_docx_is_refused(digital_pdf, tmp_path, data_dir):
    fake = tmp_path / "fake.docx"
    shutil.copy(digital_pdf, fake)
    result = process(fake, "w8", "c1")
    assert (result.status, result.warnings) == ("failed", [messages.TYPE_MISMATCH])


def test_processing_the_same_word_file_twice_gives_the_same_chunks(make_docx, data_dir, word_tokens):
    path = make_docx(build=_lecture)
    process(path, "w9", "c1")
    first = (data_dir / "w9" / "chunks.json").read_bytes()
    process(path, "w9", "c1")
    assert (data_dir / "w9" / "chunks.json").read_bytes() == first


def test_only_paragraphs_with_a_caption_text_are_marked():
    blocks = [_block("Figure 1:  a diagram"), _block("Plain text"), _block("Figure 1: a diagram", "list_item")]
    marked = _mark_captions(blocks, Counter({"Figure 1: a diagram": 1}))
    assert [b.kind for b in marked] == ["caption", "paragraph", "list_item"]


def test_each_caption_text_is_used_once():
    blocks = [_block("Figure 1: a diagram"), _block("Figure 1: a diagram")]
    marked = _mark_captions(blocks, Counter({"Figure 1: a diagram": 1}))
    assert [b.kind for b in marked] == ["caption", "paragraph"]

def _add_toc(doc, entries):
    """A table of contents the way Word stores it: a content control holding the TOC lines."""
    lines = "".join(
        f'<w:p><w:r><w:t>{text}</w:t></w:r><w:r><w:tab/></w:r><w:r><w:t>{page}</w:t></w:r></w:p>'
        for text, page in entries
    )
    doc.element.body.insert(0, parse_xml(
        f'<w:sdt {nsdecls("w")}><w:sdtPr><w:docPartObj><w:docPartGallery w:val="Table of Contents"/>'
        f'</w:docPartObj></w:sdtPr><w:sdtContent>'
        f'<w:p><w:pPr><w:pStyle w:val="TOCHeading"/></w:pPr><w:r><w:t>Contents</w:t></w:r></w:p>{lines}'
        f'</w:sdtContent></w:sdt>'
    ))


def test_the_table_of_contents_stays_out(make_docx, data_dir, word_tokens):
    def build(doc):
        _add_toc(doc, [("Intro", 1), ("Details", 2)])
        _lecture(doc)

    result = process(make_docx(build=build), "w10", "c1")
    texts = [b.text for b in result.parsed.blocks]
    assert "Contents" not in texts and "Intro 1" not in texts and "Details 2" not in texts
    assert [b.text for b in result.parsed.blocks if b.kind == "heading"] == ["Intro", "Details"]


def _add_cover_page(doc, title, author):
    """A cover page the way Word stores it: a content control marked "Cover Pages"."""
    doc.element.body.insert(0, parse_xml(
        f'<w:sdt {nsdecls("w")}><w:sdtPr><w:docPartObj><w:docPartGallery w:val="Cover Pages"/>'
        f'</w:docPartObj></w:sdtPr><w:sdtContent>'
        f'<w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr><w:r><w:t>{title}</w:t></w:r></w:p>'
        f'<w:p><w:r><w:t>{author}</w:t></w:r></w:p>'
        f'</w:sdtContent></w:sdt>'
    ))


def test_the_cover_page_stays_out_of_blocks_and_heading_paths(make_docx, data_dir, word_tokens):
    def build(doc):
        _add_cover_page(doc, "Cover Title", "Cover Author")
        _lecture(doc)

    result = process(make_docx(build=build), "w11", "c1")
    assert not any("Cover" in b.text for b in result.parsed.blocks)
    assert not any("Cover Title" in b.heading_path for b in result.parsed.blocks)


def test_hidden_text_stays_out(make_docx, data_dir, word_tokens):
    def build(doc):
        doc.add_heading("Intro", 1)
        paragraph = doc.add_paragraph("Shown before ")
        paragraph.add_run("SECRET ").font.hidden = True
        paragraph.add_run("shown after.")
        doc.add_paragraph("Whole paragraph hidden.").runs[0].font.hidden = True
        doc.add_paragraph("Last visible paragraph.")

    result = process(make_docx(build=build), "w12", "c1")
    texts = [b.text for b in result.parsed.blocks]
    assert "Shown before shown after." in texts and "Last visible paragraph." in texts
    assert not any("SECRET" in t or "Whole paragraph hidden" in t for t in texts)


def test_a_real_heading_with_the_same_words_as_a_toc_line_is_kept():
    blocks = [_block("Intro"), _block("Intro", "heading"), _block("Body")]
    kept = _drop_word_extras(blocks, Counter({"Intro": 1}))
    assert [(b.kind, b.text) for b in kept] == [("heading", "Intro"), ("paragraph", "Body")]


def test_a_dropped_heading_is_taken_out_of_the_paths_below_it():
    def block(seq, kind, text, path):
        return Block(seq=seq, kind=kind, text=text, heading_path=path, loc=Location(), lang="en")

    blocks = [
        block(0, "heading", "Cover", ["t", "Cover"]),
        block(1, "heading", "Intro", ["t", "Cover", "Intro"]),
        block(2, "paragraph", "Body", ["t", "Cover", "Intro"]),
    ]
    kept = _drop_word_extras(blocks, Counter({"Cover": 1}))
    assert [(b.text, b.heading_path) for b in kept] == [("Intro", ["t", "Intro"]), ("Body", ["t", "Intro"])]
def _commands(doc):
    """Shell commands the way the Bandit notes have them: one Consolas paragraph per line."""
    def code_line(text):
        doc.add_paragraph().add_run(text).font.name = "Consolas"

    doc.add_heading("Level 12", 2)
    doc.add_paragraph("Commands Used:")
    code_line("mktemp -d          # make a work folder")
    code_line("cd /tmp/work")
    code_line("")                                           # a blank line inside the commands
    code_line("ls -la")
    doc.add_paragraph("Explanation follows here.")


def test_monospace_commands_become_one_code_block_with_word_spacing(make_docx, data_dir, word_tokens):
    result = process(make_docx(build=_commands), "w13", "c1")
    code = [b for b in result.parsed.blocks if b.kind == "code"]
    assert [b.text for b in code] == ["mktemp -d          # make a work folder\ncd /tmp/work\n\nls -la"]
    assert code[0].lang == "code"
    texts = [b.text for b in result.parsed.blocks]
    assert "Commands Used:" in texts and "Explanation follows here." in texts


def test_commands_in_a_file_without_a_normal_style_become_code(make_docx, data_dir, word_tokens):
    def build(doc):
        doc.styles["Normal"].element.attrib.pop(qn("w:default"))   # like the Bandit notes: no default style
        _commands(doc)

    result = process(make_docx(build=build), "w14", "c1")
    assert [b.kind for b in result.parsed.blocks].count("code") == 1


def test_a_file_typed_all_in_a_monospace_font_is_not_turned_into_code(make_docx, data_dir, word_tokens):
    def build(doc):
        doc.styles["Normal"].font.name = "Courier New"
        doc.add_heading("Notes", 1)
        doc.add_paragraph("Arrays keep items next to each other in memory.")
        doc.add_paragraph("Linked lists keep a pointer to the next item.")

    result = process(make_docx(build=build), "w15", "c1")
    assert "code" not in [b.kind for b in result.parsed.blocks]
def test_paragraph_and_code_blocks_of_one_run_become_one_code_block():
    blocks = [_block("Commands Used:"), _block("ls -la"), _block('echo "<p>" | nc localhost 30000', "code"),
              _block("After.")]
    marked = _mark_code(blocks, [["ls -la", 'echo "<p>" | nc localhost 30000']])
    assert [(b.kind, b.text) for b in marked] == [
        ("paragraph", "Commands Used:"), ("code", 'ls -la\necho "<p>" | nc localhost 30000'), ("paragraph", "After.")]


def test_code_text_comes_from_word_with_indentation_and_lines_the_cleaner_dropped():
    blocks = [_block("int main() {"), _block("return 0;"), _block("After.")]   # "}" was cleaned away
    marked = _mark_code(blocks, [["int main() {", "    return 0;", "}"]])
    assert [(b.kind, b.text) for b in marked] == [("code", "int main() {\n    return 0;\n}"), ("paragraph", "After.")]
def _bold_line(doc, text, size):
    run = doc.add_paragraph().add_run(text)
    run.bold, run.font.size = True, Pt(size)


def test_bold_titles_become_headings_in_a_file_without_heading_styles(make_docx, data_dir, word_tokens):
    def build(doc):                                         # like Results.docx: no heading style at all
        _bold_line(doc, "Outcomes", 18)
        _bold_line(doc, "Pain score 24 hours", 14)
        doc.add_paragraph("Pain was lower on the first day.")
        _bold_line(doc, "Pain score 48 hours", 14)
        doc.add_paragraph("Pain was the same on the second day.")

    result = process(make_docx(build=build), "w16", "c1")
    headings = [(b.text, b.heading_path[1:]) for b in result.parsed.blocks if b.kind == "heading"]
    assert headings == [("Outcomes", ["Outcomes"]),
                        ("Pain score 24 hours", ["Outcomes", "Pain score 24 hours"]),
                        ("Pain score 48 hours", ["Outcomes", "Pain score 48 hours"])]
    chunks = {c.heading_path[-1]: c.text for c in result.chunked.chunks}
    assert chunks["Pain score 48 hours"] == "Pain was the same on the second day."


def _text_picture(path, lines):
    """A screenshot-like picture: black text on white."""
    image = Image.new("RGB", (900, 60 + 50 * len(lines)), "white")
    draw = ImageDraw.Draw(image)
    for k, line in enumerate(lines):
        draw.text((20, 30 + 50 * k), line, fill="black")
    image.save(path)
    return path


def test_a_picture_adds_no_text_of_its_own(make_docx, data_dir, word_tokens, tmp_path):
    """No OCR (figures guide): a picture without a caption leaves only a "[Figure]" block with its id."""
    picture = _text_picture(tmp_path / "shot.png", ["Binary search needs a sorted array"])

    def build(doc):
        doc.add_heading("Searching", 1)
        doc.add_paragraph("Before the picture.")
        doc.add_picture(str(picture))
        doc.add_paragraph("After the picture.")
    result = process(make_docx(build=build), "w18", "c1")
    blocks = result.parsed.blocks
    texts = [b.text for b in blocks]
    i = texts.index("Before the picture.")
    assert (blocks[i + 1].kind, blocks[i + 1].text, blocks[i + 1].figure_id) == ("figure", "[Figure]", "fig0")
    assert texts[i + 2] == "After the picture."
    assert not any("Binary search" in t for t in texts)
    assert (result.status, result.warnings) == ("ok", [])
    assert ["w18:fig0"] in [c.figure_ids for c in result.chunked.chunks]


def test_a_word_caption_takes_the_id_of_the_picture_above_it(make_docx, data_dir, word_tokens, tmp_path):
    picture = _text_picture(tmp_path / "tree.png", ["root"])

    def build(doc):
        doc.add_heading("Trees", 1)
        doc.add_paragraph("A binary tree:")
        doc.add_picture(str(picture))
        doc.add_paragraph("Figure 1: a binary tree", style="Caption")
    result = process(make_docx(build=build), "w19", "c1")
    blocks = result.parsed.blocks
    assert [(b.kind, b.text, b.figure_id) for b in blocks if b.figure_id] == [
        ("caption", "Figure 1: a binary tree", "fig0")]                  # no "[Figure]" left beside it
    assert ["w19:fig0"] in [c.figure_ids for c in result.chunked.chunks]


def test_link_captions_below_then_above_and_never_a_table_caption():
    def figure(n):
        return Block(seq=0, kind="figure", text="[Figure]", heading_path=["t"], loc=Location(), figure_id=f"fig{n}")
    blocks = [figure(0), _block("Figure 1: below", "caption"),
              _block("Figure 2: above", "caption"), figure(1),
              _block("Text."), figure(2), _block("Table 1: marks", "caption")]
    out = _link_captions(blocks)
    assert [(b.kind, b.text, b.figure_id) for b in out] == [
        ("caption", "Figure 1: below", "fig0"), ("caption", "Figure 2: above", "fig1"),
        ("paragraph", "Text.", None), ("figure", "[Figure]", "fig2"), ("caption", "Table 1: marks", None)]


# ---------------------------------------------------------------------------------------------------
# PART C: flowcharts drawn with Word shapes (docx_flowchart.py): boxes, arrows, labels -> one text block
# ---------------------------------------------------------------------------------------------------
_EMU = 12700
_DRAWING_NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
               'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
               'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
               'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
               'xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup" '
               'xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas" '
               'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"')
_URI = {"wsp": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
        "wgp": "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup",
        "wpc": "http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas"}


def _emu(points):
    return int(round(points * _EMU))


def _shape(prst, x, y, w, h, text=None, *, line=False, heads=(False, True), flip=(False, False), sid=None,
           glue=None):
    """One Word shape (wps:wsp). In a group or canvas (x, y) is its place; at the top level the anchor places it."""
    flips = (' flipH="1"' if flip[0] else "") + (' flipV="1"' if flip[1] else "")
    nv = f'<wps:cNvPr id="{sid}" name="Shape {sid}"/>' if sid else ""
    if line:
        st = f'<a:stCxn id="{glue[0]}" idx="0"/>' if glue else ""
        en = f'<a:endCxn id="{glue[1]}" idx="0"/>' if glue else ""
        ends = "".join(f'<a:{end} type="triangle"/>' for end, on in zip(("headEnd", "tailEnd"), heads) if on)
        nv += f'<wps:cNvCnPr>{st}{en}</wps:cNvCnPr>'
        look = f'<a:ln w="12700"><a:solidFill><a:srgbClr val="000000"/></a:solidFill>{ends}</a:ln>'
    else:
        nv += '<wps:cNvSpPr/>'
        look = '<a:ln w="12700"><a:solidFill><a:srgbClr val="000000"/></a:solidFill></a:ln>'
    box = ("<wps:txbx><w:txbxContent>" + "".join(f"<w:p><w:r><w:t>{t}</w:t></w:r></w:p>" for t in text)
           + "</w:txbxContent></wps:txbx>") if text else ""
    return (f'<wps:wsp>{nv}<wps:spPr><a:xfrm{flips}><a:off x="{_emu(x)}" y="{_emu(y)}"/>'
            f'<a:ext cx="{_emu(w)}" cy="{_emu(h)}"/></a:xfrm><a:prstGeom prst="{prst}"><a:avLst/></a:prstGeom>{look}'
            f'</wps:spPr>{box}<wps:bodyPr/></wps:wsp>')


def _drawing(paragraph, kind, inner, x, y, w, h, inline=False):
    """Put a drawing in a paragraph: x from the text's left edge, y below the paragraph's top (points)."""
    graphic = f'<a:graphic><a:graphicData uri="{_URI[kind]}">{inner}</a:graphicData></a:graphic>'
    size = f'<wp:extent cx="{_emu(w)}" cy="{_emu(h)}"/>'
    if inline:
        body = f'<wp:inline>{size}<wp:docPr id="900" name="Canvas"/>{graphic}</wp:inline>'
    else:
        body = (f'<wp:anchor simplePos="0" relativeHeight="1" behindDoc="0" locked="0" layoutInCell="1" '
                f'allowOverlap="1"><wp:simplePos x="0" y="0"/>'
                f'<wp:positionH relativeFrom="column"><wp:posOffset>{_emu(x)}</wp:posOffset></wp:positionH>'
                f'<wp:positionV relativeFrom="paragraph"><wp:posOffset>{_emu(y)}</wp:posOffset></wp:positionV>'
                f'{size}<wp:wrapNone/><wp:docPr id="{abs(hash(inner)) % 100000}" name="Shape"/>{graphic}</wp:anchor>')
    paragraph._p.append(parse_xml(f'<w:r {_DRAWING_NS}><mc:AlternateContent><mc:Choice Requires="wps">'
                                  f'<w:drawing>{body}</w:drawing></mc:Choice></mc:AlternateContent></w:r>'))


# "Is n > 0?": the kind of program flowchart students draw. Shapes: name -> (prst, x, y, w, h, text) in points.
_FLOW_BOXES = {
    "start": ("flowChartTerminator", 150, 0, 120, 30, ["Start"]),
    "input": ("flowChartInputOutput", 140, 60, 140, 34, ["Read number n"]),
    "check": ("flowChartDecision", 145, 125, 130, 70, ["Is n > 0?"]),
    "pos": ("flowChartProcess", 20, 235, 130, 34, ['Print "positive"']),
    "neg": ("flowChartProcess", 270, 235, 130, 34, ['Print "not positive"']),
    "end": ("flowChartTerminator", 150, 310, 120, 30, ["End"]),
}
_FLOW_LINES = [  # prst, x, y, w, h, flips, arrowheads (start, end)
    ("straightConnector1", 210, 30, 0, 30, (False, False), (False, True)),
    ("straightConnector1", 210, 94, 0, 31, (False, True), (True, False)),     # drawn upward, head at its start
    ("bentConnector2", 85, 160, 60, 75, (True, False), (False, True)),        # elbow, drawn right to left
    ("bentConnector2", 275, 160, 60, 75, (False, False), (False, True)),
    ("bentConnector2", 85, 269, 65, 56, (False, False), (False, True)),
    ("bentConnector2", 270, 269, 65, 56, (True, False), (False, True)),
]
_FLOW_LABELS = [("Yes", 95, 140), ("No", 300, 140)]
_FLOW_ARROWS = ['- Start → Read number n', '- Read number n → Is n > 0?',
                '- Is n > 0? → Print "positive" [Yes]', '- Is n > 0? → Print "not positive" [No]',
                '- Print "positive" → End', '- Print "not positive" → End']


def _arrows(chart):
    return chart.text.split("Arrows:\n")[1].splitlines()


def _loose_flowchart(doc, boxes=_FLOW_BOXES):
    """Each shape anchored to its own empty paragraph, like Word does when shapes are drawn one by one."""
    doc.add_heading("Selection", 1)
    doc.add_paragraph("The flowchart below checks whether a number is positive.")
    holders = [doc.add_paragraph() for _ in range(8)] + [doc.add_paragraph("(see below)")]
    holders += [doc.add_paragraph() for _ in range(7)]
    step = 11 * 1.2207 * 276 / 240 + 10        # one empty paragraph: Calibri 11 pt, this template's spacing

    def put(inner, x, y, w, h):
        k = min(int(y // step), len(holders) - 1)
        _drawing(holders[k], "wsp", inner, x, y - k * step, w, h)
    for prst, x, y, w, h, text in boxes.values():
        put(_shape(prst, 0, 0, w, h, text), x, y, w, h)
    for prst, x, y, w, h, flip, heads in _FLOW_LINES:
        put(_shape(prst, 0, 0, w, h, line=True, flip=flip, heads=heads), x, y, w, h)
    for text, x, y in _FLOW_LABELS:
        put(_shape("rect", 0, 0, 30, 16, [text]), x, y, 30, 16)
    doc.add_paragraph("Figure 1: Checking if a number is positive")


def test_a_flowchart_of_loose_shapes_is_read_with_its_arrows_and_labels(make_docx):
    charts = read_flowcharts(make_docx(build=_loose_flowchart))
    assert len(charts) == 1
    assert _arrows(charts[0]) == _FLOW_ARROWS
    assert charts[0].text.startswith(FLOWCHART_HEADER + "\n- Start\n- Read number n\n- Is n > 0?")
    assert {"Start", "Is n > 0?", "Yes", "No", "End"} <= set(charts[0].texts)    # to find Docling's copies


def test_a_grouped_flowchart_is_read_in_the_group_units(make_docx):
    def build(doc):
        doc.add_paragraph("The flowchart below checks whether a number is positive.")
        def c(x, y, w, h):                     # the group's own units: 2 per point, starting at (20, -10)
            return 2 * x + 20, 2 * y - 10, 2 * w, 2 * h
        inner = [_shape(p, *c(x, y, w, h), t, sid=k) for k, (p, x, y, w, h, t) in enumerate(_FLOW_BOXES.values(), 1)]
        inner += [_shape(p, *c(x, y, w, h), line=True, flip=f, heads=hd, sid=20 + k)
                  for k, (p, x, y, w, h, f, hd) in enumerate(_FLOW_LINES)]
        inner += [_shape("rect", *c(x, y, 30, 16), [t], sid=40 + k) for k, (t, x, y) in enumerate(_FLOW_LABELS)]
        group = (f'<wpg:wgp><wpg:cNvGrpSpPr/><wpg:grpSpPr><a:xfrm><a:off x="0" y="0"/>'
                 f'<a:ext cx="{_emu(420)}" cy="{_emu(340)}"/><a:chOff x="{_emu(20)}" y="{_emu(-10)}"/>'
                 f'<a:chExt cx="{_emu(840)}" cy="{_emu(680)}"/></a:xfrm></wpg:grpSpPr>{"".join(inner)}</wpg:wgp>')
        _drawing(doc.add_paragraph(), "wgp", group, 30, 6, 420, 340)
    charts = read_flowcharts(make_docx(build=build))
    assert [_arrows(c) for c in charts] == [_FLOW_ARROWS]


def test_glued_connectors_join_the_shapes_they_are_glued_to(make_docx):
    def build(doc):
        shapes = [_shape("flowChartProcess", 10, 10, 100, 30, ["Enter password"], sid=1),
                  _shape("flowChartDecision", 200, 0, 110, 50, ["Correct?"], sid=2),
                  _shape("flowChartTerminator", 380, 10, 100, 30, ["Dashboard"], sid=3),
                  # drawn far from the shapes: only Word's glue says what they join
                  _shape("straightConnector1", 10, 100, 50, 0, line=True, sid=11, glue=(1, 2)),
                  _shape("straightConnector1", 200, 100, 50, 0, line=True, sid=12, glue=(2, 3))]
        _drawing(doc.add_paragraph(), "wpc", "<wpc:wpc>" + "".join(shapes) + "</wpc:wpc>", 0, 0, 500, 120,
                 inline=True)
    charts = read_flowcharts(make_docx(build=build))
    assert [_arrows(c) for c in charts] == [["- Enter password → Correct?", "- Correct? → Dashboard"]]


def test_shapes_without_arrows_are_not_a_flowchart(make_docx):
    def build(doc):
        p = doc.add_paragraph("Read these before the first lab.")
        _drawing(p, "wsp", _shape("rect", 0, 0, 150, 40, ["Labs start at 9"]), 0, 20, 150, 40)
        _drawing(p, "wsp", _shape("roundRect", 0, 0, 150, 40, ["Bring your laptop"]), 220, 20, 150, 40)
        _drawing(p, "wsp", _shape("line", 0, 0, 380, 0, line=True, heads=(False, False)), 0, 80, 380, 0)
    assert read_flowcharts(make_docx(build=build)) == []
    assert read_flowcharts(make_docx(build=_lecture)) == []


def test_a_text_box_laid_on_an_empty_diamond_names_the_diamond(make_docx):
    boxes = dict(_FLOW_BOXES, check=("flowChartDecision", 145, 125, 130, 70, None),
                 check_words=("rect", 175, 150, 70, 20, ["Is n > 0?"]))
    charts = read_flowcharts(make_docx(build=lambda doc: _loose_flowchart(doc, boxes)))
    assert [_arrows(c) for c in charts] == [_FLOW_ARROWS]


def test_a_flowchart_replaces_the_loose_words_of_its_shapes():
    def block(ref, text, section="Selection"):
        return Block(seq=0, kind="paragraph", text=text, heading_path=["t", section], loc=Location(),
                     extra={"ref": ref})
    blocks = [block("#/texts/0", "Intro."),
              block("#/texts/1", "Records removed"), block("#/texts/2", "before screening"),   # one paragraph,
              block("#/texts/3", "(n = 12)"), block("#/texts/4", "A body line between."),     # split by Docling
              block("#/texts/5", "Records screened"),
              block("#/texts/6", "Figure 1: the flow")]
    blocks += [block(f"#/texts/{n}", f"Later text {n}.", "Later") for n in range(7, 11)]
    blocks += [block("#/texts/11", "Records screened", "Later")]     # same words in a shape further on: kept
    chart = Flowchart(text=FLOWCHART_HEADER + "\n- Records removed before screening\nArrows:\n- a → b",
                      texts=["Records removed before screening:", "(n = 12)", "Records screened"])
    shape_refs = {"#/texts/1", "#/texts/2", "#/texts/3", "#/texts/5", "#/texts/11"}
    out, taken = _add_flowcharts(blocks, [chart], shape_refs)
    assert [(b.kind, b.text.splitlines()[0]) for b in out][:4] == [
        ("paragraph", "Intro."), ("figure_text", FLOWCHART_HEADER), ("paragraph", "A body line between."),
        ("paragraph", "Figure 1: the flow")]
    assert out[-1].text == "Records screened" and len(out) == 9
    assert out[1].heading_path == ["t", "Selection"] and out[1].extra["source"] == "shapes"
    assert taken == {"#/texts/1", "#/texts/2", "#/texts/3", "#/texts/5"}


def test_a_word_flowchart_becomes_one_figure_text_block_with_its_arrows(make_docx, data_dir, word_tokens):
    result = process(make_docx(build=_loose_flowchart), "w20", "c1")
    blocks = result.parsed.blocks
    texts = [b.text for b in blocks]
    i = texts.index("The flowchart below checks whether a number is positive.")
    chart = blocks[i + 1]
    assert chart.kind == "figure_text" and chart.heading_path[-1] == "Selection"
    assert chart.text.split("Arrows:\n")[1].splitlines() == _FLOW_ARROWS
    assert not {"Start", "Read number n", "Yes", "No", "End"} & set(texts)    # no loose shape words left
    assert "Figure 1: Checking if a number is positive" in texts[i + 2:]
    assert (result.status, result.warnings) == ("ok", [])
