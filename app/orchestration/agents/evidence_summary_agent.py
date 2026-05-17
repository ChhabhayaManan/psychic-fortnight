"""Evidence summary agent."""

from __future__ import annotations

from typing import List

from app.orchestration.state import EvidenceItem


class EvidenceSummaryAgent:
    """Create compact source-aware summaries from ranked evidence."""

    def summarize(self, evidence: List[EvidenceItem]) -> str:
        """Summarize evidence without removing provenance."""
        if not evidence:
            return "No source-backed evidence was retrieved."
        lines = []
        for index, item in enumerate(evidence[:6], start=1):
            detail = item.summary or item.title
            reason = item.metadata.get("reasoning") or item.metadata.get("root_cause")
            if reason:
                detail = f"{detail} Reasoning: {reason}"
            lines.append(
                f"{index}. [{item.artifact_type}:{item.artifact_id}] "
                f"{item.title}: {detail} "
                f"(confidence {item.confidence:.2f}, relevance {item.relevance_score:.2f})"
            )
        return "\n".join(lines)

