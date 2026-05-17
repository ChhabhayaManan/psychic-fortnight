"""Timeline event extraction agent using LLM."""

import json
from datetime import datetime
from typing import Any, Dict, List

from app.extraction.base_extractor import BaseExtractor
from app.models import TimelineEvent
from app.utils.logging import get_logger

logger = get_logger(__name__)

_PROMPT = """You are an engineering intelligence system. Analyze this GitHub PR or Issue and extract it as a significant engineering timeline event — something worth remembering in the project history.

Every merged PR or closed issue with meaningful content is a timeline event. Focus on: feature releases, bug fixes, deployments, breaking changes, milestones, refactors, deprecations.

PR/Issue Data:
Title: {title}
Description: {description}
State: {state}
Merged: {merged}
Labels: {labels}
Author: {author}
Created: {created_at}
Merged/Closed: {closed_at}

Return a JSON object:
{{
  "is_timeline_event": true,
  "event_type": "<feature|bugfix|refactor|deployment|deprecation|breaking_change|release|milestone|other>",
  "title": "<concise event title>",
  "summary": "<1-2 sentence summary of what this event represents>",
  "related_entities": ["<service or component name>"],
  "tags": ["<tag1>", "<tag2>"]
}}

If this PR/Issue has NO engineering significance (e.g., typo fix, docs update only, WIP/draft), return:
{{"is_timeline_event": false}}

Return ONLY the JSON, no explanation."""


class TimelineExtractor(BaseExtractor):
    """Extract timeline events from GitHub PRs and issues using LLM."""

    def get_artifact_type(self) -> str:
        return "timeline"

    async def extract(self, raw_data: Dict[str, Any]) -> List[TimelineEvent]:
        metadata = raw_data.get("metadata", {})
        title = metadata.get("title", "")
        description = raw_data.get("description", "") or ""
        state = metadata.get("state", "open")
        merged = raw_data.get("merged", False)
        labels = metadata.get("labels", [])
        author = metadata.get("author", "unknown")

        # Only process closed/merged items — open drafts rarely matter for timeline
        if state == "open" and not merged:
            return []

        # Skip very trivial changes
        trivial = ["typo", "docs only", "wip", "draft", "chore: bump", "dependabot"]
        text = title.lower()
        if any(t in text for t in trivial) and len(description) < 50:
            return []

        try:
            from app.config.llm_config import get_llm_config
            llm_config = get_llm_config()
            if not llm_config.validate_llm_ready():
                logger.warning("LLM not configured — skipping timeline extraction")
                return []

            llm = llm_config.get_extraction_llm()
            prompt = _PROMPT.format(
                title=title,
                description=description[:1500],
                state=state,
                merged=merged,
                labels=labels,
                author=author,
                created_at=metadata.get("created_at", ""),
                closed_at=metadata.get("closed_at") or metadata.get("merged_at", "")
            )

            print(f"[EXTRACT] 📅 TimelineExtractor → LLM analyzing: {title[:60]}")
            response = await llm.ainvoke(prompt)
            raw_text = response.content if hasattr(response, "content") else str(response)

            raw_text = raw_text.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
            data = json.loads(raw_text.strip())

            if not data.get("is_timeline_event"):
                return []

            source_refs = self.build_source_references(raw_data)
            if not source_refs:
                return []

            event = TimelineEvent(
                event_type=data.get("event_type", "other"),
                title=data.get("title", title)[:200],
                summary=data.get("summary", "")[:500],
                related_entities=data.get("related_entities", []),
                related_decisions=[],
                related_incidents=[],
                contributors=self.extract_contributors(raw_data),
                tags=data.get("tags", []) + labels,
                source_refs=source_refs,
                timestamp=self._parse_timestamp(
                    metadata.get("merged_at") or metadata.get("closed_at") or metadata.get("created_at")
                ),
                created_at=datetime.now(),
                metadata={}
            )

            self.log_extraction("timeline", 1, source_refs[0].source_id)
            print(f"[EXTRACT] ✅ Timeline event: [{event.event_type}] {event.title[:50]}")
            return [event]

        except Exception as e:
            logger.error("TimelineExtractor failed", error=str(e))
            print(f"[EXTRACT] ❌ TimelineExtractor error: {e}")
            return []
