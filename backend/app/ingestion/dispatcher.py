"""ingest_file(): file in, ParsedDocument out. The only entry point into ingestion."""
import logging
import threading
from contextlib import nullcontext
from pathlib import Path

from app.ingestion import messages
from app.ingestion.contract import ParsedDocument, ResourceMeta
from app.ingestion.documents import failed_document
from app.ingestion.precheck import precheck
from app.ingestion.registry import get_loader , is_heavy
from app.ingestion.storage import Timer, file_sha256, parsed_path, write_text_atomic
logger = logging.getLogger("tta.ingestion")

_HEAVY: set[str] = {"pdf", "docx", "pptx"}   # these use a lot of memory
_heavy_slot = threading.Semaphore(1)         # only one heavy file at a time: see register(heavy=True)

def ingest_file(path: Path, resource_id: str, course_id: str) -> ParsedDocument:
    timer = Timer()
    with timer("hash"):
        sha = file_sha256(path)
    with timer("precheck"):
        pre = precheck(path)        # an unsupported type raises: the upload page must refuse it first
    meta = ResourceMeta(resource_id=resource_id, course_id=course_id, file_name=path.name,
                        file_sha256=sha, precheck=pre)

    if not pre.ok:
        doc = failed_document(meta, pre.source_type, pre.reason)
    else:
        loader = get_loader(pre.source_type)
        slot = _heavy_slot if is_heavy(pre.source_type) else nullcontext()
        try:
            with timer("load"), slot:
                doc = loader(path, meta)
            if (doc.resource_id, doc.file_sha256) != (resource_id, sha):
                raise ValueError("loader returned a document for a different file")
            doc = ParsedDocument.model_validate(doc.model_dump())   # check the rules once more
        except Exception:
            logger.exception("ingestion failed: resource=%s type=%s", resource_id, pre.source_type)
            doc = failed_document(meta, pre.source_type, messages.INTERNAL)

    doc.quality.seconds_taken.update({f"dispatch_{k}": v for k, v in timer.seconds.items()})
    write_text_atomic(parsed_path(resource_id), doc.model_dump_json(indent=2))
    logger.info("ingested resource=%s type=%s status=%s blocks=%d",
                resource_id, doc.source_type, doc.quality.status, len(doc.blocks))
    return doc