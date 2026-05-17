# Step 3: Processing, Artifact Storage, and Indexing

## Objective

Implement the automatic processing stage that consumes stored raw GitHub item
references from Step 2 and turns them into structured, indexed engineering
memory.

Step 3 owns extraction, artifact storage, embedding generation, vector indexing,
relationship graph updates, and project snapshot refreshes. The future
retrieval and response workflow will be planned separately.

## Automatic Flow

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

This stage is automatic: once Step 2 stores raw records and emits raw item
references, Step 3 workers process those references without the user selecting
individual PRs or issues.

## Scope

In scope:

- Loading raw GitHub PR and issue JSON from `data/raw/github/{source_id}/`.
- Extraction workers for typed memory artifacts.
- JSON storage for extracted artifacts.
- Confidence filtering.
- Required source provenance on every artifact.
- Embedding text generation for stored artifacts.
- ChromaDB vector index writes.
- NetworkX graph updates for relationships between memories and entities.
- Project snapshot refresh after accepted artifacts are stored.

Not part of this step:

- GitHub API ingestion.
- Manual source selection workflows.
- Final response generation.
- User-facing exploration pages.

## Current Repo State

Existing models to use:

- `app/models/decision.py` provides `Decision`.
- `app/models/incident.py` provides `Incident`.
- `app/models/timeline.py` provides `TimelineEvent`.
- `app/models/relationship.py` provides `Relationship`.
- `app/models/source.py` provides `SourceReference`.

Planned model additions:

- `ArchitectureChange`
- `OwnershipMemory`
- `UnresolvedQuestion`

Existing placeholder packages to fill during implementation:

- `app/extraction/decisions/`
- `app/extraction/incidents/`
- `app/extraction/timeline/`
- `app/extraction/architecture/`
- `app/extraction/ownership/`
- `app/extraction/unresolved/`
- `app/workers/extraction_worker.py`
- `app/workers/indexing_worker.py`
- `app/memory/json_store.py`
- `app/memory/vector_store.py`
- `app/memory/graph_store.py`
- `app/memory/snapshots.py`

## Artifact Types

### Decisions

Use existing `Decision`.

Required extraction output:

- title
- summary
- reasoning
- confidence
- related services
- contributors
- tags
- one or more `SourceReference` values

Storage path:

```text
data/extracted/decisions/{decision_id}.json
```

### Incidents

Use existing `Incident`.

Required extraction output:

- title
- summary
- root cause when present
- resolution when present
- severity
- affected services
- impact description when present
- contributors
- tags
- one or more `SourceReference` values

Storage path:

```text
data/extracted/incidents/{incident_id}.json
```

### Timeline Events

Use existing `TimelineEvent`.

Required extraction output:

- event type
- title
- summary
- timestamp
- related entities
- related decisions or incidents when known
- contributors
- tags
- one or more `SourceReference` values

Storage path:

```text
data/extracted/timeline/{event_id}.json
```

### Architecture Changes

Add `ArchitectureChange`.

Required fields:

- id
- title
- summary
- change type
- affected services
- before state when known
- after state when known
- confidence
- contributors
- tags
- source references
- timestamp
- metadata

Storage path:

```text
data/extracted/architecture/{architecture_change_id}.json
```

### Ownership Memories

Add `OwnershipMemory`.

Required fields:

- id
- entity name
- entity type
- owners
- evidence summary
- confidence
- source references
- timestamp
- metadata

Storage path:

```text
data/extracted/ownership/{ownership_id}.json
```

### Unresolved Questions

Add `UnresolvedQuestion`.

Required fields:

- id
- title
- question
- context
- status
- related services
- contributors
- confidence
- source references
- timestamp
- metadata

Storage path:

```text
data/extracted/unresolved/{question_id}.json
```

### Relationships

Use existing `Relationship`.

Required extraction output:

- source entity id
- target entity id
- relation type
- confidence
- description
- metadata

Storage path:

```text
data/extracted/relationships/{relationship_id}.json
```

## Processing Pipeline

### 1. Raw Item Loading

Input from Step 2:

```json
{
  "source_id": "owner_repo",
  "item_type": "pr",
  "item_number": 145,
  "raw_data_path": "data/raw/github/owner_repo/prs/145.json"
}
```

Required behavior:

- Load the raw JSON from `raw_data_path`.
- Reject missing or malformed raw files.
- Build `SourceReference` values from the raw source block, contributor fields,
  timestamps, URL, and raw path.
- Preserve `raw_data_path` in every source reference.

### 2. Extraction Agents

Each extractor has one responsibility and returns structured outputs only.

Planned extractors:

- decision extractor
- incident extractor
- timeline extractor
- architecture extractor
- ownership extractor
- unresolved-question extractor
- relationship extractor

Extractor rules:

- Do not emit generic summaries as final storage artifacts.
- Emit typed artifacts that match the model contracts.
- Attach source references to every artifact.
- Include confidence scores.
- Return no artifact when evidence is weak.

### 3. Confidence and Provenance Validation

Required behavior:

- Reject any artifact without at least one source reference.
- Reject any artifact below its configured confidence threshold.
- Use settings from `app/config/processing_config.py` where available:
  - decisions: `min_decision_confidence`
  - incidents: `min_incident_confidence`
  - relationships: `min_relationship_confidence`
- Use `0.7` as the default threshold for new artifact types until a dedicated
  setting exists.
- Record rejected artifacts only in logs or processing state, not in extracted
  artifact storage.

### 4. Artifact JSON Storage

Implement `app/memory/json_store.py` as the storage boundary for extracted
artifacts.

Required behavior:

- Store accepted artifacts under the correct `data/extracted/` subdirectory.
- Save one JSON file per artifact id.
- Preserve artifact type, artifact id, source references, confidence, and
  timestamps.
- Support loading artifacts by type and id.
- Support listing artifacts by type for indexing and snapshot refresh.

Storage layout:

```text
data/extracted/
+-- decisions/
+-- incidents/
+-- timeline/
+-- architecture/
+-- ownership/
+-- unresolved/
+-- relationships/
```

### 5. Embedding Generation and Vector Index

Implement `app/memory/vector_store.py` as the ChromaDB boundary.

Required behavior:

- Generate embedding text from artifact fields.
- Use existing `to_embedding_text()` methods where present.
- Add equivalent embedding text methods for new artifact models.
- Store vectors in ChromaDB under `data/embeddings/chroma/`.
- Store metadata with each vector:
  - artifact id
  - artifact type
  - title or display name
  - confidence
  - source id
  - primary source URL
  - raw data path
- Upsert by stable artifact id so reprocessing does not create duplicate
  vectors.

### 6. Relationship Graph Update

Implement `app/memory/graph_store.py` as the NetworkX graph boundary.

Required behavior:

- Store graph data at `data/graph/knowledge_graph.json`.
- Add nodes for artifacts, services, contributors, and repositories.
- Add edges from accepted `Relationship` artifacts.
- Add provenance edges from artifacts to raw sources.
- Update existing nodes instead of duplicating them.
- Persist the graph after each processing batch.

### 7. Snapshot Refresh

Implement `app/memory/snapshots.py` as the snapshot boundary.

Required behavior:

- Write `data/snapshots/project_summary.json`.
- Include counts by artifact type.
- Include latest decisions, active or recent incidents, timeline highlights,
  ownership map, unresolved questions, and graph summary statistics.
- Refresh after accepted artifacts are stored and indexed.

## Worker Responsibilities

### Extraction Worker

Use `app/workers/extraction_worker.py`.

Responsibilities:

- Consume raw item references from Step 2.
- Load raw JSON.
- Run extraction agents.
- Validate confidence and provenance.
- Store accepted artifacts through `JsonStore`.
- Emit artifact references for indexing.
- Continue processing other items when one item fails.

### Indexing Worker

Use `app/workers/indexing_worker.py`.

Responsibilities:

- Consume accepted artifact references.
- Load stored artifact JSON.
- Generate embedding text.
- Upsert vectors into ChromaDB.
- Update graph nodes and edges.
- Trigger snapshot refresh after each batch.

## Public Interfaces

### `JsonStore`

- `store_artifact(artifact_type, artifact)`
- `get_artifact(artifact_type, artifact_id)`
- `list_artifacts(artifact_type)`
- `artifact_exists(artifact_type, artifact_id)`

### `VectorStore`

- `upsert_artifact(artifact_type, artifact)`
- `delete_artifact(artifact_type, artifact_id)`
- `get_collection_stats()`

### `GraphStore`

- `upsert_artifact_node(artifact_type, artifact)`
- `upsert_entity_node(entity_type, entity_id, metadata)`
- `upsert_relationship(relationship)`
- `save()`
- `load()`

### `SnapshotStore`

- `refresh_project_summary()`
- `load_project_summary()`

## Acceptance Criteria

- Raw item references from Step 2 can be processed automatically.
- Accepted artifacts are typed, confidence-scored, and source-backed.
- Every stored artifact includes at least one source reference.
- Extracted artifacts are stored under `data/extracted/`.
- Embeddings are written to ChromaDB under `data/embeddings/chroma/`.
- Graph data is persisted to `data/graph/knowledge_graph.json`.
- Project snapshot data is persisted to `data/snapshots/project_summary.json`.
- Reprocessing the same raw item does not duplicate artifacts, vectors, or graph
  nodes.
- Failed raw items do not stop the processing pipeline.

## Configuration

Minimum configuration needed for Step 3:

```env
EXTRACTED_DATA_DIR=./data/extracted
GRAPH_DATA_DIR=./data/graph
SNAPSHOTS_DIR=./data/snapshots
EMBEDDINGS_DIR=./data/embeddings
CHROMA_PERSIST_DIRECTORY=./data/embeddings/chroma
MIN_DECISION_CONFIDENCE=0.7
MIN_INCIDENT_CONFIDENCE=0.6
MIN_RELATIONSHIP_CONFIDENCE=0.5
```

## Summary

Step 3 creates the structured memory layer:

```text
Stored raw item reference
    -> extraction workers
    -> typed artifacts
    -> extracted JSON storage
    -> vector index
    -> graph update
    -> project snapshot
```

The future response workflow will consume these stored and indexed artifacts.
