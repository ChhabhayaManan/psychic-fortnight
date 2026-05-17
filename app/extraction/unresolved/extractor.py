"""Unresolved question extraction agent using LLM."""

import json
from datetime import datetime
from typing import Any, Dict, List

from app.extraction.base_extractor import BaseExtractor
from app.models import UnresolvedQuestion
from app.utils.logging import get_logger

logger = get_logger(__name__)

_PROMPT = """You are an engineering intelligence system. Analyze this GitHub PR or Issue and identify any unresolved engineering questions, open debates, or pending decisions that were NOT conclusively resolved in this thread.

Look for: "should we?", "what about?", "TBD", "TODO", "open question", "need to decide", "unclear", questions in comments that got no answer, follow-up issues mentioned but not created.

PR/Issue Data:
Title: {title}
Description: {description}
State: {state}
Labels: {labels}
Comments: {comments}

Return a JSON list of unresolved questions found. Each entry:
{{
  "title": "<short title for the question>",
  "question": "<the actual question or concern>",
  "context": "<what this is in the context of>",
  "related_services": ["<service1>"],
  "confidence": <0.0-1.0>
}}

Return an empty list [] if everything is resolved or there are no open questions.
Return ONLY a valid JSON array, no explanation."""


class UnresolvedExtractor(BaseExtractor):
    """Extract unresolved engineering questions using LLM."""

    def get_artifact_type(self) -> str:
        return "unresolved"

    async def extract(self, raw_data: Dict[str, Any]) -> List[UnresolvedQuestion]:
        metadata = raw_data.get("metadata", {})
        title = metadata.get("title", "")
        description = raw_data.get("description", "") or ""
        state = metadata.get("state", "open")
        labels = metadata.get("labels", [])

        # Full comment thread is valuable here
        comments_text = "\n".join(
            f"[{c.get('author', '?')}]: {c.get('body', '')[:300]}"
            for c in raw_data.get("comments", [])[:10]
        )

        # Quick filter — need question signals
        unresolved_signals = [
            "?", "tbd", "todo", "open question", "should we", "not sure",
            "unclear", "need to", "follow up", "follow-up", "question",
            "discuss", "considering", "wondering", "debate"
        ]
        text = (title + " " + description + " " + comments_text).lower()
        if not any(sig in text for sig in unresolved_signals):
            return []

        try:
            from app.config.llm_config import get_llm_config
            llm_config = get_llm_config()
            if not llm_config.validate_llm_ready():
                logger.warning("LLM not configured — skipping unresolved extraction")
                return []

            llm = llm_config.get_extraction_llm()
            prompt = _PROMPT.format(
                title=title,
                description=description[:1000],
                state=state,
                labels=labels,
                comments=comments_text[:2000]
            )

            print(f"[EXTRACT] ❓ UnresolvedExtractor → LLM analyzing: {title[:60]}")
            response = await llm.ainvoke(prompt)
            raw_text = response.content if hasattr(response, "content") else str(response)

            raw_text = raw_text.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
            questions_data = json.loads(raw_text.strip())

            if not isinstance(questions_data, list):
                return []

            source_refs = self.build_source_references(raw_data)
            if not source_refs:
                return []

            results = []
            now = datetime.now()
            for q in questions_data:
                confidence = float(q.get("confidence", 0.6))
                if not self.meets_confidence_threshold(confidence):
                    continue
                if not q.get("question"):
                    continue

                question = UnresolvedQuestion(
                    title=q.get("title", "Open Question")[:200],
                    question=q["question"][:500],
                    context=q.get("context", "")[:500],
                    status="open",
                    related_services=q.get("related_services", []),
                    contributors=self.extract_contributors(raw_data),
                    confidence=confidence,
                    source_refs=source_refs,
                    timestamp=self._parse_timestamp(metadata.get("created_at")),
                    created_at=now,
                    updated_at=now,
                    resolved_at=None,
                    metadata={}
                )
                results.append(question)

            if results:
                self.log_extraction("unresolved", len(results), source_refs[0].source_id)
                print(f"[EXTRACT] ✅ Unresolved questions: {len(results)} found")
            return results

        except Exception as e:
            logger.error("UnresolvedExtractor failed", error=str(e))
            print(f"[EXTRACT] ❌ UnresolvedExtractor error: {e}")
            return []
