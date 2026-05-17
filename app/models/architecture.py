"""Architecture change memory model."""

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .source import SourceReference


class ArchitectureChange(BaseModel):
    """
    Architecture change memory.

    Represents a significant architectural change, migration, or
    system design modification.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = Field(..., min_length=1, max_length=200)
    summary: str = Field(..., min_length=10)
    change_type: str  # "migration", "refactor", "new_service", "deprecation", etc.

    # State changes
    before_state: Optional[str] = None
    after_state: Optional[str] = None

    # Confidence score
    confidence: float = Field(..., ge=0.0, le=1.0)

    # Related entities
    affected_services: List[str] = Field(default_factory=list)
    contributors: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)

    # Source provenance
    source_refs: List[SourceReference] = Field(..., min_length=1)

    # Timestamps
    timestamp: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Metadata
    metadata: dict = Field(default_factory=dict)

    def to_embedding_text(self) -> str:
        """Generate text for embedding generation."""
        text = f"{self.title}\n\n{self.summary}\n\nChange Type: {self.change_type}"
        if self.before_state:
            text += f"\n\nBefore: {self.before_state}"
        if self.after_state:
            text += f"\n\nAfter: {self.after_state}"
        return text

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "arch_123",
                "title": "Migration from REST to gRPC",
                "summary": "Migrated all inter-service communication from REST to gRPC for improved performance and type safety.",
                "change_type": "migration",
                "before_state": "REST APIs with JSON payloads",
                "after_state": "gRPC with Protocol Buffers",
                "confidence": 0.9,
                "affected_services": ["api-gateway", "user-service", "payment-service"],
                "contributors": ["alice", "bob"],
                "tags": ["architecture", "grpc", "migration"],
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
