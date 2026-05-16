import os
from datetime import datetime, timedelta

os.environ.setdefault("WATSONX_API_KEY", "test-key")
os.environ.setdefault("WATSONX_PROJECT_ID", "test-project")
os.environ.setdefault("LOG_FORMAT", "text")

from app.memory.graph_store import GraphStore
from app.memory.json_store import JsonStore
from app.models import Decision, SourceReference, SourceType, TimelineEvent
from app.orchestration.answer import answer_query
from app.orchestration.state import QueryRequest
from app.retrieval.graph_search import GraphSearcher
from app.retrieval.timeline import TimelineRetriever


def make_source(source_id: str = "42") -> SourceReference:
    return SourceReference(
        source_type=SourceType.PR,
        source_id=source_id,
        url=f"https://github.com/acme/project/pull/{source_id}",
        contributor="alice",
        timestamp=datetime(2024, 1, 1, 10, 0, 0),
        raw_data_path=f"data/raw/github/acme_project/prs/{source_id}.json",
    )


def test_timeline_retriever_returns_relevant_events_in_chronological_order(tmp_path):
    json_store = JsonStore(tmp_path / "extracted")
    source = make_source()
    earlier = TimelineEvent(
        id="evt_1",
        event_type="architecture_change",
        title="Auth service introduced",
        summary="The team split authentication into auth-service.",
        related_entities=["auth-service"],
        source_refs=[source],
        timestamp=datetime(2024, 1, 1, 9, 0, 0),
    )
    later = TimelineEvent(
        id="evt_2",
        event_type="migration",
        title="Auth service moved to gRPC",
        summary="The team migrated auth-service calls to gRPC.",
        related_entities=["auth-service", "grpc"],
        source_refs=[source],
        timestamp=datetime(2024, 2, 1, 9, 0, 0),
    )
    unrelated = TimelineEvent(
        id="evt_3",
        event_type="incident",
        title="Billing retry issue fixed",
        summary="The team fixed retries in billing-service.",
        related_entities=["billing-service"],
        source_refs=[source],
        timestamp=datetime(2024, 1, 15, 9, 0, 0),
    )
    json_store.store_artifact("timeline", later)
    json_store.store_artifact("timeline", unrelated)
    json_store.store_artifact("timeline", earlier)

    request = QueryRequest(query="How did auth-service architecture evolve?")
    results = TimelineRetriever(json_store).search(request)

    assert [item.event_id for item in results] == ["evt_1", "evt_2"]
    assert all(item.source_refs for item in results)


def test_graph_searcher_returns_paths_with_linked_artifact_sources(tmp_path):
    json_store = JsonStore(tmp_path / "extracted")
    graph_store = GraphStore(tmp_path / "graph")
    decision = Decision(
        id="dec_redis",
        title="Remove Redis from auth-service",
        summary="The team removed Redis from auth-service session storage.",
        reasoning="Redis caused stale session reads during deploys.",
        confidence=0.9,
        related_services=["auth-service", "redis"],
        source_refs=[make_source("77")],
        timestamp=datetime.now() - timedelta(days=1),
    )
    json_store.store_artifact("decisions", decision)
    graph_store.upsert_artifact_node("decisions", decision)
    graph_store.save()

    request = QueryRequest(query="How is auth-service related to Redis?")
    results = GraphSearcher(graph_store, json_store).search(request)

    assert results
    assert results[0].related_artifacts
    assert results[0].source_refs


def test_answer_query_uses_evidence_and_cites_sources(tmp_path):
    json_store = JsonStore(tmp_path / "extracted")
    decision = Decision(
        id="dec_redis",
        title="Remove Redis from auth-service",
        summary="Redis was removed from auth-service session storage.",
        reasoning="The PR explains that Redis caused stale session reads during rolling deploys.",
        confidence=0.92,
        related_services=["auth-service", "redis"],
        source_refs=[make_source("88")],
        timestamp=datetime.now(),
    )
    json_store.store_artifact("decisions", decision)

    response = answer_query(
        QueryRequest(query="Why was Redis removed from auth-service?"),
        json_store=json_store,
    )

    assert "Redis" in response.answer
    assert response.sources
    assert response.evidence
    assert response.query_type == "decision"
    assert response.confidence > 0

