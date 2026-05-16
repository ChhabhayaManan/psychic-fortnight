"""Evidence deduplication and reranking."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List

from app.orchestration.state import EvidenceItem


class EvidenceReranker:
    """Merge duplicate evidence and rank the strongest source-backed items."""

    def rerank(self, evidence: Iterable[EvidenceItem], top_k: int = 8) -> List[EvidenceItem]:
        """Deduplicate evidence by artifact id/type and return ranked items."""
        merged: dict[tuple[str, str], EvidenceItem] = {}
        for item in evidence:
            key = (item.artifact_type, item.artifact_id)
            if key not in merged:
                merged[key] = item
                continue
            existing = merged[key]
            existing.relevance_score = max(existing.relevance_score, item.relevance_score)
            existing.confidence = max(existing.confidence, item.confidence)
            existing.source_refs = self._merge_sources(existing.source_refs, item.source_refs)
            existing.raw_data_paths = sorted(set(existing.raw_data_paths + item.raw_data_paths))
            existing.metadata = {**existing.metadata, **item.metadata}

        ranked = list(merged.values())
        ranked.sort(key=self._rank_key, reverse=True)
        return ranked[:top_k]

    def _rank_key(self, item: EvidenceItem) -> tuple[float, float, float, int]:
        return (
            item.relevance_score,
            item.confidence,
            self._recency_score(item),
            len(item.source_refs),
        )

    def _recency_score(self, item: EvidenceItem) -> float:
        timestamp = item.metadata.get("timestamp")
        if not timestamp and item.source_refs:
            timestamp = item.source_refs[0].get("timestamp")
        if not timestamp:
            return 0.0
        try:
            parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            age_days = max((datetime.now(timezone.utc) - parsed).days, 0)
            return 1.0 / (1.0 + age_days)
        except ValueError:
            return 0.0

    def _merge_sources(self, left: List[dict], right: List[dict]) -> List[dict]:
        seen: set[tuple[str, str, str]] = set()
        merged: List[dict] = []
        for ref in [*left, *right]:
            key = (
                str(ref.get("source_type", "")),
                str(ref.get("source_id", "")),
                str(ref.get("url", "")),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(ref)
        return merged

