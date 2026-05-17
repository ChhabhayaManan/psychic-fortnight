# Step 4: LangGraph Orchestration Plan

## Objective

Implement a dynamic LangGraph workflow for engineering-memory questions.

The graph coordinates planning, retrieval, summarization, and answer generation.
It should route work based on the question type and available evidence.

## Query State

Implement `app/orchestration/state.py` as the shared state contract.

Required state fields:

- `request`: original `QueryRequest`.
- `query`: normalized query text.
- `query_type`: primary query type.
- `secondary_query_types`: optional related types.
- `retrieval_plan`: selected retrieval strategies and filters.
- `semantic_results`: semantic evidence.
- `timeline_results`: ordered timeline evidence.
- `graph_results`: graph paths and related entities.
- `snapshot_context`: project summary sections when used.
- `evidence`: merged and deduplicated evidence.
- `reranked_evidence`: final ranked evidence.
- `evidence_summary`: condensed evidence summary.
- `timeline_summary`: timeline-specific summary.
- `graph_summary`: graph-specific summary.
- `answer`: final answer text.
- `sources`: final cited sources.
- `confidence`: answer confidence.
- `limitations`: known gaps or weak evidence.
- `errors`: recoverable node errors.

State should be serializable so later workflow persistence is possible.

## Graph Nodes

Implement the workflow in `app/orchestration/graph.py`.

Planned nodes:

- `plan_query`
- `retrieve_semantic`
- `retrieve_timeline`
- `retrieve_graph`
- `load_snapshot_context`
- `aggregate_evidence`
- `rerank_evidence`
- `summarize_evidence`
- `summarize_timeline`
- `summarize_graph`
- `generate_answer`
- `handle_insufficient_evidence`

## Routing Rules

Use conditional routing after planning.

Required behavior:

- Decision questions use semantic retrieval and related graph context.
- Incident questions use semantic retrieval, timeline context, and related
  decisions when present.
- Timeline questions use timeline retrieval first, then semantic and graph
  context.
- Architecture questions use semantic retrieval, timeline context, and graph
  traversal.
- Ownership questions use graph traversal and contributor-related evidence.
- Unresolved-question queries use unresolved artifacts and related decisions.
- Relationship questions use graph traversal first, then semantic evidence.
- General questions use hybrid retrieval.

If a selected retrieval path fails, the workflow should continue with remaining
paths and record the failure in `limitations` or `errors`.

## Retrieval Plan

Implement `app/orchestration/planner.py` as the planner boundary.

The planner should output:

- primary query type.
- secondary query types.
- artifact type filters.
- entity hints.
- contributor hints.
- time-range hints.
- whether timeline retrieval is needed.
- whether graph retrieval is needed.
- whether snapshot context is useful.

The planner can use the Watsonx reasoning model through `LLMConfig`, but it
must return structured data. If the model call fails, use deterministic keyword
fallback classification.

## Retrieval Node

Implement `app/orchestration/retrieval.py` as the orchestration wrapper around
retrievers.

Required behavior:

- Call the selected retrievers from the planner output.
- Preserve typed evidence from each retriever.
- Attach retrieval metadata, including strategy and score.
- Do not perform final answer generation.

## Error Handling

Required behavior:

- Missing vector index should not break graph-only or timeline-only queries.
- Missing graph file should not break semantic-only queries.
- Missing timeline artifacts should produce a limitation, not a crash.
- If no evidence is found, route to `handle_insufficient_evidence`.

## Acceptance Criteria

- The graph can execute a basic query end to end.
- Different query types take different paths.
- Failed optional retrieval paths are captured as limitations.
- The final state contains answer, evidence, sources, confidence, and
  limitations.
- The orchestration layer does not know about Streamlit.

