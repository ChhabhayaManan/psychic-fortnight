"""Incident extraction agent using LLM."""

import json
from datetime import datetime
from typing import Any, Dict, List

from app.extraction.base_extractor import BaseExtractor
from app.models import Incident
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Prompt template
_PROMPT = """You are an engineering intelligence system. Analyze the following GitHub PR or Issue and determine whether it describes or relates to a production incident, outage, bug, or system failure.

PR/Issue Data:
Title: {title}
Description: {description}
Labels: {labels}
State: {state}
Comments (sample): {comments}

Return a JSON object. If this is NOT an incident, return {{"is_incident": false}}.
If it IS an incident, return:
{{
  "is_incident": true,
  "title": "<concise incident title>",
  "summary": "<1-2 sentence summary of what happened>",
  "root_cause": "<root cause if identifiable, else null>",
  "resolution": "<how it was resolved if mentioned, else null>",
  "severity": "<critical|high|medium|low>",
  "affected_services": ["<service1>", "<service2>"],
  "impact_description": "<what was impacted>",
  "tags": ["<tag1>", "<tag2>"]
}}

Return ONLY the JSON, no explanation."""


class IncidentExtractor(BaseExtractor):
    """Extract production incidents from GitHub PRs and issues using LLM."""

    def get_artifact_type(self) -> str:
        return "incident"

    async def extract(self, raw_data: Dict[str, Any]) -> List[Incident]:
        metadata = raw_data.get("metadata", {})
        title = metadata.get("title", "")
        description = raw_data.get("description", "") or ""
        labels = metadata.get("labels", [])
        state = metadata.get("state", "")

        # Quick keyword pre-filter to avoid wasting LLM calls
        incident_keywords = [
            "incident", "outage", "bug", "crash", "failure", "error",
            "hotfix", "fix:", "fix!", "rollback", "revert", "down", "broken",
            "regression", "alert", "pagerduty", "on-call", "postmortem", "p0", "p1"
        ]
        text = (title + " " + description + " " + " ".join(labels)).lower()
        if not any(kw in text for kw in incident_keywords):
            return []

        # Sample comments for context
        comments_sample = " | ".join(
            c.get("body", "")[:200] for c in raw_data.get("comments", [])[:3]
        )

        try:
            from app.config.llm_config import get_llm_config
            llm_config = get_llm_config()
            if not llm_config.validate_llm_ready():
                logger.warning("LLM not configured — skipping incident extraction")
                return []

            llm = llm_config.get_extraction_llm()
            prompt = _PROMPT.format(
                title=title,
                description=description[:2000],
                labels=labels,
                state=state,
                comments=comments_sample[:500]
            )

            print(f"[EXTRACT] 🔍 IncidentExtractor → LLM analyzing: {title[:60]}")
            response = await llm.ainvoke(prompt)
            raw_text = response.content if hasattr(response, "content") else str(response)

            # Parse JSON
            raw_text = raw_text.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
            data = json.loads(raw_text.strip())

            if not data.get("is_incident"):
                return []

            source_refs = self.build_source_references(raw_data)
            if not source_refs:
                return []

            now = datetime.now()
            incident = Incident(
                title=data.get("title", title)[:200],
                summary=data.get("summary", "")[:500],
                root_cause=data.get("root_cause"),
                resolution=data.get("resolution"),
                severity=data.get("severity", "medium"),
                affected_services=data.get("affected_services", []),
                impact_description=data.get("impact_description"),
                related_decisions=[],
                contributors=self.extract_contributors(raw_data),
                tags=data.get("tags", []) + labels,
                source_refs=source_refs,
                occurred_at=self._parse_timestamp(metadata.get("created_at")),
                resolved_at=self._parse_timestamp(metadata.get("closed_at")),
                timestamp=self._parse_timestamp(metadata.get("created_at")),
                created_at=now,
                updated_at=now,
                metadata={}
            )

            self.log_extraction("incident", 1, source_refs[0].source_id)
            print(f"[EXTRACT] ✅ Incident found: {incident.title[:60]}")
            return [incident]

        except Exception as e:
            logger.error("IncidentExtractor failed", error=str(e))
            print(f"[EXTRACT] ❌ IncidentExtractor error: {e}")
            return []
