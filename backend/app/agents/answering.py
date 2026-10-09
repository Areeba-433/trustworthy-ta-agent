from app.agents.types import Answer, Citation


def answer(course_id: str, question: str) -> Answer:
    """STUB. Real version: run the LangGraph query flow."""
    # TODO(Member 2): replace with the real graph
    return Answer(
        text="(stub answer) This is a fake reply.",
        citations=[Citation(file="lecture1.pdf", page=3)],
        confidence=0.8,
        explanation="(stub) Based on the cited course material.",
    )