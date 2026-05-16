"""Decision memory model."""

from datetime import datetime
from typing import List
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .source import SourceReference


class Decision(BaseModel):
    """
    Architectural decision memory.

    Represents a significant engineering decision extracted from PRs, issues,
    or discussions. One decision can be derived from multiple sources.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = Field(..., min_length=1, max_length=200)
    summary: str = Field(..., min_length=10)
    reasoning: str = Field(..., min_length=10)

    # Confidence score (0.0 to 1.0)
    # Only decisions with confidence > 0.7 are stored
    confidence: float = Field(..., ge=0.0, le=1.0)

    # Related entities
    related_services: List[str] = Field(default_factory=list)
    contributors: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)

    # Source provenance - CRITICAL for preventing hallucinations
    # Can have multiple sources if decision spans multiple PRs/Issues
    source_refs: List[SourceReference] = Field(..., min_length=1)

    # Timestamps
    timestamp: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Metadata
    metadata: dict = Field(default_factory=dict)

    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Ensure confidence is within valid range."""
        if v < 0.0 or v > 1.0:
            raise ValueError('Confidence must be between 0.0 and 1.0')
        return v

    @field_validator('source_refs')
    @classmethod
    def validate_sources(cls, v: List[SourceReference]) -> List[SourceReference]:
        """Ensure at least one source reference exists."""
        if not v:
            raise ValueError('At least one source reference is required')
        return v

    def add_source(self, source_ref: SourceReference) -> None:
        """Add additional source reference."""
        self.source_refs.append(source_ref)
        self.updated_at = datetime.now()

    def to_embedding_text(self) -> str:
        """Generate text for embedding generation."""
        return f"{self.title}\n\n{self.summary}\n\nReasoning: {self.reasoning}"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "dec_123",
                "title": "Migration to gRPC for inter-service communication",
                "summary": "Decided to migrate from REST to gRPC for all inter-service communication to improve performance and type safety.",
                "reasoning": "REST was causing latency issues and lack of type safety led to runtime errors. gRPC provides better performance with HTTP/2 and strong typing with Protocol Buffers.",
                "confidence": 0.85,
                "related_services": ["api-gateway", "user-service", "payment-service"],
                "contributors": ["alice", "bob"],
                "tags": ["architecture", "performance", "grpc"],
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
