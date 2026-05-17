"""Architecture change extraction agent using LLM."""

import json
from datetime import datetime
from typing import Any, Dict, List

from app.extraction.base_extractor import BaseExtractor
from app.models import ArchitectureChange
from app.utils.logging import get_logger

logger = get_logger(__name__)

_PROMPT = """You are an engineering intelligence system. Analyze the following GitHub PR or Issue and determine whether it represents an architecture change — e.g. new service, technology migration, database change, API redesign, infrastructure update, dependency upgrade with impact, design pattern change.

PR/Issue Data:
Title: {title}
Description: {description}
Labels: {labels}
Files changed (if available): {files}
Comments (sample): {comments}

Return a JSON object. If this is NOT an architecture change, return {{"is_architecture_change": false}}.
If it IS, return:
{{
  "is_architecture_change": true,
  "confidence": <0.0-1.0>,
  "title": "<concise title>",
  "summary": "<1-2 sentence summary>",
  "change_type": "<new_service|migration|refactor|infrastructure|api_change|database|dependency|other>",
  "before_state": "<what existed before, if mentioned>",
  "after_state": "<what it becomes>",
  "affected_services": ["<service1>"],
  "tags": ["<tag1>"]
}}

Return ONLY the JSON, no explanation."""


class ArchitectureExtractor(BaseExtractor):
    """Extract architecture changes from GitHub PRs and issues using LLM."""

    def get_artifact_type(self) -> str:
        return "architecture"

    async def extract(self, raw_data: Dict[str, Any]) -> List[ArchitectureChange]:
        metadata = raw_data.get("metadata", {})
        title = metadata.get("title", "")
        description = raw_data.get("description", "") or ""
        labels = metadata.get("labels", [])

        arch_keywords = [
            "migrate", "migration", "refactor", "rewrite", "replace", "move to",
            "switch to", "adopt", "introduce", "new service", "new api", "redesign",
            "architecture", "infra", "infrastructure", "database", "deploy", "kubernetes",
            "docker", "microservice", "monolith", "breaking change", "deprecate"
        ]
        text = (title + " " + description + " " + " ".join(labels)).lower()
        if not any(kw in text for kw in arch_keywords):
            return []

        commits_sample = " | ".join(
            c.get("message", "")[:100] for c in raw_data.get("commits", [])[:5]
        )
        comments_sample = " | ".join(
            c.get("body", "")[:200] for c in raw_data.get("comments", [])[:3]
        )

        try:
            from app.config.llm_config import get_llm_config
            llm_config = get_llm_config()
            if not llm_config.validate_llm_ready():
                logger.warning("LLM not configured — skipping architecture extraction")
                return []

            llm = llm_config.get_extraction_llm()
            prompt = _PROMPT.format(
                title=title,
                description=description[:2000],
                labels=labels,
                files=f"~{raw_data.get('files_changed', 0)} files changed",
                comments=comments_sample[:500]
            )

            print(f"[EXTRACT] 🏗️  ArchitectureExtractor → LLM analyzing: {title[:60]}")
            response = await llm.ainvoke(prompt)
            raw_text = response.content if hasattr(response, "content") else str(response)

            raw_text = raw_text.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
            data = json.loads(raw_text.strip())

            if not data.get("is_architecture_change"):
                return []

            confidence = float(data.get("confidence", 0.7))
            if not self.meets_confidence_threshold(confidence):
                return []

            source_refs = self.build_source_references(raw_data)
            if not source_refs:
                return []

            now = datetime.now()
            change = ArchitectureChange(
                title=data.get("title", title)[:200],
                summary=data.get("summary", "")[:500],
                change_type=data.get("change_type", "other"),
                before_state=data.get("before_state"),
                after_state=data.get("after_state"),
                confidence=confidence,
                affected_services=data.get("affected_services", []),
                contributors=self.extract_contributors(raw_data),
                tags=data.get("tags", []) + labels,
                source_refs=source_refs,
                timestamp=self._parse_timestamp(metadata.get("created_at")),
                created_at=now,
                updated_at=now,
                metadata={}
            )

            self.log_extraction("architecture", 1, source_refs[0].source_id)
            print(f"[EXTRACT] ✅ Architecture change found: {change.title[:60]}")
            return [change]

        except Exception as e:
            logger.error("ArchitectureExtractor failed", error=str(e))
            print(f"[EXTRACT] ❌ ArchitectureExtractor error: {e}")
            return []
