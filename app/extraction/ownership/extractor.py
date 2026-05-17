"""Ownership extraction agent using LLM."""

import json
from datetime import datetime
from typing import Any, Dict, List

from app.extraction.base_extractor import BaseExtractor
from app.models import OwnershipMemory
from app.utils.logging import get_logger

logger = get_logger(__name__)

_PROMPT = """You are an engineering intelligence system. Analyze this GitHub PR or Issue to identify component or service ownership — i.e., which engineers or teams own, maintain, or are responsible for specific services, modules, or components.

PR/Issue Data:
Title: {title}
Description: {description}
Author: {author}
Assignees: {assignees}
Labels: {labels}
Reviewers who approved: {reviewers}
Files changed: ~{files_changed} files

Look for: who is the primary author of changes to a service/component, who reviews/approves changes, who is assigned issues for specific systems.

Return a JSON list of ownership records found. Each entry:
{{
  "entity_name": "<service, component, or module name>",
  "entity_type": "<service|module|component|api|database|infrastructure|other>",
  "owners": ["<github_username1>", "<github_username2>"],
  "evidence_summary": "<1 sentence explaining why these are the owners>",
  "confidence": <0.0-1.0>
}}

Return an empty list [] if no clear ownership can be inferred.
Return ONLY a valid JSON array, no explanation."""


class OwnershipExtractor(BaseExtractor):
    """Extract ownership signals from GitHub PRs and issues using LLM."""

    def get_artifact_type(self) -> str:
        return "ownership"

    async def extract(self, raw_data: Dict[str, Any]) -> List[OwnershipMemory]:
        metadata = raw_data.get("metadata", {})
        title = metadata.get("title", "")
        description = raw_data.get("description", "") or ""
        author = metadata.get("author", "unknown")
        assignees = metadata.get("assignees", [])
        labels = metadata.get("labels", [])
        files_changed = raw_data.get("files_changed", 0)

        reviewers = [
            r.get("author") for r in raw_data.get("reviews", [])
            if r.get("state") in ("APPROVED", "CHANGES_REQUESTED") and r.get("author")
        ]

        # Need at least author + some code change signals
        if not author or author == "unknown":
            return []

        try:
            from app.config.llm_config import get_llm_config
            llm_config = get_llm_config()
            if not llm_config.validate_llm_ready():
                logger.warning("LLM not configured — skipping ownership extraction")
                return []

            llm = llm_config.get_extraction_llm()
            prompt = _PROMPT.format(
                title=title,
                description=description[:1500],
                author=author,
                assignees=assignees,
                labels=labels,
                reviewers=reviewers,
                files_changed=files_changed
            )

            print(f"[EXTRACT] 👤 OwnershipExtractor → LLM analyzing: {title[:60]}")
            response = await llm.ainvoke(prompt)
            raw_text = response.content if hasattr(response, "content") else str(response)

            raw_text = raw_text.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
            records_data = json.loads(raw_text.strip())

            if not isinstance(records_data, list):
                return []

            source_refs = self.build_source_references(raw_data)
            if not source_refs:
                return []

            results = []
            now = datetime.now()
            for rec in records_data:
                confidence = float(rec.get("confidence", 0.6))
                if not self.meets_confidence_threshold(confidence):
                    continue
                if not rec.get("entity_name") or not rec.get("owners"):
                    continue

                ownership = OwnershipMemory(
                    entity_name=rec["entity_name"][:200],
                    entity_type=rec.get("entity_type", "other"),
                    owners=rec["owners"],
                    evidence_summary=rec.get("evidence_summary", "")[:500],
                    confidence=confidence,
                    source_refs=source_refs,
                    timestamp=self._parse_timestamp(metadata.get("created_at")),
                    created_at=now,
                    updated_at=now,
                    metadata={}
                )
                results.append(ownership)

            if results:
                self.log_extraction("ownership", len(results), source_refs[0].source_id)
                print(f"[EXTRACT] ✅ Ownership records: {len(results)} found")
            return results

        except Exception as e:
            logger.error("OwnershipExtractor failed", error=str(e))
            print(f"[EXTRACT] ❌ OwnershipExtractor error: {e}")
            return []
