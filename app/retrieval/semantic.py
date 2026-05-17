"""Semantic and lexical retrieval over stored memory artifacts."""

from __future__ import annotations

import re
from typing import Any, Iterable, List, Optional

from app.memory.json_store import JsonStore
from app.orchestration.state import EvidenceItem, QueryRequest, artifact_to_evidence

DEFAULT_ARTIFACT_TYPES = [
    "decisions",
    "incidents",
    "architecture",
    "ownership",
    "unresolved",
    "timeline",
]


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "did",
    "do",
    "does",
    "for",
    "from",
    "how",
    "in",
    "is",
    "of",
    "on",
    "the",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
}


def tokenize(text: str) -> List[str]:
    """Tokenize query or artifact text for deterministic fallback scoring."""
    return [
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token and token not in STOPWORDS
    ]


def artifact_text(artifact: Any) -> str:
    """Build searchable text from a typed artifact."""
    if hasattr(artifact, "to_embedding_text"):
        return artifact.to_embedding_text()
    fields = [
        "title",
        "summary",
        "reasoning",
        "root_cause",
        "resolution",
        "question",
        "context",
        "evidence_summary",
        "description",
        "event_type",
        "change_type",
        "entity_name",
        "entity_type",
    ]
    values = [str(getattr(artifact, field, "")) for field in fields]
    for field in [
        "related_services",
        "affected_services",
        "related_entities",
        "contributors",
        "tags",
        "owners",
    ]:
        values.extend(str(value) for value in getattr(artifact, field, []) or [])
    return "\n".join(value for value in values if value)


def lexical_score(query: str, text: str) -> float:
    """Score text by query-token overlap."""
    query_tokens = tokenize(query)
    if not query_tokens:
        return 0.0
    text_tokens = set(tokenize(text))
    matches = sum(1 for token in query_tokens if token in text_tokens)
    score = matches / len(query_tokens)
    if query.lower() in text.lower():
        score += 0.5
    return score


def artifact_matches_filters(artifact: Any, request: QueryRequest) -> bool:
    """Apply source, contributor, service, and time filters."""
    if request.contributors:
        contributors = {value.lower() for value in getattr(artifact, "contributors", []) or []}
        owners = {value.lower() for value in getattr(artifact, "owners", []) or []}
        requested = {value.lower() for value in request.contributors}
        if not requested.intersection(contributors | owners):
            return False

    if request.services:
        service_values: set[str] = set()
        for field in [
            "related_services",
            "affected_services",
            "related_entities",
            "tags",
        ]:
            service_values.update(str(value).lower() for value in getattr(artifact, field, []) or [])
        entity_name = getattr(artifact, "entity_name", "")
        if entity_name:
            service_values.add(str(entity_name).lower())
        requested_services = {value.lower() for value in request.services}
        if not requested_services.intersection(service_values):
            return False

    if request.source_id:
        source_id = request.source_id.lower()
        refs = getattr(artifact, "source_refs", []) or []
        source_match = False
        for ref in refs:
            raw_path = str(getattr(ref, "raw_data_path", "") or "").lower()
            ref_source_id = str(getattr(ref, "source_id", "") or "").lower()
            if source_id in raw_path or source_id == ref_source_id:
                source_match = True
                break
        metadata = getattr(artifact, "metadata", {}) or {}
        if source_id == str(metadata.get("source_id", "")).lower():
            source_match = True
        if not source_match:
            return False

    if request.time_range and not request.time_range.contains(getattr(artifact, "timestamp", None)):
        return False

    return True


class SemanticRetriever:
    """Retrieve source-backed artifacts using Chroma when available, then JSON fallback."""

    def __init__(self, json_store: JsonStore, vector_store: Optional[Any] = None):
        self.json_store = json_store
        self.vector_store = vector_store

    def search(self, request: QueryRequest) -> List[EvidenceItem]:
        """Return ranked evidence for a query."""
        artifact_types = request.artifact_types or DEFAULT_ARTIFACT_TYPES
        if self.vector_store is not None:
            vector_results = self._search_vector_store(request, artifact_types)
            if vector_results:
                return vector_results[: request.top_k]
        return self._search_json_store(request, artifact_types)[: request.top_k]

    def _search_vector_store(
        self,
        request: QueryRequest,
        artifact_types: Iterable[str],
    ) -> List[EvidenceItem]:
        evidence: List[EvidenceItem] = []
        seen: set[tuple[str, str]] = set()
        for artifact_type in artifact_types:
            where = {"artifact_type": artifact_type}
            results = self.vector_store.search(
                request.query,
                n_results=request.top_k,
                filter_metadata=where,
            )
            for result in results:
                metadata = result.get("metadata", {}) or {}
                result_type = metadata.get("artifact_type", artifact_type)
                artifact_id = metadata.get("artifact_id", result.get("id", ""))
                key = (str(result_type), str(artifact_id))
                if key in seen:
                    continue
                seen.add(key)
                artifact = self.json_store.get_artifact(str(result_type), str(artifact_id))
                distance = result.get("distance")
                relevance = 1.0 / (1.0 + float(distance)) if distance is not None else 0.5
                if artifact and artifact_matches_filters(artifact, request):
                    evidence.append(
                        artifact_to_evidence(
                            str(result_type),
                            artifact,
                            relevance_score=relevance,
                            metadata={"retrieval": "vector", **metadata},
                        )
                    )
                elif not artifact:
                    evidence.append(
                        EvidenceItem(
                            artifact_id=str(artifact_id),
                            artifact_type=str(result_type),
                            title=str(metadata.get("title", "")),
                            summary=str(result.get("document", "")),
                            confidence=float(metadata.get("confidence", 0.5) or 0.5),
                            relevance_score=relevance,
                            metadata={"retrieval": "vector", **metadata},
                        )
                    )
        evidence.sort(key=lambda item: (item.relevance_score, item.confidence), reverse=True)
        return evidence

    def _search_json_store(
        self,
        request: QueryRequest,
        artifact_types: Iterable[str],
    ) -> List[EvidenceItem]:
        evidence: List[EvidenceItem] = []
        for artifact_type in artifact_types:
            try:
                artifact_ids = self.json_store.list_artifacts(artifact_type)
            except ValueError:
                continue
            for artifact_id in artifact_ids:
                artifact = self.json_store.get_artifact(artifact_type, artifact_id)
                if not artifact or not artifact_matches_filters(artifact, request):
                    continue
                score = lexical_score(request.query, artifact_text(artifact))
                if score <= 0 and request.artifact_types:
                    score = 0.05
                if score <= 0:
                    continue
                evidence.append(
                    artifact_to_evidence(
                        artifact_type,
                        artifact,
                        relevance_score=score,
                        metadata={"retrieval": "lexical"},
                    )
                )
        evidence.sort(key=lambda item: (item.relevance_score, item.confidence), reverse=True)
        return evidence

