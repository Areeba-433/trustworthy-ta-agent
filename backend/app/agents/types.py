"""Shared data shapes (the contract) used by ingestion, retrieval,
the chat API and the frontend.

This file is FROZEN: change it only
after agreeing in the group chat, because other people depend on it.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Chunk:
    """One piece of course material."""
    text: str
    source: str                   # file name
    page: Optional[int]           # page, slide or line number
    score: float                  # how relevant (0 to 1)
    course_id: str
    resource_id: str


@dataclass
class Citation:
    """What the student sees under an answer."""
    file: str
    page: Optional[int]


@dataclass
class Answer:
    """What the chat gets back from the query agent."""
    text: str
    citations: list[Citation] = field(default_factory=list)
    confidence: float = 0.0
    explanation: str = ""


@dataclass
class IngestResult:
    """What ingestion reports back to the upload API."""
    status: str                   # "ready" or "failed"
    chunk_count: int = 0
    error: Optional[str] = None