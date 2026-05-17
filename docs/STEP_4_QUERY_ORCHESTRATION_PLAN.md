# Step 4: Query Orchestration, Retrieval, Timeline, Graph, and Answering

## Objective

Implement the backend intelligence layer that answers engineering-memory
questions from the structured memory created in Step 3.

Step 4 consumes extracted artifacts, Chroma embeddings, NetworkX graph data,
project snapshots, and source provenance. It plans the query workflow,
retrieves relevant evidence, summarizes timeline and graph context, and
generates source-grounded answers.

Step 4 does not build the Streamlit interface. The final UI step will call the
backend entrypoints defined here.

## Automatic Query Flow

```text
User query
  -> query request validation
  -> query planner
  -> query type detection
  -> retrieval strategy selection
  -> semantic retrieval
  -> timeline retrieval when useful
  -> graph traversal when useful
  -> snapshot context when useful
  -> evidence aggregation
  -> reranking and deduplication
  -> evidence summary agent
  -> timeline summary agent when useful
  -> graph summary agent when useful
  -> final answer agent
  -> answer with sources and limitations
```

The workflow is dynamic. Decision questions, ownership questions, timeline
questions, incident questions, and relationship questions should not all use the
same retrieval path.

## Scope

In scope:

- Basic backend querying.
- Query request and response schemas.
- LangGraph orchestration.
- Query planning and retrieval routing.
- Semantic retrieval over ChromaDB artifacts.
- Timeline retrieval from extracted timeline events.
- Knowledge-graph traversal from the persisted graph.
- Hybrid evidence aggregation and reranking.
- Watsonx/Watson AI answer generation through the existing LLM config.
- Source-grounded final answers with provenance.

Not part of this step:

- GitHub ingestion.
- Raw-data extraction or Step 3 artifact creation.
- Streamlit pages or visual UI.
- New source connectors.
- Manual editing of memories.

## Input Data From Step 3

Step 4 reads these persisted outputs:

```text
data/extracted/decisions/
data/extracted/incidents/
data/extracted/timeline/
data/extracted/architecture/
data/extracted/ownership/
data/extracted/unresolved/
data/extracted/relationships/
data/embeddings/chroma/
data/graph/knowledge_graph.json
data/snapshots/project_summary.json
```

Every response must preserve the Step 3 provenance contract: answers are based
on typed artifacts and their source references, not loose generated summaries.

## Subsystem Plans

This Step 4 plan is split into focused implementation documents:

- `docs/STEP_4_BASIC_QUERYING_PLAN.md`
- `docs/STEP_4_LANGGRAPH_ORCHESTRATION_PLAN.md`
- `docs/STEP_4_TIMELINE_PLAN.md`
- `docs/STEP_4_KNOWLEDGE_GRAPH_PLAN.md`
- `docs/STEP_4_ANSWER_GENERATION_PLAN.md`

## Planned Backend Modules

Retrieval modules:

- `app/retrieval/semantic.py`
- `app/retrieval/timeline.py`
- `app/retrieval/graph_search.py`
- `app/retrieval/hybrid.py`
- `app/retrieval/reranking.py`

Orchestration modules:

- `app/orchestration/state.py`
- `app/orchestration/planner.py`
- `app/orchestration/retrieval.py`
- `app/orchestration/graph.py`
- `app/orchestration/answer.py`

Agent modules:

- `app/orchestration/agents/evidence_summary_agent.py`
- `app/orchestration/agents/timeline_summary_agent.py`
- `app/orchestration/agents/graph_summary_agent.py`
- `app/orchestration/agents/answer_agent.py`

Prompt modules:

- `app/prompts/query_planning.py`
- `app/prompts/evidence_summarization.py`
- `app/prompts/timeline_summarization.py`
- `app/prompts/graph_summarization.py`
- `app/prompts/answer_generation.py`

## Query Types

The planner should classify each query into one primary type and optional
secondary types:

- `decision`
- `incident`
- `timeline`
- `architecture`
- `ownership`
- `unresolved`
- `relationship`
- `general`

The selected type controls retrieval strategy, summarization needs, and final
answer format.

## Public Interfaces

### `answer_query(request)`

Main backend entrypoint for future UI and CLI usage.

Required behavior:

- Accept a `QueryRequest`.
- Execute the LangGraph query workflow.
- Return a `QueryResponse`.
- Never return unsupported generated claims without evidence.

### `build_query_graph()`

Builds and returns the LangGraph workflow.

Required behavior:

- Register planner, retrieval, aggregation, summarization, and answer nodes.
- Route conditionally based on query type and available evidence.
- Preserve errors and limitations in state instead of hiding them.

### `HybridRetriever.search(request, plan)`

Runs selected retrieval strategies and returns ranked evidence.

Required behavior:

- Combine semantic, timeline, graph, and snapshot context.
- Deduplicate artifacts by stable artifact id.
- Preserve source references and raw source paths.

## Response Contract

Every response should include:

- `answer`
- `query_type`
- `confidence`
- `sources`
- `evidence`
- `timeline_context` when useful
- `graph_context` when useful
- `limitations`

The final answer can be concise, but the returned structure must keep enough
detail for later UI rendering.

## Acceptance Criteria

- A query can be answered from stored Step 3 artifacts without running
  ingestion or extraction.
- The planner selects different retrieval paths for different query types.
- Semantic retrieval returns typed artifacts with provenance.
- Timeline questions include ordered timeline context when available.
- Relationship questions include graph context when available.
- Answers cite source references from retrieved artifacts.
- Weak evidence produces a cautious answer with explicit limitations.
- No Streamlit or UI files are required for this step.

