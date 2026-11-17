"""Build ParsedDocuments in one place, so every loader sets numbering, status and counts the same way."""
from collections.abc import Sequence

from app.ingestion import messages
from app.ingestion.cleaning.common import title_from_filename
from app.ingestion.contract import Block, ParsedDocument, QualityReport, ResourceMeta, SourceType
from app.ingestion.precheck import UNREADABLE_SHARE_MAX


class FileRefused(Exception):
    """Raise inside a loader to fail the file with a message from messages.py that the teacher can act on."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def document_title(file_name: str, source_type: SourceType) -> str:
    """The title every heading path starts with, the same whether the file loads or fails. Code and text keep
    their file name, so stack.cpp and stack.h stay apart; every other file gets title_from_filename()."""
    return file_name if source_type in ("code", "text") else title_from_filename(file_name)


def picture_findings(unit_name: str, units: Sequence[int], total: int) -> tuple[list[str], list[str]]:
    """Pages or slides with a picture and no text, as (problems, notes), one rule for every format: a few of them
    (a cover, a diagram slide) are a note, so the status stays "ok"; more than the pre-check lets a scan have
    (UNREADABLE_SHARE_MAX, 1 in 5) make the file mostly unanswerable, a problem the teacher sees at once.
    unit_name is plural, like "Pages" or "Slides"."""
    units = sorted(set(units))
    if not units:
        return [], []
    if total and len(units) / total > UNREADABLE_SHARE_MAX:
        return [messages.mostly_pictures(unit_name, units, total)], []
    return [], [messages.no_text_units(unit_name, units)]


def failed_document(meta: ResourceMeta, source_type: SourceType, reason: str) -> ParsedDocument:
    return ParsedDocument(
        resource_id=meta.resource_id, course_id=meta.course_id, file_name=meta.file_name,
        file_sha256=meta.file_sha256, source_type=source_type,
        title=document_title(meta.file_name, source_type), parser="none", parser_version="-", blocks=[],
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