"""Processing state model for autonomous processing."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class ProcessingStatus(str, Enum):
    """Processing status states."""
    IDLE = "idle"
    DISCOVERING = "discovering"
    QUEUED = "queued"
    PROCESSING = "processing"
    MONITORING = "monitoring"
    PAUSED = "paused"
    ERROR = "error"
    COMPLETED = "completed"


class ProcessingState(BaseModel):
    """
    Processing state for autonomous background processing.

    Tracks the current state of data processing for a connected source,
    enabling resumable workflows and progress tracking.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    source_id: str
    source_name: str
    status: ProcessingStatus = ProcessingStatus.IDLE

    # Progress tracking
    total_items: int = 0
    processed_items: int = 0
    failed_items: int = 0
    in_progress: int = 0

    # Checkpoints for resumption
    last_pr_number: Optional[int] = None
    last_issue_number: Optional[int] = None
    last_processed_id: Optional[str] = None

    # Timestamps
    started_at: Optional[datetime] = None
    last_updated: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    # Error tracking
    error_message: Optional[str] = None
    error_count: int = 0

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_items == 0:
            return 0.0
        return (self.processed_items / self.total_items) * 100

    @property
    def is_complete(self) -> bool:
        """Check if processing is complete."""
        return self.processed_items + self.failed_items >= self.total_items

    def update_progress(self, processed: int = 0, failed: int = 0) -> None:
        """Update processing progress."""
        self.processed_items += processed
        self.failed_items += failed
        self.last_updated = datetime.now()

        if self.is_complete and self.status == ProcessingStatus.PROCESSING:
            self.status = ProcessingStatus.COMPLETED
            self.completed_at = datetime.now()

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "state_123",
                "source_id": "source_456",
                "source_name": "owner/repo",
                "status": "processing",
                "total_items": 200,
                "processed_items": 150,
                "failed_items": 5,
                "in_progress": 3,
                "last_pr_number": 145,
                "last_issue_number": 89,
                "started_at": "2024-01-15T10:00:00Z",
                "last_updated": "2024-01-15T10:30:00Z"
            }
        }
    )


class Checkpoint(BaseModel):
    """Checkpoint for resumable processing."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    source_id: str
    checkpoint_data: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "chk_123",
                "source_id": "source_456",
                "checkpoint_data": {
                    "last_pr": 145,
                    "last_issue": 89,
                    "queue_position": 150
                },
                "created_at": "2024-01-15T10:30:00Z"
            }
        }
    )

# Made with Bob
