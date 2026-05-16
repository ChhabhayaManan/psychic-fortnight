"""Hybrid retrieval across semantic, timeline, graph, and snapshot context."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.memory.graph_store import GraphStore
from app.memory.json_store import JsonStore
from app.memory.snapshots import SnapshotStore
from app.orchestration.state import (
    EvidenceItem,
    GraphContextItem,
    QueryRequest,
    RetrievalPlan,
    TimelineContextItem,
)
from app.retrieval.graph_search import GraphSearcher
from app.retrieval.reranking import EvidenceReranker
from app.retrieval.semantic import SemanticRetriever
from app.retrieval.timeline import TimelineRetriever


@dataclass
class HybridSearchResult:
    """Combined retrieval output consumed by orchestration."""

    evidence: List[EvidenceItem] = field(default_factory=list)
    timeline_context: List[TimelineContextItem] = field(default_factory=list)
    graph_context: List[GraphContextItem] = field(default_factory=list)
    snapshot_context: Dict[str, Any] = field(default_factory=dict)
    limitations: List[str] = field(default_factory=list)


class HybridRetriever:
    """Coordinate query-time retrieval strategies."""

    def __init__(
        self,
        json_store: JsonStore,
        vector_store: Optional[Any] = None,
        graph_store: Optional[GraphStore] = None,
        snapshot_store: Optional[SnapshotStore] = None,
    ):
        self.json_store = json_store
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.snapshot_store = snapshot_store
        self.reranker = EvidenceReranker()

    def search(self, request: QueryRequest, plan: Optional[RetrievalPlan] = None) -> HybridSearchResult:
        """Run selected retrieval strategies and merge their evidence."""
        plan = plan or RetrievalPlan()
        evidence: List[EvidenceItem] = []
        timeline_context: List[TimelineContextItem] = []
        graph_context: List[GraphContextItem] = []
        limitations: List[str] = []
        snapshot_context: Dict[str, Any] = {}

        if plan.artifact_types and not request.artifact_types:
            request = request.model_copy(update={"artifact_types": plan.artifact_types})

        if plan.use_semantic:
            semantic_results = SemanticRetriever(self.json_store, self.vector_store).search(request)
            evidence.extend(semantic_results)
            if not semantic_results:
                limitations.append("No semantic evidence matched the query.")

        if plan.use_timeline or request.include_timeline:
            timeline_context = TimelineRetriever(self.json_store).search(request)
            for item in timeline_context:
                evidence.append(
                    EvidenceItem(
                        artifact_id=item.event_id,
                        artifact_type="timeline",
                        title=item.title,
                        summary=item.summary,
                        confidence=item.confidence,
                        relevance_score=item.relevance_score,
                        source_refs=item.source_refs,
                        raw_data_paths=[
                            ref.get("raw_data_path")
                            for ref in item.source_refs
                            if isinstance(ref, dict) and ref.get("raw_data_path")
                        ],
                        metadata={"retrieval": "timeline", "event_type": item.event_type},
                    )
                )
            if not timeline_context:
                limitations.append("No timeline events matched the query.")

        if plan.use_graph or request.include_graph:
            if self.graph_store is None:
                limitations.append("Knowledge graph is unavailable for this query.")
            else:
                graph_context = GraphSearcher(self.graph_store, self.json_store).search(request)
                for item in graph_context:
                    evidence.extend(item.related_artifacts)
                if not graph_context:
                    limitations.append("No graph relationships matched the query.")

        if plan.use_snapshot and self.snapshot_store is not None:
            snapshot_context = self.snapshot_store.load_project_summary() or {}
            if not snapshot_context:
                limitations.append("Project snapshot is unavailable.")

        reranked = self.reranker.rerank(evidence, top_k=request.top_k)
        return HybridSearchResult(
            evidence=reranked,
            timeline_context=timeline_context,
            graph_context=graph_context,
            snapshot_context=snapshot_context,
            limitations=limitations,
        )

