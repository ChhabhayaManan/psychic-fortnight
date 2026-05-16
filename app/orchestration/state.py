"""Query orchestration state and public query contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, field_validator

QUERY_TYPES = {
    "decision",
    "incident",
    "timeline",
    "architecture",
    "ownership",
    "unresolved",
    "relationship",
    "general",
}


ARTIFACT_TYPES = {
    "decisions",
    "incidents",
    "timeline",
    "architecture",
    "ownership",
    "unresolved",
    "relationships",
}


class TimeRange(BaseModel):
    """Optional timestamp range filter for query-time retrieval."""

    start: Optional[datetime] = None
    end: Optional[datetime] = None

    def contains(self, value: Optional[datetime]) -> bool:
        """Return whether a timestamp is inside this range."""
        if value is None:
            return True
        if self.start and value < self.start:
            return False
        if self.end and value > self.end:
            return False
        return True


class QueryRequest(BaseModel):
    """Structured backend query request."""

    query: str = Field(..., min_length=1)
    source_id: Optional[str] = None
    top_k: int = Field(default=8, ge=1, le=20)
    artifact_types: List[str] = Field(default_factory=list)
    contributors: List[str] = Field(default_factory=list)
    services: List[str] = Field(default_factory=list)
    time_range: Optional[TimeRange] = None
    include_timeline: Optional[bool] = None
    include_graph: Optional[bool] = None

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        """Trim query text and reject empty strings."""
        value = value.strip()
        if not value:
            raise ValueError("Query text cannot be empty")
        return value

    @field_validator("artifact_types")
    @classmethod
    def normalize_artifact_types(cls, values: List[str]) -> List[str]:
        """Normalize artifact type filters to plural storage names."""
        normalized = []
        aliases = {
            "decision": "decisions",
            "incident": "incidents",
            "event": "timeline",
            "timeline_event": "timeline",
            "architecture_change": "architecture",
            "owner": "ownership",
            "ownership_memory": "ownership",
            "question": "unresolved",
            "unresolved_question": "unresolved",
            "relationship": "relationships",
        }
        for value in values:
            key = value.strip().lower()
            key = aliases.get(key, key)
            if key in ARTIFACT_TYPES and key not in normalized:
                normalized.append(key)
        return normalized


class EvidenceItem(BaseModel):
    """One retrieved artifact or source-backed context item."""

    artifact_id: str
    artifact_type: str
    title: str = ""
    summary: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    relevance_score: float = Field(default=0.0, ge=0.0)
    source_refs: List[Dict[str, Any]] = Field(default_factory=list)
    raw_data_paths: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TimelineContextItem(BaseModel):
    """Timeline event context returned at query time."""

    event_id: str
    event_type: str
    title: str
    summary: str
    timestamp: Optional[datetime] = None
    related_entities: List[str] = Field(default_factory=list)
    related_artifacts: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    relevance_score: float = Field(default=0.0, ge=0.0)
    source_refs: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GraphContextItem(BaseModel):
    """Knowledge-graph context returned at query time."""

    start_node: str
    end_node: str
    path: List[str] = Field(default_factory=list)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    related_artifacts: List[EvidenceItem] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    relevance_score: float = Field(default=0.0, ge=0.0)
    source_refs: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RetrievalPlan(BaseModel):
    """Planner output used to route query-time retrieval."""

    query_type: str = "general"
    secondary_query_types: List[str] = Field(default_factory=list)
    artifact_types: List[str] = Field(default_factory=list)
    entity_hints: List[str] = Field(default_factory=list)
    contributor_hints: List[str] = Field(default_factory=list)
    use_semantic: bool = True
    use_timeline: bool = False
    use_graph: bool = False
    use_snapshot: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("query_type")
    @classmethod
    def validate_query_type(cls, value: str) -> str:
        """Keep planner classifications inside the known query taxonomy."""
        value = value.lower()
        return value if value in QUERY_TYPES else "general"


class QueryState(BaseModel):
    """Serializable state passed through the query workflow."""

    request: QueryRequest
    query: str
    query_type: str = "general"
    secondary_query_types: List[str] = Field(default_factory=list)
    retrieval_plan: Optional[RetrievalPlan] = None
    semantic_results: List[EvidenceItem] = Field(default_factory=list)
    timeline_results: List[TimelineContextItem] = Field(default_factory=list)
    graph_results: List[GraphContextItem] = Field(default_factory=list)
    snapshot_context: Dict[str, Any] = Field(default_factory=dict)
    evidence: List[EvidenceItem] = Field(default_factory=list)
    reranked_evidence: List[EvidenceItem] = Field(default_factory=list)
    evidence_summary: str = ""
    timeline_summary: str = ""
    graph_summary: str = ""
    answer: str = ""
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    limitations: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class QueryResponse(BaseModel):
    """Structured backend query response."""

    answer: str
    query_type: str = "general"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: List[EvidenceItem] = Field(default_factory=list)
    timeline_context: List[TimelineContextItem] = Field(default_factory=list)
    graph_context: List[GraphContextItem] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


def make_initial_state(request: QueryRequest) -> QueryState:
    """Create the initial state for a query workflow."""
    return QueryState(request=request, query=request.query)


def source_ref_to_dict(source_ref: Any) -> Dict[str, Any]:
    """Serialize source references from Pydantic models or plain dicts."""
    if source_ref is None:
        return {}
    if isinstance(source_ref, dict):
        return source_ref
    if hasattr(source_ref, "model_dump"):
        return source_ref.model_dump(mode="json")
    return dict(source_ref)


def artifact_to_evidence(
    artifact_type: str,
    artifact: Any,
    relevance_score: float = 0.0,
    metadata: Optional[Dict[str, Any]] = None,
) -> EvidenceItem:
    """Convert a typed memory artifact into a query evidence item."""
    source_refs = [source_ref_to_dict(ref) for ref in getattr(artifact, "source_refs", [])]
    raw_data_paths = [
        ref.get("raw_data_path")
        for ref in source_refs
        if isinstance(ref, dict) and ref.get("raw_data_path")
    ]
    title = getattr(artifact, "title", "") or getattr(artifact, "entity_name", "")
    summary = (
        getattr(artifact, "summary", "")
        or getattr(artifact, "evidence_summary", "")
        or getattr(artifact, "question", "")
        or getattr(artifact, "description", "")
    )
    confidence = float(getattr(artifact, "confidence", 0.5) or 0.5)
    enriched_metadata = dict(metadata or {})
    for field in [
        "reasoning",
        "root_cause",
        "resolution",
        "severity",
        "status",
        "event_type",
        "change_type",
        "related_services",
        "affected_services",
        "related_entities",
        "contributors",
        "owners",
        "timestamp",
    ]:
        value = getattr(artifact, field, None)
        if value is not None:
            if hasattr(value, "isoformat"):
                value = value.isoformat()
            enriched_metadata[field] = value
    return EvidenceItem(
        artifact_id=str(getattr(artifact, "id", "")),
        artifact_type=artifact_type,
        title=title,
        summary=summary,
        confidence=confidence,
        relevance_score=relevance_score,
        source_refs=source_refs,
        raw_data_paths=raw_data_paths,
        metadata=enriched_metadata,
    )


def unique_source_refs(items: List[EvidenceItem]) -> List[Dict[str, Any]]:
    """Collect unique source references from evidence items."""
    seen: set[Tuple[str, str, str]] = set()
    sources: List[Dict[str, Any]] = []
    for item in items:
        for ref in item.source_refs:
            key = (
                str(ref.get("source_type", "")),
                str(ref.get("source_id", "")),
                str(ref.get("url", "")),
            )
            if key not in seen:
                seen.add(key)
                sources.append(ref)
    return sources
