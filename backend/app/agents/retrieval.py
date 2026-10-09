from app.agents.types import Chunk


def retrieve(course_id: str, query: str, k: int = 5) -> list[Chunk]:
    """STUB. Real version: search Chroma, always filtered by course_id."""
    # TODO(Member 2): replace with real search
    return [
        Chunk(
            text="(stub chunk) This is fake course material.",
            source="lecture1.pdf",
            page=3,
            score=0.9,
            course_id=course_id,
            resource_id="stub",
        )
    ]