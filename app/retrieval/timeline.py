"""Timeline retrieval over extracted timeline artifacts."""

from __future__ import annotations

import re
from typing import List

from app.memory.json_store import JsonStore
from app.orchestration.state import QueryRequest, TimelineContextItem, source_ref_to_dict
from app.retrieval.semantic import artifact_matches_filters, artifact_text, lexical_score


class TimelineRetriever:
    """Load, score, and chronologically order timeline events."""

    def __init__(self, json_store: JsonStore):
        self.json_store = json_store

    def search(self, request: QueryRequest) -> List[TimelineContextItem]:
        """Return relevant timeline context in chronological order."""
        try:
            event_ids = self.json_store.list_artifacts("timeline")
        except ValueError:
            return []

        scored_items: List[tuple[float, TimelineContextItem]] = []
        exact_entity_terms = [
            value.lower()
            for value in re.findall(r"\b[a-z0-9]+(?:-[a-z0-9]+)+\b", request.query.lower())
        ]
        for event_id in event_ids:
            event = self.json_store.get_artifact("timeline", event_id)
            if not event or not artifact_matches_filters(event, request):
                continue
            searchable_text = artifact_text(event).lower()
            if exact_entity_terms and not any(term in searchable_text for term in exact_entity_terms):
                continue
            score = lexical_score(request.query, artifact_text(event))
            if request.include_timeline and score == 0:
                score = 0.05
            if score <= 0:
                continue
            confidence = float(getattr(event, "confidence", 0.7) or 0.7)
            source_refs = [source_ref_to_dict(ref) for ref in getattr(event, "source_refs", [])]
            related_artifacts = [
                *[str(value) for value in getattr(event, "related_decisions", []) or []],
                *[str(value) for value in getattr(event, "related_incidents", []) or []],
            ]
            scored_items.append(
                (
                    score,
                    TimelineContextItem(
                        event_id=str(event.id),
                        event_type=str(getattr(event, "event_type", "")),
                        title=str(getattr(event, "title", "")),
                        summary=str(getattr(event, "summary", "")),
                        timestamp=getattr(event, "timestamp", None),
                        related_entities=[str(value) for value in getattr(event, "related_entities", [])],
                        related_artifacts=related_artifacts,
                        confidence=confidence,
                        relevance_score=score,
                        source_refs=source_refs,
                        metadata={"retrieval": "timeline"},
                    ),
                )
            )

        scored_items.sort(
            key=lambda pair: (
                pair[1].timestamp is None,
                pair[1].timestamp,
                -pair[0],
            )
        )
        return [item for _, item in scored_items[: request.top_k]]
