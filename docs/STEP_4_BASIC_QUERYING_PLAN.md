# Step 4: Basic Querying Plan

## Objective

Implement the backend query interface that receives user questions and returns
structured, source-grounded responses.

This is the stable API surface that later Streamlit pages will call. It should
work without any UI dependency.

## Query Flow

```text
QueryRequest
  -> validate query text and filters
  -> normalize source and artifact filters
  -> create QueryState
  -> run LangGraph query workflow
  -> return QueryResponse
```

## Query Request Schema

Plan a `QueryRequest` model with these fields:

- `query`: required natural-language question.
- `source_id`: optional source filter, such as `owner_repo`.
- `top_k`: optional result count, default `8`.
- `artifact_types`: optional list of artifact types to search.
- `contributors`: optional contributor filter.
- `services`: optional service or entity filter.
- `time_range`: optional start and end timestamp filter.
- `include_timeline`: optional override for timeline retrieval.
- `include_graph`: optional override for graph traversal.

Required behavior:

- Reject empty query text.
- Clamp `top_k` to a safe range, such as `1` to `20`.
- Treat missing filters as "search all available project memory."
- Preserve filters in orchestration state for retrieval and answer metadata.

## Query Response Schema

Plan a `QueryResponse` model with these fields:

- `answer`: final natural-language answer.
- `query_type`: planner classification.
- `confidence`: answer-level confidence from `0.0` to `1.0`.
- `sources`: source references used in the answer.
- `evidence`: ranked evidence artifacts.
- `timeline_context`: ordered timeline context when used.
- `graph_context`: graph paths, neighbors, and entities when used.
- `limitations`: missing evidence, low confidence, or partial coverage.
- `metadata`: execution metadata such as retrieval strategy and counts.

Required behavior:

- Always return `sources`, even when empty.
- Always return `limitations`, even when empty.
- Preserve artifact ids and artifact types in evidence entries.
- Preserve raw source references for every cited artifact.

## Evidence Object

Each evidence item should represent one extracted artifact or snapshot section.

Required fields:

- `artifact_id`
- `artifact_type`
- `title`
- `summary`
- `confidence`
- `relevance_score`
- `source_refs`
- `raw_data_paths`
- `metadata`

Evidence must remain typed. Do not convert retrieved artifacts into one large
unstructured summary before answer generation.

## Query Classification

The basic query layer should support these types:

- `decision`: why or what decision questions.
- `incident`: outage, bug, regression, root-cause questions.
- `timeline`: evolution, history, when, sequence questions.
- `architecture`: services, migrations, protocols, dependencies.
- `ownership`: who knows, who changed, who reviewed, who owns.
- `unresolved`: open concerns, risks, unanswered questions.
- `relationship`: how entities connect.
- `general`: broad questions needing mixed retrieval.

The classification is produced by the planner node, but the response contract
should expose it.

## Backend Entry Point

Plan this public function:

```python
answer_query(request: QueryRequest) -> QueryResponse
```

Required behavior:

- Build or reuse the query graph.
- Execute the graph with a fresh state.
- Return a `QueryResponse`.
- Surface recoverable failures as limitations.
- Raise clear errors only for invalid requests or missing required storage.

## Manual Verification Scenarios

- Empty query is rejected.
- Query with no filters searches all artifact types.
- Query with `source_id` searches only that source.
- Query with `artifact_types=["decisions"]` does not return incident-only
  artifacts.
- Unknown query returns a response with limitations instead of invented facts.

## Acceptance Criteria

- The backend has one clear query entrypoint.
- Query input and output are structured.
- Evidence, sources, and limitations are first-class response fields.
- The response shape is ready for a future Streamlit UI.

