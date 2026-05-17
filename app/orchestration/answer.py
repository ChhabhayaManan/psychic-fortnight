"""Public answer-generation entrypoint."""

from __future__ import annotations

from typing import Any, Optional

from app.memory.graph_store import GraphStore
from app.memory.json_store import JsonStore
from app.orchestration.agents import AnswerAgent
from app.orchestration.state import QueryRequest, QueryResponse, QueryState


def default_json_store() -> JsonStore:
    """Create the default extracted artifact store."""
    from app.config.settings import get_settings

    settings = get_settings()
    return JsonStore(settings.extracted_data_dir)


def default_graph_store() -> Optional[GraphStore]:
    """Create the default graph store when graph dependencies are available."""
    try:
        from app.config.settings import get_settings

        settings = get_settings()
        return GraphStore(settings.graph_data_dir)
    except Exception:
        return None


def answer_query(
    request: QueryRequest | dict,
    json_store: Optional[JsonStore] = None,
    vector_store: Optional[Any] = None,
    graph_store: Optional[GraphStore] = None,
) -> QueryResponse:
    """Run the Step 4 backend query workflow and return a structured response."""
    if isinstance(request, dict):
        request = QueryRequest(**request)
    use_default_stores = json_store is None
    json_store = json_store or default_json_store()
    if graph_store is None and use_default_stores:
        graph_store = default_graph_store()

    from app.orchestration.graph import build_query_graph

    workflow = build_query_graph(
        json_store=json_store,
        vector_store=vector_store,
        graph_store=graph_store,
    )
    final_state = workflow.invoke(QueryState(request=request, query=request.query))
    if isinstance(final_state, dict):
        final_state = QueryState(**final_state)
    return QueryResponse(
        answer=final_state.answer,
        query_type=final_state.query_type,
        confidence=final_state.confidence,
        sources=final_state.sources,
        evidence=final_state.reranked_evidence,
        timeline_context=final_state.timeline_results,
        graph_context=final_state.graph_results,
        limitations=final_state.limitations,
        metadata={
            "retrieval_plan": final_state.retrieval_plan.model_dump(mode="json")
            if final_state.retrieval_plan
            else {},
            "errors": final_state.errors,
        },
    )


def generate_answer(state: QueryState) -> QueryState:
    """Populate final answer fields in query state."""
    response = AnswerAgent().generate(
        request=state.request,
        query_type=state.query_type,
        evidence=state.reranked_evidence,
        evidence_summary=state.evidence_summary,
        timeline_summary=state.timeline_summary,
        graph_summary=state.graph_summary,
        limitations=state.limitations,
    )
    state.answer = response.answer
    state.sources = response.sources
    state.confidence = response.confidence
    state.limitations = response.limitations
    return state
