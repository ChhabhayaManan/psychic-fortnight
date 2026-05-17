# Step 4: Timeline Retrieval and Summarization Plan

## Objective

Implement the timeline query layer that answers history and evolution questions
from extracted timeline artifacts.

Step 3 creates timeline events. Step 4 loads, ranks, orders, and summarizes
those events for query-time use.

## Data Source

Read timeline artifacts from:

```text
data/extracted/timeline/
```

Timeline retrieval can also use related artifacts from:

```text
data/extracted/decisions/
data/extracted/incidents/
data/extracted/architecture/
data/extracted/relationships/
```

The timeline layer must not fetch raw GitHub data or run raw extraction.

## Timeline Retrieval Module

Implement `app/retrieval/timeline.py`.

Required behavior:

- Load timeline events from JSON storage.
- Filter by source, service, contributor, entity, and time range.
- Score events by query relevance, confidence, and timestamp usefulness.
- Sort selected events into chronological order.
- Link timeline events to related decisions, incidents, architecture changes,
  and relationships when ids are present.
- Return timeline context with source references.

## Timeline Context

Each returned timeline item should include:

- `event_id`
- `event_type`
- `title`
- `summary`
- `timestamp`
- `related_entities`
- `related_artifacts`
- `confidence`
- `source_refs`

Timeline context should preserve enough metadata to render a future UI timeline
without changing the backend response shape.

## Supported Timeline Questions

The planner should prefer timeline retrieval for questions like:

- "How did auth architecture evolve?"
- "When did we move to gRPC?"
- "What happened before the outage?"
- "What changed after PR 42?"
- "How did payment-service migration unfold?"
- "What decisions led to this incident?"

## Timeline Summary Agent

Implement `app/orchestration/agents/timeline_summary_agent.py`.

Required behavior:

- Use ordered timeline context as input.
- Produce a concise chronological summary.
- Preserve uncertainty when timestamps are missing or partial.
- Cite event source references.
- Avoid inventing missing intermediate events.

Prompt content should live in:

```text
app/prompts/timeline_summarization.py
```

## Integration With Orchestration

Timeline retrieval should be called when:

- planner selects `timeline` as primary query type.
- planner selects `incident`, `architecture`, or `decision` and time ordering is
  useful.
- user sets `include_timeline`.

Timeline summary should feed the final answer agent as a separate context block,
not as a replacement for raw evidence.

## Acceptance Criteria

- Timeline questions return ordered events when available.
- Events include source provenance.
- Timeline summaries do not create unsupported history.
- Missing timeline data appears as a limitation.
- The timeline layer consumes Step 3 artifacts only.

