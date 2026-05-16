"""Base ingestion class for all data sources."""

from abc import ABC, abstractmethod
from typing import Any, Dict

from app.models.ingestion import DiscoveryResult


class BaseIngestion(ABC):
    """
    Base class for all ingestion sources.

    Provides common interface for discovering and fetching data
    from various sources (GitHub, GitLab, Jira, etc.).
    """

    @abstractmethod
    async def discover(self) -> DiscoveryResult:
        """
        Discover all items to ingest from the source.

        Returns:
            DiscoveryResult containing all discovered items
        """
        pass

    @abstractmethod
    async def fetch(self, item_id: str) -> Dict[str, Any]:
        """
        Fetch raw data for a single item.

        Args:
            item_id: Unique identifier for the item

        Returns:
            Dictionary containing raw item data
        """
        pass

    @abstractmethod
    async def validate(self) -> bool:
        """
        Validate connection to source.

        Returns:
            True if connection is valid, False otherwise
        """
        pass

    @abstractmethod
    def get_source_id(self) -> str:
        """
        Get unique identifier for this source.

        Returns:
            Source identifier string
        """
        pass

# Made with Bob
