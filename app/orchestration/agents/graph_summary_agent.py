"""Graph summary agent."""

from __future__ import annotations

from typing import List

from app.orchestration.state import GraphContextItem


class GraphSummaryAgent:
    """Summarize graph paths and attached evidence."""

    def summarize(self, graph_context: List[GraphContextItem]) -> str:
        """Return a relationship-oriented graph summary."""
        if not graph_context:
            return ""
        lines = []
        for item in graph_context[:5]:
            relation_text = " -> ".join(item.path)
            lines.append(
                f"- {relation_text} "
                f"(confidence {item.confidence:.2f}, relevance {item.relevance_score:.2f})"
            )
        return "\n".join(lines)

