"""Build ParsedDocuments in one place, so every loader sets numbering, status and counts the same way."""
from collections.abc import Sequence

from app.ingestion import messages
from app.ingestion.cleaning.common import title_from_filename
from app.ingestion.contract import Block, ParsedDocument, QualityReport, ResourceMeta, SourceType


class FileRefused(Exception):
    """Raise inside a loader to fail the file with a message from messages.py that the teacher can act on."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def failed_document(meta: ResourceMeta, source_type: SourceType, reason: str) -> ParsedDocument:
    return ParsedDocument(
        resource_id=meta.resource_id, course_id=meta.course_id, file_name=meta.file_name,
        file_sha256=meta.file_sha256, source_type=source_type,
        title=title_from_filename(meta.file_name), parser="none", parser_version="-", blocks=[],
        quality=QualityReport(status="failed", warnings=[reason], units_total=0, chars_total=0),
    )


def parsed_document(
    meta: ResourceMeta, *, title: str, blocks: list[Block], parser: str, parser_version: str,
    units_total: int, problems: Sequence[str] = (), notes: Sequence[str] = (),
) -> ParsedDocument:
    """A loader's answer.

    problems: content may be missing or wrong, so the status drops to "degraded".
    notes: worth telling the teacher, but nothing is missing, so the status stays "ok".
    No blocks at all means nothing readable came out, so the document fails.
    """
    if isinstance(problems, str) or isinstance(notes, str):
        raise TypeError("problems and notes are lists of messages, not one message")
    if not blocks:
        return failed_document(meta, meta.precheck.source_type, messages.NO_TEXT_FILE)
    blocks = [b.model_copy(update={"seq": i}) for i, b in enumerate(blocks)]   # rules may have dropped some
    return ParsedDocument(
        resource_id=meta.resource_id, course_id=meta.course_id, file_name=meta.file_name,
        file_sha256=meta.file_sha256, source_type=meta.precheck.source_type, title=title,
        parser=parser, parser_version=parser_version, blocks=blocks,
        quality=QualityReport(
            status="degraded" if problems else "ok",
            warnings=list(dict.fromkeys([*problems, *notes])),    # problems first, repeats dropped
            units_total=units_total,
            chars_total=sum(len(b.text) for b in blocks),
        ),
    )