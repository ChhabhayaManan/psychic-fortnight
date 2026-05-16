"""JSON storage for extracted artifacts."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

from app.models import (
    ArchitectureChange,
    Decision,
    Incident,
    OwnershipMemory,
    Relationship,
    TimelineEvent,
    UnresolvedQuestion,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Type mapping for artifacts
ARTIFACT_TYPES = {
    "decision": Decision,
    "decisions": Decision,
    "incident": Incident,
    "incidents": Incident,
    "timeline": TimelineEvent,
    "architecture": ArchitectureChange,
    "ownership": OwnershipMemory,
    "unresolved": UnresolvedQuestion,
    "relationship": Relationship,
    "relationships": Relationship,
}

ARTIFACT_DIRECTORY_ALIASES = {
    "decision": "decisions",
    "incident": "incidents",
    "relationship": "relationships",
}


class JsonStore:
    """
    JSON storage for extracted artifacts.

    Stores typed memory artifacts as JSON files organized by type.
    """

    def __init__(self, base_path: Path):
        """
        Initialize JSON store.

        Args:
            base_path: Base directory for extracted data storage
        """
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Create subdirectories for each artifact type
        self.directories = {
            "decisions": self.base_path / "decisions",
            "incidents": self.base_path / "incidents",
            "timeline": self.base_path / "timeline",
            "architecture": self.base_path / "architecture",
            "ownership": self.base_path / "ownership",
            "unresolved": self.base_path / "unresolved",
            "relationships": self.base_path / "relationships",
        }

        for directory in self.directories.values():
            directory.mkdir(parents=True, exist_ok=True)

        logger.info("JSON store initialized", base_path=str(base_path))

    def store_artifact(
        self,
        artifact_type: str,
        artifact: Union[Decision, Incident, TimelineEvent, ArchitectureChange,
                       OwnershipMemory, UnresolvedQuestion, Relationship]
    ) -> Path:
        """
        Store an artifact.

        Args:
            artifact_type: Type of artifact (e.g., "decision", "incident")
            artifact: Artifact instance to store

        Returns:
            Path to stored file
        """
        # Normalize artifact type
        artifact_type = self._normalize_artifact_type(artifact_type)
        if artifact_type not in self.directories:
            raise ValueError(f"Unknown artifact type: {artifact_type}")

        # Get directory
        directory = self.directories[artifact_type]

        # Create file path
        file_path = directory / f"{artifact.id}.json"

        # Convert to dict and add storage metadata
        artifact_dict = artifact.model_dump(mode='json')
        artifact_dict["_storage_metadata"] = {
            "stored_at": datetime.now().isoformat(),
            "artifact_type": artifact_type,
            "artifact_id": artifact.id
        }

        # Write to file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(artifact_dict, f, indent=2, ensure_ascii=False)

        logger.info(
            "Artifact stored",
            artifact_type=artifact_type,
            artifact_id=artifact.id,
            path=str(file_path)
        )

        return file_path

    def get_artifact(
        self,
        artifact_type: str,
        artifact_id: str
    ) -> Optional[Union[Decision, Incident, TimelineEvent, ArchitectureChange,
                       OwnershipMemory, UnresolvedQuestion, Relationship]]:
        """
        Retrieve an artifact by type and ID.

        Args:
            artifact_type: Type of artifact
            artifact_id: Artifact ID

        Returns:
            Artifact instance if found, None otherwise
        """
        # Normalize artifact type
        artifact_type = self._normalize_artifact_type(artifact_type)
        if artifact_type not in self.directories:
            raise ValueError(f"Unknown artifact type: {artifact_type}")

        # Get file path
        directory = self.directories[artifact_type]
        file_path = directory / f"{artifact_id}.json"

        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Remove storage metadata before creating instance
            data.pop("_storage_metadata", None)

            # Get model class
            model_class = ARTIFACT_TYPES.get(artifact_type)
            if not model_class:
                logger.error(f"No model class for artifact type: {artifact_type}")
                return None

            # Create instance
            return model_class(**data)

        except Exception as e:
            logger.error(
                "Failed to load artifact",
                artifact_type=artifact_type,
                artifact_id=artifact_id,
                error=str(e)
            )
            return None

    def list_artifacts(self, artifact_type: str) -> List[str]:
        """
        List all artifact IDs of a given type.

        Args:
            artifact_type: Type of artifact

        Returns:
            List of artifact IDs
        """
        # Normalize artifact type
        artifact_type = self._normalize_artifact_type(artifact_type)
        if artifact_type not in self.directories:
            raise ValueError(f"Unknown artifact type: {artifact_type}")

        directory = self.directories[artifact_type]

        # Get all JSON files
        artifact_ids = [
            f.stem for f in directory.glob("*.json")
        ]

        return artifact_ids

    def artifact_exists(self, artifact_type: str, artifact_id: str) -> bool:
        """
        Check if an artifact exists.

        Args:
            artifact_type: Type of artifact
            artifact_id: Artifact ID

        Returns:
            True if artifact exists, False otherwise
        """
        # Normalize artifact type
        artifact_type = self._normalize_artifact_type(artifact_type)
        if artifact_type not in self.directories:
            return False

        directory = self.directories[artifact_type]
        file_path = directory / f"{artifact_id}.json"

        return file_path.exists()

    def get_artifact_count(self, artifact_type: str) -> int:
        """
        Get count of artifacts of a given type.

        Args:
            artifact_type: Type of artifact

        Returns:
            Count of artifacts
        """
        return len(self.list_artifacts(artifact_type))

    def get_all_counts(self) -> Dict[str, int]:
        """
        Get counts for all artifact types.

        Returns:
            Dictionary mapping artifact type to count
        """
        return {
            artifact_type: self.get_artifact_count(artifact_type)
            for artifact_type in self.directories.keys()
        }

    def delete_artifact(self, artifact_type: str, artifact_id: str) -> bool:
        """
        Delete an artifact.

        Args:
            artifact_type: Type of artifact
            artifact_id: Artifact ID

        Returns:
            True if deleted, False if not found
        """
        # Normalize artifact type
        artifact_type = self._normalize_artifact_type(artifact_type)
        if artifact_type not in self.directories:
            return False

        directory = self.directories[artifact_type]
        file_path = directory / f"{artifact_id}.json"

        if file_path.exists():
            file_path.unlink()
            logger.info(
                "Artifact deleted",
                artifact_type=artifact_type,
                artifact_id=artifact_id
            )
            return True

        return False

    def _normalize_artifact_type(self, artifact_type: str) -> str:
        """Normalize singular artifact names to storage directory names."""
        normalized = artifact_type.lower()
        return ARTIFACT_DIRECTORY_ALIASES.get(normalized, normalized)


# Made with Bob
