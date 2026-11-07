"""mark_exponents(): a power of ten keeps its exponent: "1.7x10^308", not "1.7x10308"."""
from app.ingestion.contract import Block, Location
from app.ingestion.pdf_exponents import mark_exponents
from conftest import write_pdf


def _block(text: str, kind: str = "paragraph") -> Block:
    return Block(seq=0, kind=kind, text=text, heading_path=["Book"], loc=Location(page=1))


def _page(tmp_path, raised: bool = True):
    """Book page 75: "from 1.7x10-308 to 1.7x10308", the exponents printed 2.5 points higher (Ts: text rise)."""
    rise = 2.5 if raised else 0
    content = (f"BT /F1 10 Tf 72 700 Td (handles numbers from 1.7x10) Tj {rise} Ts (-308) Tj 0 Ts (to 1.7x10) Tj "
               f"{rise} Ts (308) Tj 0 Ts (in 10308 places) Tj ET")
    return write_pdf(tmp_path / "exponents.pdf", [content], fonts=("Times-Roman",))


def test_a_raised_exponent_of_ten_gets_a_caret(tmp_path):
    path = _page(tmp_path)
    [block] = mark_exponents([_block("handles numbers from 1.7x10-308 to 1.7x10308 in 10308 places")], path)
    assert block.text == "handles numbers from 1.7x10^-308 to 1.7x10^308 in 10308 places"


def test_in_a_table_too(tmp_path):
    """Book page 81: the table of floating-point types, "3.4 x 10 -38" in its cells."""
    path = _page(tmp_path)
    [block] = mark_exponents([_block("| double | 1.7 x 10 -308 | 1.7 x 10 308 |", kind="table")], path)
    assert block.text == "| double | 1.7 x 10^-308 | 1.7 x 10^308 |"


def test_digits_the_pdf_does_not_raise_stay_as_they_are(tmp_path):
    path = _page(tmp_path, raised=False)
    text = "handles numbers from 1.7x10-308 to 1.7x10308 in 10308 places"
    assert mark_exponents([_block(text)], path)[0].text == text


def test_code_is_never_changed(tmp_path):
    path = _page(tmp_path)
    assert mark_exponents([_block("double d = 1.7x10308;", kind="code")], path)[0].text == "double d = 1.7x10308;"
