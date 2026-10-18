"""Build ParsedDocuments in one place, so every loader sets numbering, status and counts the same way."""
from app.ingestion.cleaning.common import title_from_filename
from app.ingestion.contract import ParsedDocument, QualityReport, ResourceMeta, SourceType


def failed_document(meta: ResourceMeta, source_type: SourceType, reason: str) -> ParsedDocument:
    return ParsedDocument(
        resource_id=meta.resource_id, course_id=meta.course_id, file_name=meta.file_name,
        file_sha256=meta.file_sha256, source_type=source_type,
        title=title_from_filename(meta.file_name), parser="none", parser_version="-", blocks=[],
        quality=QualityReport(status="failed", warnings=[reason], units_total=0, chars_total=0),
    )