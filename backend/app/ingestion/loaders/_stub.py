"""A placeholder answer every department can return until its real code is written."""
from app.ingestion.cleaning.common import title_from_filename
from app.ingestion.contract import (LOCATION_FIELD, Block, Location, ParsedDocument,
                                    QualityReport, ResourceMeta)


def stub_document(meta: ResourceMeta, kind: str = "paragraph") -> ParsedDocument:
    source_type = meta.precheck.source_type
    field = LOCATION_FIELD[source_type]
    title = title_from_filename(meta.file_name)
    return ParsedDocument(
        resource_id=meta.resource_id, course_id=meta.course_id, file_name=meta.file_name,
        file_sha256=meta.file_sha256, source_type=source_type, title=title,
        parser="stub", parser_version="0",
        blocks=[Block(seq=0, kind=kind, text=f"stub output for {meta.file_name}", heading_path=[title],
                      loc=Location(**({field: 1} if field else {})))],
        quality=QualityReport(status="ok", units_total=1, chars_total=10),
    )