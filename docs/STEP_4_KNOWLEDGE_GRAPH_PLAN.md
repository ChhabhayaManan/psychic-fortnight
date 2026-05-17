# Step 4: Knowledge Graph Retrieval Plan

## Objective

Implement graph retrieval for relationship-heavy engineering-memory questions.

Step 3 builds and persists the graph. Step 4 loads the graph, finds relevant
entities and paths, and summarizes graph context for answer generation.

## Data Source

Read graph data from:

```text
data/graph/knowledge_graph.json
```

Graph retrieval should resolve graph node ids back to extracted artifact JSON
when the answer needs source references.

## Graph Retrieval Module

Implement `app/retrieval/graph_search.py`.

Required behavior:

- Load the persisted NetworkX graph through the graph storage boundary.
- Search nodes by entity name, service name, contributor, artifact title, and
  artifact id.
- Traverse relationships within a safe depth, default `2`.
- Return relevant paths, neighboring nodes, relationship descriptions, and
  linked artifacts.
- Rank graph results by query relevance, relationship confidence, path length,
  and source-backed artifact availability.

## Graph Context

Each graph result should include:

- `start_node`
- `end_node`
- `path`
- `relationships`
- `related_artifacts`
- `confidence`
- `source_refs`
- `metadata`

Graph context must make the difference clear between:

- graph relationship evidence.
- artifact evidence attached to graph nodes.
- inferred traversal relevance.

## Supported Graph Questions

The planner should prefer graph retrieval for questions like:

- "How is payment-service related to Kafka?"
- "Which decisions affected auth-service?"
- "Who understands checkout?"
- "What incidents are connected to Redis removal?"
- "Which services were touched by the gRPC migration?"
- "What unresolved questions relate to billing?"

## Graph Summary Agent

Implement `app/orchestration/agents/graph_summary_agent.py`.

Required behavior:

- Summarize graph paths and related artifacts.
- Explain relationships without overstating weak edges.
- Include relationship confidence when useful.
- Preserve source references from linked artifacts.
- Flag graph-only relationships that lack strong artifact evidence.

Prompt content should live in:

```text
app/prompts/graph_summarization.py
```

## Integration With Orchestration

Graph retrieval should be called when:

- planner selects `relationship` as primary query type.
- planner selects `ownership`, `architecture`, `incident`, or `decision` and
  related entities are useful.
- user sets `include_graph`.

Graph summary should feed final answer generation as a separate context block.

## Acceptance Criteria

- Relationship questions use graph traversal before final answering.
- Graph results include related artifacts and provenance when available.
- Weak or indirect graph paths are marked as lower confidence.
- Missing graph data appears as a limitation.
- The graph layer does not create new Step 3 relationships during query time.

