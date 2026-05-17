"""Query planning and retrieval routing."""

from __future__ import annotations

from app.orchestration.state import QueryRequest, RetrievalPlan
from app.retrieval.semantic import tokenize


class QueryPlanner:
    """Classify queries and select retrieval strategies."""

    DECISION_TERMS = {"why", "decision", "decided", "removed", "remove", "chosen", "choice"}
    INCIDENT_TERMS = {"incident", "outage", "bug", "failure", "root", "cause", "caused", "fix"}
    TIMELINE_TERMS = {"timeline", "evolve", "evolved", "history", "when", "before", "after", "sequence"}
    ARCHITECTURE_TERMS = {"architecture", "migration", "migrate", "grpc", "service", "dependency"}
    OWNERSHIP_TERMS = {"owner", "owns", "understands", "expert", "reviewer", "contributor", "who"}
    UNRESOLVED_TERMS = {"open", "unresolved", "question", "concern", "risk", "unknown"}
    RELATIONSHIP_TERMS = {"related", "relationship", "connect", "connected", "affect", "depends"}

    def plan(self, request: QueryRequest) -> RetrievalPlan:
        """Return a structured retrieval plan."""
        terms = set(tokenize(request.query))
        lowered = request.query.lower()
        query_type = self._classify(terms, lowered)
        secondary = self._secondary_types(query_type, terms, lowered)
        artifact_types = request.artifact_types or self._artifact_types_for(query_type)
        use_timeline = bool(request.include_timeline) or query_type in {
            "timeline",
            "incident",
            "architecture",
        }
        use_graph = bool(request.include_graph) or query_type in {
            "relationship",
            "ownership",
            "architecture",
            "incident",
            "decision",
        }
        entity_hints = self._entity_hints(request)
        return RetrievalPlan(
            query_type=query_type,
            secondary_query_types=secondary,
            artifact_types=artifact_types,
            entity_hints=entity_hints,
            contributor_hints=request.contributors,
            use_semantic=True,
            use_timeline=use_timeline,
            use_graph=use_graph,
            metadata={"planner": "deterministic"},
        )

    def _classify(self, terms: set[str], lowered_query: str) -> str:
        if terms.intersection(self.DECISION_TERMS) or lowered_query.startswith("why "):
            return "decision"
        if terms.intersection(self.OWNERSHIP_TERMS) and "who" in terms:
            return "ownership"
        if terms.intersection(self.RELATIONSHIP_TERMS):
            return "relationship"
        if terms.intersection(self.TIMELINE_TERMS):
            return "timeline"
        if terms.intersection(self.INCIDENT_TERMS):
            return "incident"
        if terms.intersection(self.ARCHITECTURE_TERMS):
            return "architecture"
        if terms.intersection(self.UNRESOLVED_TERMS):
            return "unresolved"
        return "general"

    def _secondary_types(self, query_type: str, terms: set[str], lowered_query: str) -> list[str]:
        candidates = []
        for name, name_terms in [
            ("decision", self.DECISION_TERMS),
            ("incident", self.INCIDENT_TERMS),
            ("timeline", self.TIMELINE_TERMS),
            ("architecture", self.ARCHITECTURE_TERMS),
            ("ownership", self.OWNERSHIP_TERMS),
            ("unresolved", self.UNRESOLVED_TERMS),
            ("relationship", self.RELATIONSHIP_TERMS),
        ]:
            if name != query_type and terms.intersection(name_terms):
                candidates.append(name)
        if lowered_query.startswith("why ") and query_type != "decision":
            candidates.append("decision")
        return candidates

    def _artifact_types_for(self, query_type: str) -> list[str]:
        mapping = {
            "decision": ["decisions", "architecture", "unresolved"],
            "incident": ["incidents", "decisions", "timeline"],
            "timeline": ["timeline", "decisions", "architecture", "incidents"],
            "architecture": ["architecture", "decisions", "timeline"],
            "ownership": ["ownership", "decisions", "architecture"],
            "unresolved": ["unresolved", "decisions"],
            "relationship": ["decisions", "incidents", "architecture", "ownership", "unresolved", "timeline"],
            "general": ["decisions", "incidents", "architecture", "ownership", "unresolved", "timeline"],
        }
        return mapping.get(query_type, mapping["general"])

    def _entity_hints(self, request: QueryRequest) -> list[str]:
        hints = list(request.services)
        for token in tokenize(request.query):
            if "-" in token and token not in hints:
                hints.append(token)
        return hints


def plan_query(request: QueryRequest) -> RetrievalPlan:
    """Convenience wrapper for query planning."""
    return QueryPlanner().plan(request)
