"""Knowledge graph retrieval for relationship-heavy queries."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.memory.graph_store import GraphStore
from app.memory.json_store import JsonStore
from app.orchestration.state import (
    EvidenceItem,
    GraphContextItem,
    QueryRequest,
    artifact_to_evidence,
)
from app.retrieval.semantic import lexical_score, tokenize


class GraphSearcher:
    """Search graph nodes, traverse nearby relationships, and attach evidence."""

    def __init__(self, graph_store: GraphStore, json_store: Optional[JsonStore] = None):
        self.graph_store = graph_store
        self.json_store = json_store

    def search(self, request: QueryRequest, max_depth: int = 2) -> List[GraphContextItem]:
        """Return graph paths related to the query."""
        graph = self.graph_store.graph
        if graph.number_of_nodes() == 0:
            return []

        matched_nodes = self._match_nodes(request)
        if not matched_nodes:
            return []

        undirected = graph.to_undirected()
        results: List[GraphContextItem] = []
        seen_paths: set[tuple[str, ...]] = set()

        for start in matched_nodes:
            lengths = self._single_source_shortest_paths(undirected, start, max_depth)
            for end, path in lengths.items():
                if start == end or len(path) < 2:
                    continue
                if not any(node in matched_nodes and node != start for node in path):
                    if not self._path_has_artifact(graph, path):
                        continue
                key = tuple(path)
                reverse_key = tuple(reversed(path))
                if key in seen_paths or reverse_key in seen_paths:
                    continue
                seen_paths.add(key)
                item = self._build_context_item(request, path)
                if item:
                    results.append(item)

        results.sort(key=lambda item: (item.relevance_score, item.confidence), reverse=True)
        return results[: request.top_k]

    def _match_nodes(self, request: QueryRequest) -> List[str]:
        graph = self.graph_store.graph
        query_terms = set(tokenize(request.query))
        service_terms = set(tokenize(" ".join(request.services)))
        terms = query_terms | service_terms
        matched: List[tuple[float, str]] = []
        for node_id, attrs in graph.nodes(data=True):
            node_text = " ".join(
                [
                    str(node_id),
                    str(attrs.get("title", "")),
                    str(attrs.get("name", "")),
                    str(attrs.get("username", "")),
                    str(attrs.get("entity_type", "")),
                    str(attrs.get("artifact_type", "")),
                ]
            )
            score = lexical_score(" ".join(terms), node_text) if terms else 0
            if score > 0:
                matched.append((score, str(node_id)))
        matched.sort(reverse=True)
        return [node_id for _, node_id in matched[: max(request.top_k, 6)]]

    def _single_source_shortest_paths(self, graph: Any, start: str, cutoff: int) -> Dict[str, List[str]]:
        try:
            import networkx as nx

            return dict(nx.single_source_shortest_path(graph, start, cutoff=cutoff))
        except Exception:
            return {}

    def _path_has_artifact(self, graph: Any, path: List[str]) -> bool:
        return any(graph.nodes[node].get("node_type") == "artifact" for node in path if graph.has_node(node))

    def _build_context_item(self, request: QueryRequest, path: List[str]) -> Optional[GraphContextItem]:
        graph = self.graph_store.graph
        related_artifacts: List[EvidenceItem] = []
        source_refs: List[Dict[str, Any]] = []
        relationships: List[Dict[str, Any]] = []
        confidence_values: List[float] = []

        for source, target in zip(path, path[1:]):
            edge_data = graph.get_edge_data(source, target) or graph.get_edge_data(target, source) or {}
            relationship = {
                "source": source,
                "target": target,
                "relation_type": str(edge_data.get("relation_type", "related_to")),
                "description": str(edge_data.get("description", "")),
                "confidence": float(edge_data.get("confidence", 0.6) or 0.6),
            }
            relationships.append(relationship)
            confidence_values.append(relationship["confidence"])

        for node in path:
            attrs = graph.nodes[node]
            if attrs.get("node_type") != "artifact":
                continue
            artifact_type = str(attrs.get("artifact_type", ""))
            artifact = self.json_store.get_artifact(artifact_type, node) if self.json_store else None
            if artifact:
                evidence = artifact_to_evidence(
                    artifact_type,
                    artifact,
                    relevance_score=lexical_score(request.query, f"{evidence_text(attrs)} {node}"),
                    metadata={"retrieval": "graph", "node_id": node},
                )
                related_artifacts.append(evidence)
                source_refs.extend(evidence.source_refs)

        path_text = " ".join(path)
        score = lexical_score(request.query, path_text)
        if related_artifacts:
            score = max(score, max(item.relevance_score for item in related_artifacts), 0.1)
        confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0.5
        if not related_artifacts and score <= 0:
            return None
        return GraphContextItem(
            start_node=path[0],
            end_node=path[-1],
            path=path,
            relationships=relationships,
            related_artifacts=related_artifacts,
            confidence=confidence,
            relevance_score=score,
            source_refs=source_refs,
            metadata={"retrieval": "graph"},
        )


def evidence_text(attrs: Dict[str, Any]) -> str:
    """Build graph-node text for evidence relevance scoring."""
    return " ".join(str(value) for value in attrs.values() if value is not None)

