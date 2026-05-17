"""Orchestration node for query-time retrieval."""

from __future__ import annotations

from typing import Any, Optional

from app.memory.graph_store import GraphStore
from app.memory.json_store import JsonStore
from app.orchestration.state import QueryState
from app.retrieval.hybrid import HybridRetriever


class RetrievalOrchestrator:
    """Run the retrieval plan and write results back into query state."""

    def __init__(
        self,
        json_store: JsonStore,
        vector_store: Optional[Any] = None,
        graph_store: Optional[GraphStore] = None,
    ):
        self.hybrid_retriever = HybridRetriever(
            json_store=json_store,
            vector_store=vector_store,
            graph_store=graph_store,
        )

    def retrieve(self, state: QueryState) -> QueryState:
        """Execute retrieval for the current state."""
        result = self.hybrid_retriever.search(state.request, state.retrieval_plan)
        state.timeline_results = result.timeline_context
        state.graph_results = result.graph_context
        state.evidence = result.evidence
        state.reranked_evidence = result.evidence
        state.limitations.extend(
            limitation for limitation in result.limitations if limitation not in state.limitations
        )
        return state

