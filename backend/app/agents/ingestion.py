from app.agents.types import IngestResult


def ingest_resource(resource_id: str, course_id: str,
                    file_path: str, file_type: str) -> IngestResult:
    """STUB. Real version: load -> clean -> chunk -> embed -> store in Chroma."""
    # TODO(Member 1): replace with the real pipeline
    return IngestResult(status="ready", chunk_count=0)