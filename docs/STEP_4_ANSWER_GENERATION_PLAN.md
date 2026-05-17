# Step 4: Answer Generation Plan

## Objective

Implement the answer generation layer that turns retrieved evidence into clear,
source-grounded engineering-memory answers.

This layer uses Watsonx/Watson AI models through the existing configuration
boundary and specialized agents for evidence, timeline, graph, and final answer
generation.

## Model Boundary

Use the existing LLM configuration boundary:

```text
app/config/llm_config.py
```

Required behavior:

- Use `LLMConfig.get_reasoning_llm()` for planning and complex synthesis.
- Use `LLMConfig.get_summarization_llm()` for evidence, timeline, and graph
  summaries.
- Keep provider-specific details outside the agents.
- Return structured outputs from all agents where practical.
- If the model is unavailable, return a limitation instead of fabricating an
  answer.

## Agent Files

Create a separate answer-generation agent layer:

```text
app/orchestration/agents/
+-- evidence_summary_agent.py
+-- timeline_summary_agent.py
+-- graph_summary_agent.py
+-- answer_agent.py
```

Prompt modules:

```text
app/prompts/evidence_summarization.py
app/prompts/timeline_summarization.py
app/prompts/graph_summarization.py
app/prompts/answer_generation.py
```

## Evidence Summary Agent

Required behavior:

- Input: ranked evidence artifacts.
- Output: compact evidence summary with artifact ids and source references.
- Group evidence by artifact type when useful.
- Highlight contradictions or missing provenance.
- Do not remove source references needed by the final answer.

## Timeline Summary Agent

Required behavior:

- Input: ordered timeline context.
- Output: chronological summary and key transitions.
- Preserve event timestamps.
- Mark gaps where events are missing or uncertain.
- Keep source references attached to summarized events.

## Graph Summary Agent

Required behavior:

- Input: graph paths, related nodes, relationship metadata, linked artifacts.
- Output: relationship summary and important connected entities.
- Distinguish direct evidence from graph traversal hints.
- Mark weak or indirect paths.

## Final Answer Agent

Implement `app/orchestration/agents/answer_agent.py`.

Required behavior:

- Input:
  - query
  - query type
  - evidence summary
  - timeline summary when available
  - graph summary when available
  - ranked evidence
  - limitations
- Output:
  - concise answer
  - reasoning summary
  - cited sources
  - confidence
  - limitations

The final answer must not use knowledge that is absent from the retrieved
evidence or provided summaries.

## Source Citation Rules

Every final response should follow these rules:

- Cite PRs, issues, comments, reviews, contributors, and timestamps when
  available.
- Prefer direct artifact source references over graph-only context.
- If a claim comes from multiple artifacts, cite the strongest few sources.
- If evidence is weak, say what is missing.
- If no evidence supports the query, say the system does not have enough stored
  memory to answer.

## Answer Style

Answers should be:

- concise but complete.
- explicit about reasoning.
- clear about uncertainty.
- grounded in source references.
- suitable for future display in a UI.

The response should avoid generic chatbot phrasing. It should behave like an
engineering memory system explaining what the organization knows and why.

## Insufficient Evidence Handling

If evidence is empty or too weak:

- Return a short answer stating that stored memory is insufficient.
- Include searched artifact types and retrieval strategies in metadata.
- Include limitations.
- Do not invent possible explanations.

## Acceptance Criteria

- Final answers are grounded in retrieved Step 3 artifacts.
- Answers include sources and limitations.
- Timeline and graph summaries remain separate inputs to final synthesis.
- Watsonx/Watson AI is accessed only through the config boundary.
- Model failures do not produce fabricated answers.
- The answer layer has no Streamlit dependency.

