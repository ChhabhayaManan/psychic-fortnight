"""Source reference models for provenance tracking."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class SourceType(str, Enum):
    """Type of source."""
    PR = "pr"
    ISSUE = "issue"
    COMMENT = "comment"
    REVIEW = "review"
    FILE = "file"
    MCP = "mcp"


class SourceReference(BaseModel):
    """
    Source provenance tracking.

    Every memory MUST track its source to prevent hallucinations
    and enable verification.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    source_type: SourceType
    source_id: str  # PR number, issue number, etc.
    url: str
    contributor: str  # GitHub username or author
    timestamp: datetime
    raw_data_path: Optional[str] = None  # Path to raw data file

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "src_123",
                "source_type": "pr",
                "source_id": "42",
                "url": "https://github.com/owner/repo/pull/42",
                "contributor": "alice",
                "timestamp": "2024-01-15T10:00:00Z",
                "raw_data_path": "data/raw/github/pr_42.json"
            }
        }
    )


class Source(BaseModel):
    """Connected knowledge source configuration."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str  # "github", "mcp", "file"
    name: str  # Display name
    config: dict  # Source-specific configuration
    connected_at: datetime = Field(default_factory=datetime.now)
    last_sync: Optional[datetime] = None
    is_active: bool = True

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "source_123",
                "type": "github",
                "name": "owner/repo",
                "config": {
                    "repo": "owner/repo",
                    "token": "ghp_xxx"
                },
                "connected_at": "2024-01-15T10:00:00Z",
                "last_sync": "2024-01-15T11:00:00Z",
                "is_active": True
            }
        }
    )

# Made with Bob
