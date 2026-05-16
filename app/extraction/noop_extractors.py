"""Safe no-op extractors for artifact lanes that are not implemented yet."""

from typing import Any, Dict, List

from app.extraction.base_extractor import BaseExtractor


class NoOpExtractor(BaseExtractor):
    """Extractor that exposes an artifact lane without emitting artifacts."""

    artifact_type: str = ""

    async def extract(self, raw_data: Dict[str, Any]) -> List[Any]:
        """Return no artifacts until the lane gets a real extractor."""
        return []

    def get_artifact_type(self) -> str:
        """Return the artifact type handled by this lane."""
        return self.artifact_type


class IncidentExtractor(NoOpExtractor):
    artifact_type = "incident"


class TimelineExtractor(NoOpExtractor):
    artifact_type = "timeline"


class ArchitectureExtractor(NoOpExtractor):
    artifact_type = "architecture"


class OwnershipExtractor(NoOpExtractor):
    artifact_type = "ownership"


class UnresolvedExtractor(NoOpExtractor):
    artifact_type = "unresolved"


class RelationshipExtractor(NoOpExtractor):
    artifact_type = "relationship"

