"""Ownership memory model."""

from datetime import datetime
from typing import List
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .source import SourceReference


class OwnershipMemory(BaseModel):
    """
    Ownership memory.

    Tracks ownership information for services, components, or features
    based on evidence from PRs, issues, and discussions.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    entity_name: str = Field(..., min_length=1)  # Service, component, or feature name
    entity_type: str  # "service", "component", "feature", "repository", etc.

    # Ownership information
    owners: List[str] = Field(..., min_length=1)  # List of owner usernames
    evidence_summary: str = Field(..., min_length=10)

    # Confidence score
    confidence: float = Field(..., ge=0.0, le=1.0)

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
        owners_text = ", ".join(self.owners)
        return f"{self.entity_name} ({self.entity_type})\n\nOwners: {owners_text}\n\n{self.evidence_summary}"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "own_123",
                "entity_name": "payment-service",
                "entity_type": "service",
                "owners": ["alice", "bob"],
                "evidence_summary": "Alice and Bob are the primary contributors to payment-service, having authored 80% of commits and reviewed most PRs.",
                "confidence": 0.85,
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
