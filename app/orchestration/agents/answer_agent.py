"""Final source-grounded answer agent."""

from __future__ import annotations

from typing import List

from app.orchestration.state import EvidenceItem, QueryRequest, QueryResponse, unique_source_refs
from app.prompts.answer_generation import ANSWER_GENERATION_PROMPT


class AnswerAgent:
    """Generate final answers from retrieved evidence and summaries."""

    def __init__(self, use_llm: bool = False, llm_config: object | None = None):
        self.use_llm = use_llm
        self.llm_config = llm_config

    def generate(
        self,
        request: QueryRequest,
        query_type: str,
        evidence: List[EvidenceItem],
        evidence_summary: str,
        timeline_summary: str = "",
        graph_summary: str = "",
        limitations: List[str] | None = None,
    ) -> QueryResponse:
        """Return a source-grounded answer response."""
        limitations = list(limitations or [])
        if not evidence:
            if "No source-backed evidence was retrieved." not in limitations:
                limitations.append("No source-backed evidence was retrieved.")
            return QueryResponse(
                answer=(
                    "I do not have enough stored engineering memory to answer this "
                    "from source-backed evidence."
                ),
                query_type=query_type,
                confidence=0.0,
                limitations=limitations,
                metadata={"answer_mode": "insufficient_evidence"},
            )

        llm_answer = self._generate_with_llm(
            request=request,
            query_type=query_type,
            evidence_summary=evidence_summary,
            timeline_summary=timeline_summary,
            graph_summary=graph_summary,
            limitations=limitations,
        )
        if llm_answer:
            confidence = self._answer_confidence(evidence, limitations)
            return QueryResponse(
                answer=llm_answer,
                query_type=query_type,
                confidence=confidence,
                sources=unique_source_refs(evidence),
                evidence=evidence,
                limitations=limitations,
                metadata={"answer_mode": "watsonx"},
            )

        top = evidence[0]
        parts = [self._lead_sentence(request, query_type, top)]
        if evidence_summary:
            parts.append(f"Evidence:\n{evidence_summary}")
        if timeline_summary:
            parts.append(f"Timeline:\n{timeline_summary}")
        if graph_summary:
            parts.append(f"Graph context:\n{graph_summary}")
        if limitations:
            parts.append("Limitations:\n" + "\n".join(f"- {item}" for item in limitations))

        confidence = self._answer_confidence(evidence, limitations)
        return QueryResponse(
            answer="\n\n".join(parts),
            query_type=query_type,
            confidence=confidence,
            sources=unique_source_refs(evidence),
            evidence=evidence,
            limitations=limitations,
            metadata={"answer_mode": "evidence_only"},
        )

    def _generate_with_llm(
        self,
        request: QueryRequest,
        query_type: str,
        evidence_summary: str,
        timeline_summary: str,
        graph_summary: str,
        limitations: List[str],
    ) -> str:
        if not self.use_llm:
            return ""
        try:
            llm_config = self.llm_config
            if llm_config is None:
                from app.config.llm_config import get_llm_config

                llm_config = get_llm_config()
            llm = llm_config.get_summarization_llm()
            prompt = self._build_prompt(
                request=request,
                query_type=query_type,
                evidence_summary=evidence_summary,
                timeline_summary=timeline_summary,
                graph_summary=graph_summary,
                limitations=limitations,
            )
            result = llm.invoke(prompt) if hasattr(llm, "invoke") else llm(prompt)
            return str(result).strip()
        except Exception as exc:
            limitations.append(f"Watsonx answer generation unavailable: {exc}")
            return ""

    def _build_prompt(
        self,
        request: QueryRequest,
        query_type: str,
        evidence_summary: str,
        timeline_summary: str,
        graph_summary: str,
        limitations: List[str],
    ) -> str:
        return "\n\n".join(
            [
                ANSWER_GENERATION_PROMPT,
                f"Query type: {query_type}",
                f"User query: {request.query}",
                f"Evidence summary:\n{evidence_summary}",
                f"Timeline summary:\n{timeline_summary or 'No timeline context.'}",
                f"Graph summary:\n{graph_summary or 'No graph context.'}",
                f"Limitations:\n{chr(10).join(limitations) if limitations else 'None'}",
            ]
        )

    def _lead_sentence(self, request: QueryRequest, query_type: str, top: EvidenceItem) -> str:
        detail = top.summary or top.title
        reasoning = top.metadata.get("reasoning")
        root_cause = top.metadata.get("root_cause")
        if query_type == "decision" and reasoning:
            return f"The strongest stored evidence is `{top.title}`: {detail} {reasoning}"
        if query_type == "incident" and root_cause:
            return f"The strongest stored incident evidence is `{top.title}`: {detail} Root cause: {root_cause}"
        return f"The strongest stored evidence is `{top.title}`: {detail}"

    def _answer_confidence(self, evidence: List[EvidenceItem], limitations: List[str]) -> float:
        if not evidence:
            return 0.0
        base = sum(item.confidence * max(item.relevance_score, 0.1) for item in evidence[:5])
        denom = sum(max(item.relevance_score, 0.1) for item in evidence[:5])
        confidence = base / denom if denom else 0.0
        if limitations:
            confidence *= 0.85
        return max(0.0, min(confidence, 1.0))
