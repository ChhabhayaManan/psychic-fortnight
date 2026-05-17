"""Timeline summary agent."""

from __future__ import annotations

from typing import List

from app.orchestration.state import TimelineContextItem


class TimelineSummaryAgent:
    """Summarize ordered timeline context."""

    def summarize(self, timeline: List[TimelineContextItem]) -> str:
        """Return a chronological timeline summary."""
        if not timeline:
            return ""
        lines = []
        for item in timeline:
            timestamp = item.timestamp.isoformat() if item.timestamp else "unknown time"
            lines.append(f"- {timestamp}: {item.title} - {item.summary}")
        return "\n".join(lines)

