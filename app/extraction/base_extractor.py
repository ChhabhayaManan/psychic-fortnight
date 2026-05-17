"""Base extraction agent framework."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from app.models import SourceReference
from app.models.source import SourceType
from app.utils.logging import get_logger

logger = get_logger(__name__)


class BaseExtractor(ABC):
    """
    Base class for extraction agents.

    Each extractor is responsible for extracting one type of artifact
    from raw GitHub data.
    """

    def __init__(self, min_confidence: float = 0.7):
        """
        Initialize extractor.

        Args:
            min_confidence: Minimum confidence threshold for extraction
        """
        self.min_confidence = min_confidence
        logger.info(
            f"{self.__class__.__name__} initialized",
            min_confidence=min_confidence
        )

    @abstractmethod
    async def extract(
        self,
        raw_data: Dict[str, Any]
    ) -> List[Union[Dict[str, Any], Any]]:
        """
        Extract artifacts from raw data.

        Args:
            raw_data: Raw GitHub PR or issue data

        Returns:
            List of extracted artifacts (can be empty if no artifacts found)
        """
        pass

    @abstractmethod
    def get_artifact_type(self) -> str:
        """
        Get the artifact type this extractor produces.

        Returns:
            Artifact type string (e.g., "decision", "incident")
        """
        pass

    def build_source_references(
        self,
        raw_data: Dict[str, Any]
    ) -> List[SourceReference]:
        """
        Build source references from raw data.

        Args:
            raw_data: Raw GitHub data

        Returns:
            List of source references
        """
        source_refs = []

        # Extract source information
        source_info = raw_data.get("source", {})

        # Determine source type
        if "pr_number" in source_info:
            source_type = SourceType.PR
            source_id = str(source_info["pr_number"])
        elif "issue_number" in source_info:
            source_type = SourceType.ISSUE
            source_id = str(source_info["issue_number"])
        else:
            logger.warning("Unknown source type in raw data")
            return source_refs

        # Get metadata
        metadata = raw_data.get("metadata", {})

        # Create main source reference
        main_ref = SourceReference(
            source_type=source_type,
            source_id=source_id,
            url=source_info.get("url", ""),
            contributor=metadata.get("author", "unknown"),
            timestamp=self._parse_timestamp(metadata.get("created_at")),
            raw_data_path=raw_data.get("_storage_metadata", {}).get("raw_data_path")
        )
        source_refs.append(main_ref)

        return source_refs

    def _parse_timestamp(self, timestamp_str: Optional[str]) -> datetime:
        """
        Parse timestamp string to datetime.

        Args:
            timestamp_str: Timestamp string

        Returns:
            Datetime object
        """
        if not timestamp_str:
            return datetime.now()

        try:
            # Try ISO format
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except Exception:
            logger.warning(f"Failed to parse timestamp: {timestamp_str}")
            return datetime.now()

    def extract_contributors(self, raw_data: Dict[str, Any]) -> List[str]:
        """
        Extract contributor usernames from raw data.

        Args:
            raw_data: Raw GitHub data

        Returns:
            List of contributor usernames
        """
        contributors = set()

        # Add author
        metadata = raw_data.get("metadata", {})
        if metadata.get("author"):
            contributors.add(metadata["author"])

        # Add assignees
        if metadata.get("assignees"):
            contributors.update(metadata["assignees"])

        # Add comment authors
        for comment in raw_data.get("comments", []):
            if comment.get("author"):
                contributors.add(comment["author"])

        # Add review authors (for PRs)
        for review in raw_data.get("reviews", []):
            if review.get("author"):
                contributors.add(review["author"])

        return list(contributors)

    def extract_labels(self, raw_data: Dict[str, Any]) -> List[str]:
        """
        Extract labels from raw data.

        Args:
            raw_data: Raw GitHub data

        Returns:
            List of labels
        """
        metadata = raw_data.get("metadata", {})
        return metadata.get("labels", [])

    def extract_services(self, text: str) -> List[str]:
        """
        Extract service names from text.

        This is a simple heuristic-based extraction.
        Can be enhanced with NER or LLM-based extraction.

        Args:
            text: Text to extract services from

        Returns:
            List of service names
        """
        services = set()

        # Common service patterns
        patterns = [
            "-service",
            "-api",
            "-worker",
            "-processor",
            "-handler"
        ]

        # Split text into words
        words = text.lower().split()

        for word in words:
            # Check if word matches service patterns
            for pattern in patterns:
                if pattern in word:
                    # Clean up the service name
                    service = word.strip('.,;:()[]{}"\'-')
                    if len(service) > 3:  # Avoid very short matches
                        services.add(service)

        return list(services)

    def meets_confidence_threshold(self, confidence: float) -> bool:
        """
        Check if confidence meets threshold.

        Args:
            confidence: Confidence score

        Returns:
            True if meets threshold, False otherwise
        """
        return confidence >= self.min_confidence

    def log_extraction(
        self,
        artifact_type: str,
        count: int,
        source_id: str
    ) -> None:
        """
        Log extraction results.

        Args:
            artifact_type: Type of artifact
            count: Number of artifacts extracted
            source_id: Source identifier
        """
        logger.info(
            f"Extracted {artifact_type} -- {count}",
            count=count,
            source_id=source_id
        )


# Made with Bob
