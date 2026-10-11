"""Builds textbook.pdf and textbook.expected.json for test_fast_pdf.py. Only needed to rebuild them.

    pip install reportlab        (for this script only; it is not in requirements.txt)
    python tests/ingestion/samples/fast_pdf/make_textbook.py tests/ingestion/samples/fast_pdf/textbook.pdf 5

A textbook-like PDF with everything real books have, plus what is in it.

Per chapter: a chapter heading, numbered sections, an unnumbered bold subsection, book-style paragraphs
(first-line indent, no gap), bullet and numbered lists, a C++ listing in Courier, a fully ruled table,
a table with only horizontal rules, a vector figure with labels and a caption, a raster figure, a
footnote, and a two-column glossary page. A running header names the chapter; page numbers alternate
sides. Writes the PDF and, beside it, .expected.json: every block with its kind, text, heading path and page
(long paragraphs keep only their start and end).
"""
import io
import json
import random
import sys
from pathlib import Path

from PIL import Image as PILImage, ImageDraw
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame, Image, KeepTogether, NextPageTemplate,
                                PageBreak, PageTemplate, Paragraph, Preformatted, Spacer, Table, TableStyle)
from reportlab.platypus.flowables import Flowable

OUT = Path(sys.argv[1])
CHAPTERS = int(sys.argv[2]) if len(sys.argv) > 2 else 6
TITLE = "Programming Fundamentals"
rng = random.Random(7)

ss = getSampleStyleSheet()
BODY = ParagraphStyle("Body", parent=ss["BodyText"], fontName="Times-Roman", fontSize=10.5, leading=13.5,
                      alignment=TA_JUSTIFY, firstLineIndent=14, spaceBefore=0, spaceAfter=0)
FIRST = ParagraphStyle("First", parent=BODY, firstLineIndent=0)
CHAP = ParagraphStyle("Chap", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=22, leading=26,
                      spaceBefore=0, spaceAfter=18)
SEC = ParagraphStyle("Sec", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=14, leading=17,
                     spaceBefore=14, spaceAfter=6)
SUB = ParagraphStyle("Sub", parent=BODY, fontName="Times-Bold", firstLineIndent=0, spaceBefore=8, spaceAfter=2)
ITEM = ParagraphStyle("Item", parent=BODY, firstLineIndent=0, leftIndent=18, bulletIndent=6, spaceBefore=1)
CAPTION = ParagraphStyle("Caption", parent=BODY, fontName="Times-Italic", fontSize=9, leading=11,
                         firstLineIndent=0, alignment=0, spaceBefore=4, spaceAfter=10)
CODE = ParagraphStyle("Code", fontName="Courier", fontSize=8.5, leading=10.5, leftIndent=12,
                      spaceBefore=6, spaceAfter=8)
NOTE = ParagraphStyle("Note", parent=BODY, fontSize=8, leading=9.5, firstLineIndent=0)
GLOSS = ParagraphStyle("Gloss", parent=BODY, fontSize=9.5, leading=12, firstLineIndent=0, spaceAfter=4,
                       alignment=0)
TITLE_STYLE = ParagraphStyle("BookTitle", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=30, leading=36)

TOPICS = ["Variables", "Loops", "Functions", "Arrays", "Pointers", "Structures", "Recursion", "Strings",
          "Files", "Classes"]
NOUNS = ["value", "counter", "index", "buffer", "pointer", "loop", "function", "array", "string", "record"]
VERBS = ["stores", "updates", "returns", "copies", "checks", "compares", "moves", "prints"]

truth = []          # (kind, text, heading_path, page) in reading order


def sentence(ch, k):
    n1, n2 = rng.choice(NOUNS), rng.choice(NOUNS)
    return (f"The {n1} {rng.choice(VERBS)} the {n2} before the next step, and example {ch}.{k} shows why "
            f"this order matters when the program runs on a small input of {rng.randint(3, 99)} items.")


def paragraph_text(ch, k, sentences=None):
    return " ".join(sentence(ch, k) for _ in range(sentences or rng.randint(3, 6)))


class Mark(Flowable):
    """Zero-size flowable that records the page a truth entry landed on."""
    def __init__(self, index):
        super().__init__()
        self.index = index
        self.width = self.height = 0

    def draw(self):
        pass


class Footnote(Flowable):
    """Zero-size flowable that asks the page to print a footnote at its bottom."""
    def __init__(self, text):
        super().__init__()
        self.text = text
        self.width = self.height = 0

    def draw(self):
        doc.footnotes.append(self.text)


class Book(BaseDocTemplate):
    def __init__(self, filename, **kw):
        super().__init__(filename, **kw)
        self.chapter = ""
        self.footnotes = []
        w, h = A4
        one = Frame(2.2 * cm, 2.2 * cm, w - 4.4 * cm, h - 4.6 * cm, id="one")
        gap = 0.8 * cm
        colw = (w - 4.4 * cm - gap) / 2
        left = Frame(2.2 * cm, 2.2 * cm, colw, h - 4.6 * cm, id="left")
        right = Frame(2.2 * cm + colw + gap, 2.2 * cm, colw, h - 4.6 * cm, id="right")
        self.addPageTemplates([PageTemplate("one", [one], onPageEnd=self.decorate),
                               PageTemplate("two", [left, right], onPageEnd=self.decorate),
                               PageTemplate("title", [one])])

    def decorate(self, canvas, doc):
        canvas.saveState()
        w, h = A4
        canvas.setFont("Times-Italic", 9)
        if self.chapter:
            canvas.drawString(2.2 * cm, h - 1.5 * cm, self.chapter)
        canvas.setFont("Times-Roman", 9)
        num = str(doc.page)
        if doc.page % 2:
            canvas.drawRightString(w - 2.2 * cm, 1.3 * cm, num)
        else:
            canvas.drawString(2.2 * cm, 1.3 * cm, num)
        if self.footnotes:
            canvas.setLineWidth(0.4)
            canvas.line(2.2 * cm, 2.0 * cm, 6 * cm, 2.0 * cm)
            y = 1.75 * cm
            for note in self.footnotes:
                canvas.setFont("Times-Roman", 7.5)
                canvas.drawString(2.2 * cm, y, note)
                y -= 9
            self.footnotes = []
        canvas.restoreState()

    def afterFlowable(self, f):
        if isinstance(f, Mark):
            truth[f.index][3] = self.page
        if isinstance(f, Paragraph) and f.style.name in ("Chap", "Sec"):
            level = 0 if f.style.name == "Chap" else 1
            key = f"h{id(f)}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(f.getPlainText(), key, level=level, closed=True)
            if level == 0:
                self.chapter = f.getPlainText()


story = []


def add(kind, text, path, flowables):
    truth.append([kind, text, list(path), None])
    story.append(Mark(len(truth) - 1))
    story.extend(flowables if isinstance(flowables, list) else [flowables])


def vector_figure(ch):
    d = Drawing(380, 120)
    labels = [f"{rng.choice(NOUNS).title()} {i}" for i in range(1, 4)]
    for i, label in enumerate(labels):
        x = 20 + i * 125
        d.add(Rect(x, 40, 100, 40, strokeColor=colors.black, fillColor=colors.whitesmoke))
        d.add(String(x + 50, 56, label, textAnchor="middle", fontName="Helvetica", fontSize=9))
        if i:
            d.add(Line(x - 25, 60, x, 60, strokeColor=colors.black))
    return d


def raster_figure():
    img = PILImage.new("RGB", (400, 160), "white")
    g = ImageDraw.Draw(img)
    for i in range(8):
        g.rectangle([20 + i * 45, 150 - rng.randint(20, 130), 50 + i * 45, 150], fill=(70, 110, 170))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return Image(buf, width=10 * cm, height=4 * cm)


CODE_SAMPLE = """int sum(const int a[], int n) {
    int total = 0;
    for (int i = 0; i < n; i++) {
        if (a[i] > 0) {
            total += a[i];
        }
    }
    return total;
}"""

add("title", TITLE, [], Paragraph(TITLE, TITLE_STYLE))
add("paragraph", "Original practice text for testing ingestion.", [TITLE],
    Paragraph("Original practice text for testing ingestion.", FIRST))
story += [NextPageTemplate("one"), PageBreak()]

for ch in range(1, CHAPTERS + 1):
    topic = TOPICS[(ch - 1) % len(TOPICS)]
    chap = f"Chapter {ch}: {topic}"
    path = [TITLE, chap]
    add("heading", chap, path[:1], Paragraph(chap, CHAP))
    for sec in range(1, 4):
        sec_title = f"{ch}.{sec} {['Basics', 'In practice', 'Pitfalls'][sec - 1]} of {topic.lower()}"
        spath = path + [sec_title]
        add("heading", sec_title, path, Paragraph(sec_title, SEC))
        for k in range(rng.randint(3, 5)):
            t = paragraph_text(ch, k)
            add("paragraph", t, spath, Paragraph(t, FIRST if k == 0 else BODY))
        if sec == 1:
            items = [f"Use a clear name for every {rng.choice(NOUNS)} in chapter {ch}." for _ in range(3)]
            for it in items:
                add("list_item", it, spath, Paragraph(it, ITEM, bulletText="•"))
            t = paragraph_text(ch, 9, 2)
            add("paragraph", t + "1", spath, Paragraph(t + "<super>1</super>", BODY))
            note = f"1 This rule also holds for the exercises at the end of chapter {ch}."
            add("footnote", note, spath, Footnote(note))
        if sec == 2:
            add("code", CODE_SAMPLE, spath, Preformatted(CODE_SAMPLE, CODE))
            add("caption", f"Listing {ch}.1: Adding the positive values of an array.", spath,
                Paragraph(f"Listing {ch}.1: Adding the positive values of an array.", CAPTION))
            steps = ["Read the input.", "Check every value.", "Print the total."]
            for i, st in enumerate(steps, 1):
                add("list_item", st, spath, Paragraph(st, ITEM, bulletText=f"{i}."))
            rows = [["Operator", "Meaning", "Example"], ["+", "addition", "a + b"],
                    ["%", "remainder", f"{ch + 7} % 3"], ["==", "equal to", "a == b"]]
            t = Table(rows, colWidths=[3 * cm, 4 * cm, 4 * cm])
            t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                                   ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                                   ("FONTNAME", (0, 1), (-1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), 9)]))
            add("table", json.dumps(rows), spath, [KeepTogether([t]), Spacer(0, 8)])
        if sec == 3:
            sub = f"Why {topic.lower()} go wrong"
            add("heading", sub, spath, Paragraph(sub, SUB))
            t = paragraph_text(ch, 5)
            add("paragraph", t, spath + [sub], Paragraph(t, FIRST))
            rows = [["Mistake", "Effect"], ["off by one", "skips a value"], ["no base case", "never stops"]]
            t2 = Table(rows, colWidths=[5 * cm, 5 * cm])
            t2.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 1, colors.black),
                                    ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
                                    ("LINEBELOW", (0, -1), (-1, -1), 1, colors.black),
                                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), 9)]))
            add("table", json.dumps(rows), spath + [sub], [KeepTogether([t2]), Spacer(0, 8)])
            add("figure", "", spath + [sub], [KeepTogether([vector_figure(ch)])])
            add("caption", f"Figure {ch}.1: How the {topic.lower()} pass data along.", spath + [sub],
                Paragraph(f"Figure {ch}.1: How the {topic.lower()} pass data along.", CAPTION))
            add("figure", "", spath + [sub], [raster_figure()])
            add("caption", f"Figure {ch}.2: Running time for eight input sizes.", spath + [sub],
                Paragraph(f"Figure {ch}.2: Running time for eight input sizes.", CAPTION))
            for k in range(2):
                t = paragraph_text(ch, 20 + k)
                add("paragraph", t, spath + [sub], Paragraph(t, BODY))
    # glossary in two columns
    story += [NextPageTemplate("two"), PageBreak()]
    gl = f"Glossary for chapter {ch}"
    add("heading", gl, path, Paragraph(gl, SEC))
    for g in range(14):
        term = f"{rng.choice(NOUNS)} {g + 1}"
        t = f"{term.title()}: " + " ".join(sentence(ch, g) for _ in range(2))
        add("paragraph", t, path + [gl], Paragraph(t, GLOSS))
    story += [NextPageTemplate("one"), PageBreak()]

doc = Book(str(OUT), pagesize=A4, title=TITLE, author="Track 1 test data")
doc.build(story)
expected = [[k, [t[:80], t[-50:]] if k == "paragraph" and len(t) > 140 else t, p, pg]
            for k, t, p, pg in truth if k != "figure"]
OUT.with_suffix(".expected.json").write_text(json.dumps(expected, separators=(",", ":"), ensure_ascii=False))
print("written", OUT, "pages", doc.page, "truth entries", len(truth))
