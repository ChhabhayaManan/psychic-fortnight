"""Project snapshot generation and storage."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.memory.json_store import JsonStore
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SnapshotStore:
    """
    Project snapshot storage.

    Generates and stores project summary snapshots including
    artifact counts, latest items, and statistics.
    """

    def __init__(self, snapshots_dir: Path, json_store: JsonStore):
        """
        Initialize snapshot store.

        Args:
            snapshots_dir: Directory for snapshot storage
            json_store: JsonStore instance for reading artifacts
        """
        self.snapshots_dir = snapshots_dir
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.json_store = json_store

        logger.info("Snapshot store initialized", snapshots_dir=str(snapshots_dir))

    def refresh_project_summary(self) -> Dict[str, Any]:
        """
        Generate and save project summary snapshot.

        Returns:
            Project summary dictionary
        """
        logger.info("Refreshing project summary")

        # Get artifact counts
        counts = self.json_store.get_all_counts()

        # Get latest items from each type
        latest_decisions = self._get_latest_artifacts("decisions", limit=5)
        latest_incidents = self._get_latest_artifacts("incidents", limit=5)
        latest_timeline = self._get_latest_artifacts("timeline", limit=10)
        latest_architecture = self._get_latest_artifacts("architecture", limit=5)
        latest_ownership = self._get_latest_artifacts("ownership", limit=10)
        latest_unresolved = self._get_latest_artifacts("unresolved", limit=10)

        # Build summary
        summary = {
            "generated_at": datetime.now().isoformat(),
            "artifact_counts": counts,
            "total_artifacts": sum(counts.values()),
            "latest_decisions": latest_decisions,
            "latest_incidents": latest_incidents,
            "timeline_highlights": latest_timeline,
            "latest_architecture_changes": latest_architecture,
            "ownership_map": latest_ownership,
            "unresolved_questions": latest_unresolved,
            "statistics": {
                "decisions": counts.get("decisions", 0),
                "incidents": counts.get("incidents", 0),
                "timeline_events": counts.get("timeline", 0),
                "architecture_changes": counts.get("architecture", 0),
                "ownership_records": counts.get("ownership", 0),
                "unresolved_questions": counts.get("unresolved", 0),
                "relationships": counts.get("relationships", 0),
            }
        }

        # Save to file
        summary_path = self.snapshots_dir / "project_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        logger.info(
            "Project summary refreshed",
            total_artifacts=summary["total_artifacts"],
            path=str(summary_path)
        )

        return summary

    def load_project_summary(self) -> Optional[Dict[str, Any]]:
        """
        Load project summary from disk.

        Returns:
            Project summary dictionary if exists, None otherwise
        """
        summary_path = self.snapshots_dir / "project_summary.json"

        if not summary_path.exists():
            logger.warning("Project summary not found")
            return None

        try:
            with open(summary_path, 'r', encoding='utf-8') as f:
                summary = json.load(f)

            logger.info("Project summary loaded")
            return summary

        except Exception as e:
            logger.error("Failed to load project summary", error=str(e))
            return None

    def _get_latest_artifacts(
        self,
        artifact_type: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get latest artifacts of a given type.

        Args:
            artifact_type: Type of artifact
            limit: Maximum number of artifacts to return

        Returns:
            List of artifact summaries
        """
        try:
            artifact_ids = self.json_store.list_artifacts(artifact_type)

            # Load artifacts and extract summaries
            artifacts = []
            for artifact_id in artifact_ids[:limit]:
                artifact = self.json_store.get_artifact(artifact_type, artifact_id)
                if artifact:
                    summary = self._artifact_to_summary(artifact)
                    artifacts.append(summary)

            # Sort by timestamp (most recent first)
            artifacts.sort(
                key=lambda x: x.get("timestamp", ""),
                reverse=True
            )

            return artifacts[:limit]

        except Exception as e:
            logger.error(
                "Failed to get latest artifacts",
                artifact_type=artifact_type,
                error=str(e)
            )
            return []

    def _artifact_to_summary(self, artifact: Any) -> Dict[str, Any]:
        """
        Convert artifact to summary dictionary.

        Args:
            artifact: Artifact instance

        Returns:
            Summary dictionary
        """
        summary = {
            "id": artifact.id,
            "title": getattr(artifact, "title", ""),
            "timestamp": getattr(artifact, "timestamp", datetime.now()).isoformat()
            if hasattr(artifact, "timestamp") else datetime.now().isoformat(),
        }

        # Add type-specific fields
        if hasattr(artifact, "confidence"):
            summary["confidence"] = artifact.confidence

        if hasattr(artifact, "summary"):
            summary["summary"] = artifact.summary[:200]  # Truncate

        if hasattr(artifact, "severity"):
            summary["severity"] = artifact.severity

        if hasattr(artifact, "status"):
            summary["status"] = artifact.status

        if hasattr(artifact, "event_type"):
            summary["event_type"] = artifact.event_type

        if hasattr(artifact, "change_type"):
            summary["change_type"] = artifact.change_type

        if hasattr(artifact, "entity_name"):
            summary["entity_name"] = artifact.entity_name
            summary["entity_type"] = artifact.entity_type

        if hasattr(artifact, "source_refs") and artifact.source_refs:
            summary["source_count"] = len(artifact.source_refs)
            summary["primary_source"] = artifact.source_refs[0].url

        return summary

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get project statistics.

        Returns:
            Statistics dictionary
        """
        counts = self.json_store.get_all_counts()

        return {
            "total_artifacts": sum(counts.values()),
            "by_type": counts,
            "generated_at": datetime.now().isoformat()
        }


# Made with Bob
