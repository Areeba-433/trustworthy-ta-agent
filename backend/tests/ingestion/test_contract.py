from typing import Any , get_args

import pytest
from pydantic import ValidationError

from app.ingestion.contract import Block, Location, ParsedDocument, QualityReport, SourceType
from app.ingestion.registry import registered


def _valid(**changes: Any) -> dict[str, Any]:
    data: dict[str, Any] = dict(resource_id="r", course_id="c", file_name="a.pdf", file_sha256="0" * 64,
                source_type="pdf", title="T", parser="p", parser_version="1",
                blocks=[Block(seq=0, kind="paragraph", text="x", heading_path=["T"], loc=Location(page=1))],
                quality=QualityReport(status="ok", units_total=1, chars_total=1))
    return data | changes


def test_a_valid_document_is_accepted():
    ParsedDocument(**_valid())


@pytest.mark.parametrize("changes", [
    {"blocks": [Block(seq=1, kind="paragraph", text="x", heading_path=["T"], loc=Location(page=1))]},
    {"blocks": [Block(seq=0, kind="paragraph", text="x", heading_path=["Other"], loc=Location(page=1))]},
    {"blocks": [Block(seq=0, kind="paragraph", text="x", heading_path=["T"], loc=Location())]},
    {"quality": QualityReport(status="failed", warnings=["w"], units_total=0, chars_total=0)},
    {"blocks": []},
], ids=["seq-gap", "path-without-title", "pdf-without-page", "failed-with-blocks", "ok-without-blocks"])
def test_broken_rules_are_rejected(changes):
    with pytest.raises(ValidationError):
        ParsedDocument(**_valid(**changes))


def test_every_file_type_has_exactly_one_department():
    assert set(get_args(SourceType)) == set(registered())