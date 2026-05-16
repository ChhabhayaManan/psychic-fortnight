"""Query workflow construction."""

from __future__ import annotations

from typing import Any, Optional

from app.memory.graph_store import GraphStore
from app.memory.json_store import JsonStore
from app.memory.snapshots import SnapshotStore
from app.orchestration.answer import generate_answer
from app.orchestration.planner import QueryPlanner
from app.orchestration.retrieval import RetrievalOrchestrator
from app.orchestration.state import QueryState
from app.orchestration.summarizer import QuerySummarizer


class QueryWorkflow:
    """Small workflow facade with the same `invoke` shape as LangGraph apps."""

    def __init__(
        self,
        json_store: JsonStore,
        vector_store: Optional[Any] = None,
        graph_store: Optional[GraphStore] = None,
        snapshot_store: Optional[SnapshotStore] = None,
    ):
        self.planner = QueryPlanner()
        self.retrieval = RetrievalOrchestrator(
            json_store=json_store,
            vector_store=vector_store,
            graph_store=graph_store,
            snapshot_store=snapshot_store,
        )
        self.summarizer = QuerySummarizer()

    def invoke(self, state: QueryState | dict) -> QueryState:
        """Execute the query workflow."""
        if isinstance(state, dict):
            state = QueryState(**state)
        state = self.plan_query(state)
        state = self.retrieve(state)
        if not state.reranked_evidence:
            state.limitations.append("No ranked evidence is available for final answer generation.")
        state = self.summarize(state)
        state = generate_answer(state)
        return state

    def plan_query(self, state: QueryState) -> QueryState:
        """Planner node."""
        plan = self.planner.plan(state.request)
        state.retrieval_plan = plan
        state.query_type = plan.query_type
        state.secondary_query_types = plan.secondary_query_types
        return state

    def retrieve(self, state: QueryState) -> QueryState:
        """Retrieval node."""
        return self.retrieval.retrieve(state)

    def summarize(self, state: QueryState) -> QueryState:
        """Summary node."""
        return self.summarizer.summarize(state)


class LangGraphQueryWorkflow:
    """LangGraph-backed workflow wrapper with the same public `invoke` API."""

    def __init__(self, fallback_workflow: QueryWorkflow):
        self.fallback_workflow = fallback_workflow
        self.app = self._compile()

    def invoke(self, state: QueryState | dict) -> QueryState:
        """Execute the compiled LangGraph workflow."""
        if isinstance(state, QueryState):
            state_dict = state.model_dump(mode="python")
        else:
            state_dict = state
        result = self.app.invoke(state_dict)
        return QueryState(**result)

    def _compile(self) -> Any:
        """Compile the LangGraph workflow."""
        from langgraph.graph import END, StateGraph

        workflow = StateGraph(dict)
        workflow.add_node("plan_query", self._wrap_node(self.fallback_workflow.plan_query))
        workflow.add_node("retrieve", self._wrap_node(self.fallback_workflow.retrieve))
        workflow.add_node("summarize", self._wrap_node(self.fallback_workflow.summarize))
        workflow.add_node("generate_answer", self._wrap_node(generate_answer))

        workflow.set_entry_point("plan_query")
        workflow.add_edge("plan_query", "retrieve")
        workflow.add_edge("retrieve", "summarize")
        workflow.add_edge("summarize", "generate_answer")
        workflow.add_edge("generate_answer", END)
        return workflow.compile()

    def _wrap_node(self, node_function: Any) -> Any:
        def wrapped(state: dict) -> dict:
            query_state = QueryState(**state)
            query_state = node_function(query_state)
            return query_state.model_dump(mode="python")

        return wrapped


def build_query_graph(
    json_store: JsonStore,
    vector_store: Optional[Any] = None,
    graph_store: Optional[GraphStore] = None,
    snapshot_store: Optional[SnapshotStore] = None,
) -> QueryWorkflow | LangGraphQueryWorkflow:
    """Build the Step 4 query workflow.

    The returned object exposes `invoke`. When LangGraph is installed, this
    returns a compiled LangGraph wrapper. If graph compilation fails, it falls
    back to the same deterministic workflow nodes.
    """
    fallback = QueryWorkflow(
        json_store=json_store,
        vector_store=vector_store,
        graph_store=graph_store,
        snapshot_store=snapshot_store,
    )
    try:
        return LangGraphQueryWorkflow(fallback)
    except Exception:
        return fallback
