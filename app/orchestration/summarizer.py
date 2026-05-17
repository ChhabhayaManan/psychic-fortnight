"""Summary orchestration for retrieved evidence."""

from __future__ import annotations

from app.orchestration.agents import EvidenceSummaryAgent, GraphSummaryAgent, TimelineSummaryAgent
from app.orchestration.state import QueryState


class QuerySummarizer:
    """Run specialized summary agents over retrieved query context."""

    def __init__(self):
        self.evidence_agent = EvidenceSummaryAgent()
        self.timeline_agent = TimelineSummaryAgent()
        self.graph_agent = GraphSummaryAgent()

    def summarize(self, state: QueryState) -> QueryState:
        """Populate evidence, timeline, and graph summaries in state."""
        state.evidence_summary = self.evidence_agent.summarize(state.reranked_evidence)
        state.timeline_summary = self.timeline_agent.summarize(state.timeline_results)
        state.graph_summary = self.graph_agent.summarize(state.graph_results)
        return state

