"""Incident memory model."""

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .source import SourceReference


class Incident(BaseModel):
    """
    Incident memory.

    Represents a production incident, outage, or significant issue
    with root cause analysis and resolution.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = Field(..., min_length=1, max_length=200)
    summary: str = Field(..., min_length=10)
    root_cause: Optional[str] = None
    resolution: Optional[str] = None

    # Severity level
    severity: str = Field(default="medium")  # low, medium, high, critical

    # Impact
    affected_services: List[str] = Field(default_factory=list)
    impact_description: Optional[str] = None

    # Related entities
    related_decisions: List[str] = Field(default_factory=list)  # Decision IDs
    contributors: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)

    # Source provenance
    source_refs: List[SourceReference] = Field(..., min_length=1)

    # Timestamps
    occurred_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Metadata
    metadata: dict = Field(default_factory=dict)

    def to_embedding_text(self) -> str:
        """Generate text for embedding generation."""
        text = f"{self.title}\n\n{self.summary}"
        if self.root_cause:
            text += f"\n\nRoot Cause: {self.root_cause}"
        if self.resolution:
            text += f"\n\nResolution: {self.resolution}"
        return text

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "inc_123",
                "title": "Payment service outage",
                "summary": "Payment service experienced complete outage for 2 hours affecting all transactions.",
                "root_cause": "Database connection pool exhaustion due to connection leak in payment processor.",
                "resolution": "Increased connection pool size and fixed connection leak in payment processor code.",
                "severity": "critical",
                "affected_services": ["payment-service", "checkout-service"],
                "impact_description": "All payment transactions failed, affecting approximately 10,000 users.",
                "related_decisions": ["dec_456"],
                "contributors": ["alice", "bob"],
                "tags": ["outage", "database", "payment"],
                "source_refs": [
                    {
                        "source_type": "issue",
                        "source_id": "789",
                        "url": "https://github.com/owner/repo/issues/789",
                        "contributor": "alice",
                        "timestamp": "2024-01-15T10:00:00Z"
                    }
                ],
                "occurred_at": "2024-01-15T08:00:00Z",
                "resolved_at": "2024-01-15T10:00:00Z",
                "timestamp": "2024-01-15T10:00:00Z"
            }
        }
    )

# Made with Bob
