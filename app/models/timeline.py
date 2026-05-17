"""Timeline event model."""

from datetime import datetime
from typing import List
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .source import SourceReference


class TimelineEvent(BaseModel):
    """
    Timeline event memory.

    Represents a significant event in the engineering timeline
    (architecture changes, migrations, releases, etc.)
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str  # "architecture_change", "migration", "release", "incident", etc.
    title: str = Field(..., min_length=1, max_length=200)
    summary: str = Field(..., min_length=10)

    # Related entities
    related_entities: List[str] = Field(default_factory=list)  # Service names, decision IDs, etc.
    related_decisions: List[str] = Field(default_factory=list)
    related_incidents: List[str] = Field(default_factory=list)
    contributors: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)

    # Source provenance
    source_refs: List[SourceReference] = Field(..., min_length=1)

    # Timestamps
    timestamp: datetime  # When the event occurred
    created_at: datetime = Field(default_factory=datetime.now)

    # Metadata
    metadata: dict = Field(default_factory=dict)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "evt_123",
                "event_type": "architecture_change",
                "title": "Migration to microservices architecture",
                "summary": "Completed migration from monolithic architecture to microservices, splitting into 5 core services.",
                "related_entities": ["api-gateway", "user-service", "payment-service"],
                "related_decisions": ["dec_123", "dec_456"],
                "contributors": ["alice", "bob", "charlie"],
                "tags": ["architecture", "microservices", "migration"],
                "source_refs": [
                    {
                        "source_type": "pr",
                        "source_id": "100",
                        "url": "https://github.com/owner/repo/pull/100",
                        "contributor": "alice",
                        "timestamp": "2024-01-15T10:00:00Z"
                    }
                ],
                "timestamp": "2024-01-15T10:00:00Z"
            }
        }
    )

# Made with Bob
