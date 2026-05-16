# Documentation Plan: Automatic Ingestion and Processing Steps

## Summary

Update the docs so the workflow matches `AUTONOMOUS_FLOW_DIAGRAM.md`: ingestion is not a standalone manual utility, it is the first stage of the automatic source-processing pipeline.

Because you chose **Broad Step 3**, create one new Step 3 plan that covers processing, extracted artifact storage, embedding generation, graph updates, and snapshots. Do not create Step 4 now. Query and answer-agent planning remains separate for later.

## Key Changes

- Modify `docs/STEP_2_GITHUB_INGESTION_PLAN.md`:
  - Reframe Step 2 as the automatic workflow entrypoint after a GitHub source is connected.
  - Include source validation, discovery, queue creation, raw fetch, raw storage, checkpoint/progress state, and handoff to the processing stage.
  - Keep Step 2 limited to GitHub ingestion and raw storage; no extraction, embeddings, graph, snapshots, or query logic.
  - Mention that ingestion outputs raw files plus queued processing items for Step 3.

- Create `docs/STEP_3_PROCESSING_AND_INDEXING_PLAN.md`:
  - Cover the post-ingestion pipeline: raw GitHub records -> extraction workers -> typed memory artifacts -> JSON storage -> embeddings -> vector index -> graph update -> snapshot refresh.
  - Include artifact types: decisions, incidents, timeline events, architecture changes, ownership memories, unresolved questions, and relationships.
  - Use existing models where present: `Decision`, `Incident`, `TimelineEvent`, `Relationship`, `SourceReference`.
  - Plan new model additions for missing artifact types: `ArchitectureChange`, `OwnershipMemory`, `UnresolvedQuestion`.

## Step 2 Content Direction

Step 2 should describe this automatic flow:

```text
Connect GitHub source
  -> validate repository access
  -> discover all PRs/issues
  -> create ingestion queue
  -> fetch raw PR/issue records
  -> store raw JSON under data/raw/github/{source_id}/
  -> persist source metadata and ingestion state
  -> enqueue stored raw item references for Step 3 processing
```

Important Step 2 interfaces:
- `GitHubClient`: API boundary.
- `GitHubIngestion`: discovery/fetch orchestration.
- `RawDataStorage`: raw JSON persistence.
- Future workflow handoff: each stored raw item should be representable as `{source_id, item_type, item_number, raw_data_path}`.

## Step 3 Content Direction

Step 3 should describe this automatic processing flow:

```text
Raw item reference
  -> load raw JSON
  -> run extraction agents
  -> validate confidence and provenance
  -> store accepted artifacts in data/extracted/
  -> generate embedding text per artifact
  -> write embeddings to ChromaDB
  -> update NetworkX graph relationships
  -> refresh project snapshot JSON
```

Storage layout to document:
- `data/extracted/decisions/`
- `data/extracted/incidents/`
- `data/extracted/timeline/`
- `data/extracted/architecture/`
- `data/extracted/ownership/`
- `data/extracted/unresolved/`
- `data/embeddings/chroma/`
- `data/graph/knowledge_graph.json`
- `data/snapshots/project_summary.json`

Step 3 should explicitly exclude query planning and answer generation.

## Verification Plan

After editing docs:
- Scan Step 2 to confirm it includes automatic queue/handoff language but no extraction, embeddings, graph, snapshots, or query-agent scope.
- Scan Step 3 to confirm it includes extraction, artifact storage, embeddings, graph, and snapshots but no query/answer-agent implementation.
- Confirm both docs use ASCII-only text and no placeholder tokens like `TBD` or `TODO`.
- No code changes and no test files.

## Assumptions

- MCP remains out of scope for these docs.
- Query and answer-agent planning will be a later document.
- Step 3 is intentionally broad because you selected that split.
- The docs can reference future files/classes as planned implementation targets, but this task only changes documentation.
