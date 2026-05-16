"""Ingestion state tracking for Step 2."""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class IngestionStatus(str, Enum):
    """Status of ingestion items."""
    QUEUED = "queued"
    STORED = "stored"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class IngestionItemState:
    """State of a single ingestion item."""
    item_id: str
    source_id: str
    item_type: str  # "pr" or "issue"
    item_number: int
    status: IngestionStatus
    raw_data_path: Optional[str] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IngestionItemState':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class IngestionSourceState:
    """State of ingestion for a source."""
    source_id: str
    repository: str
    discovered_at: str
    pr_count: int = 0
    issue_count: int = 0
    total_count: int = 0
    queued_count: int = 0
    stored_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    items: Dict[str, IngestionItemState] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_item(self, item: IngestionItemState) -> None:
        """Add or update an item."""
        self.items[item.item_id] = item
        self._update_counts()

    def update_item_status(
        self,
        item_id: str,
        status: IngestionStatus,
        raw_data_path: Optional[str] = None,
        error: Optional[str] = None
    ) -> None:
        """Update item status."""
        if item_id in self.items:
            item = self.items[item_id]
            item.status = status
            item.updated_at = datetime.now().isoformat()
            if raw_data_path:
                item.raw_data_path = raw_data_path
            if error:
                item.error = error
            self._update_counts()

    def get_item(self, item_id: str) -> Optional[IngestionItemState]:
        """Get item by ID."""
        return self.items.get(item_id)

    def get_items_by_status(self, status: IngestionStatus) -> List[IngestionItemState]:
        """Get all items with given status."""
        return [item for item in self.items.values() if item.status == status]

    def _update_counts(self) -> None:
        """Update status counts."""
        self.queued_count = sum(1 for item in self.items.values() if item.status == IngestionStatus.QUEUED)
        self.stored_count = sum(1 for item in self.items.values() if item.status == IngestionStatus.STORED)
        self.skipped_count = sum(1 for item in self.items.values() if item.status == IngestionStatus.SKIPPED)
        self.failed_count = sum(1 for item in self.items.values() if item.status == IngestionStatus.FAILED)

    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_count == 0:
            return 0.0
        completed = self.stored_count + self.skipped_count + self.failed_count
        return (completed / self.total_count) * 100

    @property
    def is_complete(self) -> bool:
        """Check if ingestion is complete."""
        return self.stored_count + self.skipped_count + self.failed_count >= self.total_count

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['items'] = {k: v.to_dict() for k, v in self.items.items()}
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IngestionSourceState':
        """Create from dictionary."""
        items_data = data.pop('items', {})
        state = cls(**data)
        state.items = {k: IngestionItemState.from_dict(v) for k, v in items_data.items()}
        return state


class IngestionStateManager:
    """Manager for ingestion state persistence."""

    def __init__(self, state_dir: Path):
        """Initialize state manager."""
        self.state_dir = state_dir / "ingestion"
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def save_state(self, state: IngestionSourceState) -> Path:
        """Save ingestion state to disk."""
        state_file = self.state_dir / f"{state.source_id}.json"
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state.to_dict(), f, indent=2, ensure_ascii=False)
        return state_file

    def load_state(self, source_id: str) -> Optional[IngestionSourceState]:
        """Load ingestion state from disk."""
        state_file = self.state_dir / f"{source_id}.json"
        if not state_file.exists():
            return None

        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return IngestionSourceState.from_dict(data)
        except Exception:
            return None

    def state_exists(self, source_id: str) -> bool:
        """Check if state exists for source."""
        state_file = self.state_dir / f"{source_id}.json"
        return state_file.exists()

    def delete_state(self, source_id: str) -> bool:
        """Delete state for source."""
        state_file = self.state_dir / f"{source_id}.json"
        if state_file.exists():
            state_file.unlink()
            return True
        return False


@dataclass
class ProcessingHandoff:
    """Handoff record for Step 3 processing."""
    source_id: str
    item_type: str
    item_number: int
    raw_data_path: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "queued"
    attempt_count: int = 0
    last_error: Optional[str] = None
    next_retry_at: Optional[str] = None
    dead_letter: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProcessingHandoff':
        """Create from dictionary."""
        return cls(**data)


class ProcessingQueue:
    """Queue for Step 3 processing handoff."""

    def __init__(self, state_dir: Path):
        """Initialize processing queue."""
        self.queue_dir = state_dir / "processing_queue"
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.queue_file = self.queue_dir / "queue.json"

    def enqueue(self, handoff: ProcessingHandoff) -> None:
        """Add item to processing queue."""
        queue = self._load_queue()
        key = self._handoff_key(handoff.to_dict())
        if not any(self._handoff_key(item) == key for item in queue):
            queue.append(handoff.to_dict())
        self._save_queue(queue)

    def enqueue_batch(self, handoffs: List[ProcessingHandoff]) -> None:
        """Add multiple items to processing queue."""
        queue = self._load_queue()
        existing_keys = {self._handoff_key(item) for item in queue}
        for handoff in handoffs:
            data = handoff.to_dict()
            key = self._handoff_key(data)
            if key not in existing_keys:
                queue.append(data)
                existing_keys.add(key)
        self._save_queue(queue)

    def dequeue(self, count: int = 1) -> List[ProcessingHandoff]:
        """Remove and return items from queue."""
        queue = self._load_queue()
        active = [item for item in queue if not item.get("dead_letter")]
        items = active[:count]
        item_keys = {self._handoff_key(item) for item in items}
        remaining = [item for item in queue if self._handoff_key(item) not in item_keys]
        self._save_queue(remaining)
        return [ProcessingHandoff.from_dict(item) for item in items]

    def peek(self, count: int = 1) -> List[ProcessingHandoff]:
        """View items without removing."""
        queue = self._load_queue()
        items = [
            item for item in queue
            if not item.get("dead_letter") and item.get("status", "queued") == "queued"
        ][:count]
        return [ProcessingHandoff.from_dict(item) for item in items]

    def size(self, include_dead_letters: bool = False) -> int:
        """Get queue size."""
        queue = self._load_queue()
        if include_dead_letters:
            return len(queue)
        return len([item for item in queue if not item.get("dead_letter")])

    def dead_letter_size(self) -> int:
        """Get dead-letter item count."""
        return len([item for item in self._load_queue() if item.get("dead_letter")])

    def peek_dead_letters(self, count: int = 1) -> List[ProcessingHandoff]:
        """View dead-letter items without removing them."""
        items = [item for item in self._load_queue() if item.get("dead_letter")][:count]
        return [ProcessingHandoff.from_dict(item) for item in items]

    def record_success(self, handoff: ProcessingHandoff) -> None:
        """Remove a successfully processed item from the queue."""
        key = self._handoff_key(handoff.to_dict())
        queue = [item for item in self._load_queue() if self._handoff_key(item) != key]
        self._save_queue(queue)

    def record_failure(
        self,
        handoff: ProcessingHandoff,
        error: str,
        max_attempts: int = 3
    ) -> ProcessingHandoff:
        """Track a failed processing attempt and dead-letter after max attempts."""
        key = self._handoff_key(handoff.to_dict())
        queue = self._load_queue()
        updated: Optional[Dict[str, Any]] = None
        for item in queue:
            if self._handoff_key(item) != key:
                continue
            item["attempt_count"] = int(item.get("attempt_count", 0)) + 1
            item["last_error"] = error
            item["next_retry_at"] = datetime.now().isoformat()
            if item["attempt_count"] >= max_attempts:
                item["status"] = "dead_letter"
                item["dead_letter"] = True
            else:
                item["status"] = "queued"
                item["dead_letter"] = False
            updated = item
            break

        if updated is None:
            updated = handoff.to_dict()
            updated["attempt_count"] = int(updated.get("attempt_count", 0)) + 1
            updated["last_error"] = error
            updated["next_retry_at"] = datetime.now().isoformat()
            updated["dead_letter"] = updated["attempt_count"] >= max_attempts
            updated["status"] = "dead_letter" if updated["dead_letter"] else "queued"
            queue.append(updated)

        self._save_queue(queue)
        return ProcessingHandoff.from_dict(updated)

    def clear(self) -> None:
        """Clear the queue."""
        self._save_queue([])

    def _handoff_key(self, item: Dict[str, Any]) -> str:
        """Stable identity for queue deduplication and state updates."""
        return "|".join(
            [
                str(item.get("source_id", "")),
                str(item.get("item_type", "")),
                str(item.get("item_number", "")),
                str(item.get("raw_data_path", "")),
            ]
        )

    def _load_queue(self) -> List[Dict[str, Any]]:
        """Load queue from disk."""
        if not self.queue_file.exists():
            return []

        try:
            with open(self.queue_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save_queue(self, queue: List[Dict[str, Any]]) -> None:
        """Save queue to disk."""
        with open(self.queue_file, 'w', encoding='utf-8') as f:
            json.dump(queue, f, indent=2, ensure_ascii=False)


# Made with Bob
