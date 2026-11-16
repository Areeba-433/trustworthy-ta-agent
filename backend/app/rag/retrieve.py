"""search(): the top chunks of one course for a student's question.

The question is embedded exactly like the chunks (bge-m3, length-1 vectors), and ChromaDB returns the
nearest chunks of that course's collection only, so a TA never answers from another course.
"""
from dataclasses import dataclass, field

from app.rag.embedder import embed_texts
from app.rag.store import Embedder, collection_for

TOP_K = 5                   # the plan's plain first version: top 5 by cosine distance


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    text: str
    distance: float                         # cosine distance: 0 = same direction, smaller is closer
    citation: str                           # "p. 47", "slide 12" or the heading path (DOCX)
    figure_ids: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def score(self) -> float:
        """Cosine similarity, 1 = the same meaning: easier to read in reports than the distance."""
        return 1 - self.distance


def citation_for(meta: dict) -> str:
    if "page" in meta:
        end = meta.get("page_end")
        return f"p. {meta['page']}" + (f"-{end}" if end and end != meta["page"] else "")
    if "slide" in meta:
        return f"slide {meta['slide']}"
    if "line_start" in meta:
        return f"lines {meta['line_start']}-{meta.get('line_end', meta['line_start'])}"
    return meta.get("heading") or meta.get("title", "")


def search(course_id: str, question: str, k: int = TOP_K, embed: Embedder = embed_texts, client=None) -> list[Hit]:
    question = question.strip()
    collection = collection_for(course_id, client)
    if not question or collection.count() == 0:
        return []
    found = collection.query(query_embeddings=embed([question]), n_results=min(k, collection.count()),
                             include=["documents", "metadatas", "distances"])
    hits = []
    for chunk_id, text, meta, distance in zip(found["ids"][0], found["documents"][0], found["metadatas"][0],
                                               found["distances"][0]):
        figures = [f for f in (meta.get("figure_ids") or "").split(",") if f]
        hits.append(Hit(chunk_id=chunk_id, text=text, distance=float(distance), citation=citation_for(meta),
                        figure_ids=figures, metadata=dict(meta)))
    return hits
