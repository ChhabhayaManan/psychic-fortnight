"""RAW data storage for ingested data."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from app.utils.logging import get_logger

logger = get_logger(__name__)


class RawDataStorage:
    """
    Storage for raw ingested data.

    Stores data as JSON files organized by source and type.
    """

    def __init__(self, base_path: Path):
        """
        Initialize raw data storage.

        Args:
            base_path: Base directory for raw data storage
        """
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)

        logger.info("Raw data storage initialized", base_path=str(base_path))

    def store_pr(
        self,
        source_id: str,
        pr_number: int,
        data: Dict[str, Any]
    ) -> Path:
        """
        Store raw PR data.

        Args:
            source_id: Unique source identifier
            pr_number: PR number
            data: Raw PR data

        Returns:
            Path to stored file
        """
        # Create directory structure
        pr_dir = self.base_path / "github" / source_id / "prs"
        pr_dir.mkdir(parents=True, exist_ok=True)

        file_path = pr_dir / f"{pr_number}.json"

        # Add storage metadata
        data["_storage_metadata"] = {
            "stored_at": datetime.now().isoformat(),
            "source_id": source_id,
            "item_type": "pr",
            "item_number": pr_number,
            "raw_data_path": str(file_path)
        }

        # Write to file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(
            "PR data stored",
            source_id=source_id,
            pr_number=pr_number,
            path=str(file_path)
        )

        return file_path

    def store_issue(
        self,
        source_id: str,
        issue_number: int,
        data: Dict[str, Any]
    ) -> Path:
        """
        Store raw issue data.

        Args:
            source_id: Unique source identifier
            issue_number: Issue number
            data: Raw issue data

        Returns:
            Path to stored file
        """
        # Create directory structure
        issue_dir = self.base_path / "github" / source_id / "issues"
        issue_dir.mkdir(parents=True, exist_ok=True)

        file_path = issue_dir / f"{issue_number}.json"

        # Add storage metadata
        data["_storage_metadata"] = {
            "stored_at": datetime.now().isoformat(),
            "source_id": source_id,
            "item_type": "issue",
            "item_number": issue_number,
            "raw_data_path": str(file_path)
        }

        # Write to file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(
            "Issue data stored",
            source_id=source_id,
            issue_number=issue_number,
            path=str(file_path)
        )

        return file_path

    def get_pr(
        self,
        source_id: str,
        pr_number: int
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve stored PR data.

        Args:
            source_id: Unique source identifier
            pr_number: PR number

        Returns:
            PR data if exists, None otherwise
        """
        file_path = self.base_path / "github" / source_id / "prs" / f"{pr_number}.json"

        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(
                "Failed to read PR data",
                source_id=source_id,
                pr_number=pr_number,
                error=str(e)
            )
            return None

    def get_issue(
        self,
        source_id: str,
        issue_number: int
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve stored issue data.

        Args:
            source_id: Unique source identifier
            issue_number: Issue number

        Returns:
            Issue data if exists, None otherwise
        """
        file_path = self.base_path / "github" / source_id / "issues" / f"{issue_number}.json"

        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(
                "Failed to read issue data",
                source_id=source_id,
                issue_number=issue_number,
                error=str(e)
            )
            return None

    def exists(
        self,
        source_id: str,
        item_type: str,
        item_number: int
    ) -> bool:
        """
        Check if item already stored.

        Args:
            source_id: Unique source identifier
            item_type: Type of item ("pr" or "issue")
            item_number: Item number

        Returns:
            True if item exists, False otherwise
        """
        if item_type == "pr":
            file_path = self.base_path / "github" / source_id / "prs" / f"{item_number}.json"
        elif item_type == "issue":
            file_path = self.base_path / "github" / source_id / "issues" / f"{item_number}.json"
        else:
            return False

        return file_path.exists()

    def get_source_metadata(self, source_id: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a source.

        Args:
            source_id: Unique source identifier

        Returns:
            Source metadata if exists, None otherwise
        """
        metadata_path = self.base_path / "github" / source_id / "metadata.json"

        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(
                "Failed to read source metadata",
                source_id=source_id,
                error=str(e)
            )
            return None

    def store_source_metadata(
        self,
        source_id: str,
        metadata: Dict[str, Any]
    ) -> Path:
        """
        Store metadata for a source.

        Args:
            source_id: Unique source identifier
            metadata: Source metadata

        Returns:
            Path to metadata file
        """
        source_dir = self.base_path / "github" / source_id
        source_dir.mkdir(parents=True, exist_ok=True)

        metadata_path = source_dir / "metadata.json"

        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        logger.info(
            "Source metadata stored",
            source_id=source_id,
            path=str(metadata_path)
        )

        return metadata_path

# Made with Bob
