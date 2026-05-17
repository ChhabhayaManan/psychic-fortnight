"""Unresolved question memory model."""

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .source import SourceReference


class UnresolvedQuestion(BaseModel):
    """
    Unresolved question memory.

    Tracks open questions, uncertainties, or areas needing clarification
    identified in PRs, issues, or discussions.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = Field(..., min_length=1, max_length=200)
    question: str = Field(..., min_length=10)
    context: str = Field(..., min_length=10)

    # Status
    status: str = Field(default="open")  # "open", "investigating", "resolved"

    # Related entities
    related_services: List[str] = Field(default_factory=list)
    contributors: List[str] = Field(default_factory=list)

    # Confidence score
    confidence: float = Field(..., ge=0.0, le=1.0)

    # Source provenance
    source_refs: List[SourceReference] = Field(..., min_length=1)

    # Timestamps
    timestamp: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None

    # Metadata
    metadata: dict = Field(default_factory=dict)

    def to_embedding_text(self) -> str:
        """Generate text for embedding generation."""
        return f"{self.title}\n\nQuestion: {self.question}\n\nContext: {self.context}"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "unr_123",
                "title": "Unclear database scaling strategy",
                "question": "How should we handle database scaling when user count exceeds 1M?",
                "context": "Discussion in PR #42 raised concerns about database performance at scale, but no clear strategy was decided.",
                "status": "open",
                "related_services": ["database", "user-service"],
                "contributors": ["alice", "bob"],
                "confidence": 0.8,
                "source_refs": [
                    {
                        "source_type": "pr",
                        "source_id": "42",
                        "url": "https://github.com/owner/repo/pull/42",
                        "contributor": "alice",
                        "timestamp": "2024-01-15T10:00:00Z"
                    }
                ],
                "timestamp": "2024-01-15T10:00:00Z"
            }
        }
    )

# Made with Bob
