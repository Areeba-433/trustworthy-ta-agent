"""process(): one uploaded file in, its chunks out. The single function the job worker will call.

    file -> ingest_file() (pre-check, loader, parsed.json) -> the chunker for its file type -> chunks.json

Like ingest_file(), it never raises for a bad file or a bug in one chunker: the result says what happened,
so one broken upload never stops the files queued after it.
"""
import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.ingestion import messages
from app.ingestion.chunking.registry import get_chunker
from app.ingestion.contract import ChunkedDocument, ParsedDocument, Status
from app.ingestion.dispatcher import ingest_file
from app.ingestion.storage import Timer, chunks_path, write_text_atomic

logger = logging.getLogger("tta.ingestion")


@dataclass(frozen=True)
class ProcessResult:
    status: Status                                    # what the teacher sees: ok, degraded or failed
    parsed: ParsedDocument
    chunked: ChunkedDocument | None                   # None when the file or its chunking failed
    warnings: list[str] = field(default_factory=list)  # plain words for the teacher


def process(path: Path, resource_id: str, course_id: str) -> ProcessResult:
    parsed = ingest_file(path, resource_id, course_id)        # always returns, and always writes parsed.json
    target = chunks_path(resource_id)
    if parsed.quality.status == "failed":
        target.unlink(missing_ok=True)                        # never leave chunks from an earlier upload behind
        return ProcessResult("failed", parsed, None, list(parsed.quality.warnings))

    timer = Timer()
    try:
        with timer("chunk"):
            chunked = get_chunker(parsed.source_type)(parsed)
            chunked = ChunkedDocument.model_validate(chunked.model_dump())    # check the rules once more
    except Exception:
        logger.exception("chunking failed: resource=%s type=%s", resource_id, parsed.source_type)
        target.unlink(missing_ok=True)
        return ProcessResult("failed", parsed, None, [*parsed.quality.warnings, messages.INTERNAL])

    write_text_atomic(target, chunked.model_dump_json(indent=2))
    logger.info("chunked resource=%s type=%s chunks=%d seconds=%.2f",
                resource_id, parsed.source_type, len(chunked.chunks), timer.seconds["chunk"])
    return ProcessResult(parsed.quality.status, parsed, chunked, list(parsed.quality.warnings))