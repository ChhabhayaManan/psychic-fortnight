"""Relationship model for knowledge graph."""

from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class RelationType(str, Enum):
    """Types of relationships between entities."""
    AFFECTS = "affects"
    CAUSED_BY = "caused_by"
    RESOLVES = "resolves"
    DEPENDS_ON = "depends_on"
    RELATED_TO = "related_to"
    IMPLEMENTS = "implements"
    SUPERSEDES = "supersedes"
    REFERENCES = "references"


class Relationship(BaseModel):
    """
    Relationship between two entities in the knowledge graph.

    Used to build connections between decisions, incidents, services,
    and other entities.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    source: str  # Source entity ID
    target: str  # Target entity ID
    relation_type: RelationType
    confidence: float = Field(..., ge=0.0, le=1.0)

    # Optional metadata
    description: str = ""
    metadata: dict = Field(default_factory=dict)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "rel_123",
                "source": "dec_123",
                "target": "payment-service",
                "relation_type": "affects",
                "confidence": 0.9,
                "description": "Decision to migrate to gRPC affects payment service architecture"
            }
        }
    )

# Made with Bob
