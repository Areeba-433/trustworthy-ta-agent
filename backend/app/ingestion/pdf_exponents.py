"""mark_exponents(): a power of ten keeps its exponent as an exponent.

The PDF prints "1.7×10³⁰⁸" with the exponent raised and smaller; its text layer, and so Docling, has only the
characters: "1.7x10308", which reads as a different number. A student who asks for the range of a double would get
it wrong. The exponent is written with a caret instead: "1.7x10^308", "times 10^-5". In the OOP book: pages 74, 75,
76 and 81 (10 places, the table of floating-point types among them).

Only powers of ten in scientific notation are changed ("x 10", "×10", "times 10" followed by the raised digits), and
only where the PDF really raises those digits: pdfium gives each character's baseline.
"""
import ctypes
import logging
import re
from collections.abc import Sequence
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from app.ingestion.contract import Block

logger = logging.getLogger(__name__)

_POWER = re.compile(r"((?:x|×|times)\s?10)\s?(-?\d+)")   # Docling's text: "1.7x10-308", "3.4 x 10 -38", "times 103"
_RAISED = (1.5, 4.5)    # points: how much higher than the "10" an exponent's baseline stands
_KINDS = {"paragraph", "list_item", "table", "caption"}
_MINUS = str.maketrans({"–": "-", "−": "-", "—": "-"})


def mark_exponents(blocks: Sequence[Block], path: Path) -> list[Block]:
    """The same blocks; in text, a power of ten whose exponent the PDF raises gets a caret: 10^308."""
    pages = sorted({b.loc.page for b in blocks if b.kind in _KINDS and b.loc.page and _POWER.search(b.text)})
    if not pages:
        return list(blocks)
    pdf = pdfium.PdfDocument(str(path))
    try:
        raised = {page: _exponents(pdf, page) for page in pages if 1 <= page <= len(pdf)}
    finally:
        pdf.close()
    out, marked = [], 0
    for block in blocks:
        exponents = raised.get(block.loc.page) if block.kind in _KINDS else None
        if exponents:
            text = _POWER.sub(lambda m: f"{m.group(1)}^{m.group(2)}" if m.group(2) in exponents else m.group(0),
                              block.text)
            if text != block.text:
                marked += 1
                block = block.model_copy(update={"text": text})
        out.append(block)
    logger.info("powers of ten: exponents marked in %d blocks", marked)
    return out


def _exponents(pdf: pdfium.PdfDocument, page_no: int) -> set[str]:
    """The exponents the page raises after a "10": "-308", "308", "3"."""
    page = pdf[page_no - 1]
    textpage = page.get_textpage()
    try:
        found, before, base, run = set(), "", None, ""
        for i in range(textpage.count_chars()):
            ch = textpage.get_text_range(i, 1).translate(_MINUS)
            x, y = ctypes.c_double(), ctypes.c_double()
            pdfium_c.FPDFText_GetCharOrigin(textpage.raw, i, ctypes.byref(x), ctypes.byref(y))
            if base is not None and _RAISED[0] <= y.value - base <= _RAISED[1] and (ch.isdigit() or ch == "-"):
                run += ch                                # still raised: the exponent goes on
                continue
            if run:
                found.add(run)
            run, base = "", None
            if before.endswith("1") and ch == "0":       # a "10": what follows may be raised
                base = y.value
            before = (before + ch)[-2:]
        if run:
            found.add(run)
        return {e for e in found if re.fullmatch(r"-?\d+", e)}
    finally:
        textpage.close()
        page.close()
