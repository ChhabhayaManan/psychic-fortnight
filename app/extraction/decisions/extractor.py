"""Decision extraction agent."""

from typing import Any, Dict, List

from app.extraction.base_extractor import BaseExtractor
from app.models import Decision
from app.utils.logging import get_logger

logger = get_logger(__name__)


class DecisionExtractor(BaseExtractor):
    """
    Extract engineering decisions from GitHub PRs and issues.

    Looks for decision-making patterns in titles, descriptions,
    and discussions.
    """

    def get_artifact_type(self) -> str:
        """Get artifact type."""
        return "decision"

    async def extract(self, raw_data: Dict[str, Any]) -> List[Decision]:
        """
        Extract decisions from raw data.

        Args:
            raw_data: Raw GitHub PR or issue data

        Returns:
            List of Decision objects
        """
        decisions = []

        # Get basic information
        metadata = raw_data.get("metadata", {})
        title = metadata.get("title", "")
        description = raw_data.get("description", "")

        # Check if this looks like a decision
        if not self._is_decision(title, description, metadata):
            return decisions

        # Build source references
        source_refs = self.build_source_references(raw_data)
        if not source_refs:
            logger.warning("No source references found, skipping")
            return decisions

        # Extract decision details
        decision_title = self._extract_title(title)
        summary = self._extract_summary(description)
        reasoning = self._extract_reasoning(description, raw_data)
        confidence = self._calculate_confidence(title, description, metadata)

        # Check confidence threshold
        if not self.meets_confidence_threshold(confidence):
            logger.debug(
                f"Decision confidence too low: {confidence}",
                title=decision_title
            )
            return decisions

        # Extract related entities
        related_services = self.extract_services(title + " " + description)
        contributors = self.extract_contributors(raw_data)
        tags = self._extract_tags(metadata, title, description)

        # Create decision
        decision = Decision(
            title=decision_title,
            summary=summary,
            reasoning=reasoning,
            confidence=confidence,
            related_services=related_services,
            contributors=contributors,
            tags=tags,
            source_refs=source_refs,
            timestamp=self._parse_timestamp(metadata.get("created_at"))
        )

        decisions.append(decision)

        self.log_extraction("decisions", len(decisions), source_refs[0].source_id)

        return decisions

    def _is_decision(
        self,
        title: str,
        description: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Check if this looks like a decision.

        Args:
            title: PR/issue title
            description: PR/issue description
            metadata: Metadata

        Returns:
            True if looks like a decision
        """
        # Decision keywords
        decision_keywords = [
            "decide", "decision", "choose", "adopt", "migrate",
            "switch", "replace", "deprecate", "architecture",
            "design", "approach", "strategy", "rfc", "adr"
        ]

        text = (title + " " + description).lower()

        # Check for decision keywords
        for keyword in decision_keywords:
            if keyword in text:
                return True

        # Check labels
        labels = metadata.get("labels", [])
        decision_labels = ["decision", "architecture", "design", "rfc", "adr"]
        for label in labels:
            if any(dl in label.lower() for dl in decision_labels):
                return True

        return False

    def _extract_title(self, title: str) -> str:
        """Extract decision title."""
        # Clean up title
        title = title.strip()

        # Limit length
        if len(title) > 200:
            title = title[:197] + "..."

        return title

    def _extract_summary(self, description: str) -> str:
        """Extract decision summary."""
        # Take first paragraph or first 500 characters
        paragraphs = description.split("\n\n")
        summary = paragraphs[0] if paragraphs else description

        # Clean up
        summary = summary.strip()

        # Ensure minimum length
        if len(summary) < 10:
            summary = description[:500] if len(description) > 500 else description

        return summary

    def _extract_reasoning(
        self,
        description: str,
        raw_data: Dict[str, Any]
    ) -> str:
        """Extract decision reasoning."""
        # Look for reasoning sections
        reasoning_markers = [
            "## Reasoning",
            "## Rationale",
            "## Why",
            "## Motivation",
            "### Reasoning",
            "### Rationale"
        ]

        for marker in reasoning_markers:
            if marker in description:
                # Extract section after marker
                parts = description.split(marker, 1)
                if len(parts) > 1:
                    # Get text until next section or end
                    reasoning = parts[1].split("##")[0].strip()
                    if len(reasoning) > 10:
                        return reasoning

        # Fallback: use description
        return description[:1000] if len(description) > 1000 else description

    def _calculate_confidence(
        self,
        title: str,
        description: str,
        metadata: Dict[str, Any]
    ) -> float:
        """
        Calculate confidence score for decision extraction.

        Args:
            title: PR/issue title
            description: PR/issue description
            metadata: Metadata

        Returns:
            Confidence score (0.0 to 1.0)
        """
        confidence = 0.5  # Base confidence

        text = (title + " " + description).lower()

        # Strong decision indicators
        strong_indicators = ["rfc", "adr", "architecture decision"]
        for indicator in strong_indicators:
            if indicator in text:
                confidence += 0.2

        # Decision keywords
        decision_keywords = ["decide", "decision", "adopt", "migrate"]
        keyword_count = sum(1 for kw in decision_keywords if kw in text)
        confidence += min(keyword_count * 0.05, 0.15)

        # Has reasoning section
        if "reasoning" in text or "rationale" in text:
            confidence += 0.1

        # Has decision label
        labels = metadata.get("labels", [])
        if any("decision" in label.lower() or "architecture" in label.lower()
               for label in labels):
            confidence += 0.1

        # Description length (longer = more detailed)
        if len(description) > 500:
            confidence += 0.05

        # Cap at 1.0
        return min(confidence, 1.0)

    def _extract_tags(
        self,
        metadata: Dict[str, Any],
        title: str,
        description: str
    ) -> List[str]:
        """Extract tags for decision."""
        tags = set()

        # Add labels as tags
        labels = metadata.get("labels", [])
        tags.update(labels)

        # Add decision-specific tags
        tags.add("decision")

        # Add technology tags based on content
        tech_keywords = {
            "grpc": "grpc",
            "rest": "rest",
            "graphql": "graphql",
            "kubernetes": "kubernetes",
            "docker": "docker",
            "microservice": "microservices",
            "database": "database",
            "cache": "caching",
            "queue": "messaging"
        }

        text = (title + " " + description).lower()
        for keyword, tag in tech_keywords.items():
            if keyword in text:
                tags.add(tag)

        return list(tags)


# Made with Bob
