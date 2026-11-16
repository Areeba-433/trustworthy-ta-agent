"""ChromaDB: one collection per course, one record per chunk.

    index_chunks(chunked)   -> delete the file's old chunks, embed the new ones, upsert them
    delete_resource(...)    -> take a file's chunks out (re-upload, or the teacher deletes the file)
    collection_for(course)  -> the course's collection, made on first use

The record id is the chunk_id, the document is the chunk text, and the metadata holds what retrieval and
citations need (see metadata_for). ChromaDB metadata takes only text, numbers and true/false: no lists and
no empty values, so lists are joined with commas and empty fields are left out.
"""
import re
from collections.abc import Callable
from functools import lru_cache

import chromadb

from app.core.config import settings
from app.ingestion.contract import Chunk, ChunkedDocument, embedding_text
from app.rag.embedder import embed_texts

Embedder = Callable[[list[str]], list[list[float]]]
_NOT_ALNUM = re.compile(r"[^A-Za-z0-9]")


@lru_cache(maxsize=4)
def get_client(path: str | None = None):
    """One client per folder (data/chroma by default): it keeps the vectors on disk between runs."""
    return chromadb.PersistentClient(path=path or settings.CHROMA_DIR)


def collection_name(course_id: str) -> str:
    """'course_' + the course id without dashes: the course's TAs search only this collection."""
    cleaned = _NOT_ALNUM.sub("", str(course_id))
    if not cleaned:
        raise ValueError(f"no usable course id: {course_id!r}")
    return f"course_{cleaned}"


def collection_for(course_id: str, client=None):
    client = client or get_client()
    return client.get_or_create_collection(
        name=collection_name(course_id),
        metadata={"hnsw:space": "cosine"},     # distance = 1 - cosine similarity; our vectors have length 1
        embedding_function=None,               # we always pass our own bge-m3 vectors
    )


def metadata_for(chunk: Chunk, doc: ChunkedDocument) -> dict[str, str | int | bool]:
    meta: dict[str, str | int | bool] = {
        "resource_id": doc.resource_id,
        "course_id": doc.course_id,
        "source_type": doc.source_type,
        "title": doc.title,
        "heading": " > ".join(chunk.heading_path),
        "kinds": ",".join(chunk.kinds),
        "figure_ids": ",".join(chunk.figure_ids),
        "has_figure": bool(chunk.figure_ids),
        "token_count": chunk.token_count,
        "chunker": doc.chunker,
        "seq": chunk.seq,
    }
    for key in ("page", "page_end", "slide", "line_start", "line_end", "t_start", "t_end"):   # empty ones left out
        value = getattr(chunk.loc, key, None)
        if value is not None:
            meta[key] = value
    return meta


def delete_resource(course_id: str, resource_id: str, client=None) -> None:
    collection_for(course_id, client).delete(where={"resource_id": resource_id})


def index_chunks(doc: ChunkedDocument, embed: Embedder = embed_texts, client=None) -> int:
    """Replace this file's chunks in its course's collection. Returns how many chunks are stored."""
    collection = collection_for(doc.course_id, client)
    collection.delete(where={"resource_id": doc.resource_id})    # a re-upload never leaves old chunks behind
    if not doc.chunks:
        return 0
    vectors = embed([embedding_text(chunk) for chunk in doc.chunks])
    collection.upsert(
        ids=[chunk.chunk_id for chunk in doc.chunks],
        embeddings=vectors,
        documents=[chunk.text for chunk in doc.chunks],
        metadatas=[metadata_for(chunk, doc) for chunk in doc.chunks],
    )
    return len(doc.chunks)
