"""Ingestion data models."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class IngestionItem:
    """Item to be ingested."""
    id: str
    source_id: str
    item_type: str  # "pr" or "issue"
    item_number: int
    priority: int = 0

    def __hash__(self):
        """Make hashable for set operations."""
        return hash(self.id)


@dataclass
class DiscoveryResult:
    """Result of discovery process."""
    source_id: str
    pr_numbers: List[int]
    issue_numbers: List[int]
    total_count: int
    discovered_at: datetime = field(default_factory=datetime.now)

    def to_items(self) -> List[IngestionItem]:
        """Convert to list of IngestionItems."""
        items = []

        # Add PRs
        for pr_num in self.pr_numbers:
            items.append(IngestionItem(
                id=f"{self.source_id}_pr_{pr_num}",
                source_id=self.source_id,
                item_type="pr",
                item_number=pr_num
            ))

        # Add Issues
        for issue_num in self.issue_numbers:
            items.append(IngestionItem(
                id=f"{self.source_id}_issue_{issue_num}",
                source_id=self.source_id,
                item_type="issue",
                item_number=issue_num
            ))

        return items


@dataclass
class IngestionResult:
    """Result of ingesting one item."""
    item_id: str
    success: bool
    error: Optional[str] = None
    stored_path: Optional[Path] = None
    duration: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

# Made with Bob
