# System Workflows

## Overview

This document describes the actual data flow through the Agentic Engineering Memory System as it is implemented today. It covers the three-stage automated pipeline (Ingest → Extract → Index), query orchestration, error handling, and key design principles.

> **LLM Usage Summary**
> | Stage | Uses LLM? | Notes |
> |---|---|---|
> | Stage 1 — Ingestion | ❌ No | Pure GitHub API, PyGithub, async I/O |
> | Stage 2 — Extraction | ✅ Yes | Each extractor calls the configured LLM (Gemini / Groq / Watsonx) |
> | Stage 3 — Indexing | ❌ No | ChromaDB's built-in embedding model; no LLM API key needed |
> | Query Interface | ✅ Yes | LangGraph orchestration uses the configured LLM |

---

## 1. Automated Pipeline (One-Click)

The Processing Dashboard triggers all three stages sequentially in a background thread. The user presses a single button and the pipeline proceeds autonomously.

```mermaid
graph TD
    A["🚀 User clicks Start Full Pipeline"] --> B["Stage 1 — Ingestion"]
    B --> C["Stage 2 — Extraction"]
    C --> D["Stage 3 — Indexing"]
    D --> E["✅ Done — Data available for queries"]

    B -.->|"pipeline_stage = ingesting"| UI["Dashboard auto-refreshes every 3s"]
    C -.->|"pipeline_stage = extracting"| UI
    D -.->|"pipeline_stage = indexing"| UI
    E -.->|"pipeline_stage = done"| UI
```

---

## 2. Stage 1 — GitHub Ingestion Workflow

**Entry point:** `app/ingestion/github/workflow.py` → `GitHubIngestionWorkflow.run()`

```mermaid
graph TD
    A["GitHubIngestionWorkflow.run()"] --> A0["Save initial IngestionSourceState to disk\n(so UI shows 'In Progress' immediately)"]
    A0 --> B["Validate GitHub token & repo access\n(GitHubIngestion.validate)"]
    B --> C{"Access valid?"}
    C -->|No| FAIL["Raise ValueError — pipeline aborts"]
    C -->|Yes| D["Discover all PRs — list_pull_requests(limit=50)\nDiscover all Issues — list_issues(limit=50)"]
    D --> E["_initialize_state()\nLoad existing IngestionSourceState or create new one\nUpdate pr_count, issue_count, total_count"]
    E --> F["_queue_items()\nFor each PR/Issue → create IngestionItemState (QUEUED)\nSkip items already STORED if skip_existing=True"]
    F --> G["_process_items()\nWorker pool — max_workers=3 concurrent coroutines"]
    G --> H{"Item already in RawDataStorage?"}
    H -->|Yes — skip_existing| I["Mark SKIPPED\nEnqueue for extraction anyway"]
    H -->|No| J["Fetch full PR/Issue data via GitHub API\nget_pr_details() or get_issue_details()"]
    J --> K["RawDataStorage.store_pr() or store_issue()\nSave raw JSON to data/raw/github/<source_id>/prs/<n>.json"]
    K --> L["Mark STORED\nEnqueue for extraction via ProcessingQueue"]
    L --> M["IngestionStateManager.save_state() — persist progress"]
    I --> M
    M --> N{"More items?"}
    N -->|Yes| G
    N -->|No| O["Final state save\nIngestion complete"]
```

**Data written:**
- `data/raw/github/<owner>_<repo>/prs/<number>.json`
- `data/raw/github/<owner>_<repo>/issues/<number>.json`
- `data/state/<source_id>.json` — ingestion progress state
- `data/state/processing_queue.json` — handoff records for Stage 2

**Rate limiting:** Token bucket limiter — 100 requests / 60 seconds. All GitHub API calls go through `RateLimiter.acquire()`.

---

## 3. Stage 2 — LLM Extraction Workflow

**Entry point:** `app/workers/extraction_worker.py` → `ExtractionWorker.process_all()`

Each item from the processing queue is passed through **all 6 extractors in parallel**. Each extractor independently decides whether the PR/Issue contains its artifact type.

```mermaid
graph TD
    Q["ProcessingQueue — items from Stage 1"] --> W["ExtractionWorker.process_all()"]
    W --> BATCH["Fetch batch of 10 items"]
    BATCH --> SEM["asyncio.Semaphore(max_workers=3)"]
    SEM --> LOAD["Load raw JSON from data/raw/..."]
    LOAD --> PAR["Run all 6 extractors concurrently on the same raw data"]

    PAR --> DEC["DecisionExtractor\nKeyword pre-filter → no LLM call if no decision keywords\nLLM scores confidence, extracts title/summary/reasoning/tags"]
    PAR --> INC["IncidentExtractor\nKeyword pre-filter (bug, outage, hotfix, p0…)\nLLM extracts severity, root_cause, resolution, affected_services"]
    PAR --> ARC["ArchitectureExtractor\nKeyword pre-filter (migrate, refactor, new service…)\nLLM extracts change_type, before/after state"]
    PAR --> TIM["TimelineExtractor\nOnly processes closed/merged items\nLLM classifies event_type (feature, bugfix, deployment…)"]
    PAR --> OWN["OwnershipExtractor\nLLM infers owners from author + reviewers + assignees"]
    PAR --> UNR["UnresolvedExtractor\nKeyword pre-filter (?, TBD, TODO, open question…)\nLLM finds unanswered questions in comment threads"]

    DEC --> CF["Confidence Filter\nmin_confidence=0.6 (all extractors)"]
    INC --> CF
    ARC --> CF
    TIM --> CF
    OWN --> CF
    UNR --> CF

    CF -->|"Meets threshold"| STORE["JsonStore.store_artifact()\ndata/extracted/<type>/<id>.json"]
    CF -->|"Below threshold"| DISC["Discard"]

    STORE --> DONE["record_success() → remove from queue"]
    DISC --> DONE
```

**LLM invocation pattern used by all extractors:**
1. Quick keyword pre-filter (no LLM cost if PR is clearly irrelevant)
2. Build a structured prompt with title, description, labels, comments
3. `await llm.ainvoke(prompt)` → parse JSON response
4. Validate confidence ≥ threshold → create typed model object

**Terminal output during extraction:**
```
[EXTRACT] 🔍 IncidentExtractor → LLM analyzing: Fix critical auth timeout in prod
[EXTRACT] ✅ Incident found: Fix critical auth timeout in prod
[EXTRACT] 📅 TimelineExtractor → LLM analyzing: Add dark mode support
[EXTRACT] ✅ Timeline event: [feature] Add dark mode support
```

**Data written:**
- `data/extracted/decisions/<id>.json`
- `data/extracted/incidents/<id>.json`
- `data/extracted/timeline/<id>.json`
- `data/extracted/architecture/<id>.json`
- `data/extracted/ownership/<id>.json`
- `data/extracted/unresolved/<id>.json`

---

## 4. Stage 3 — Indexing Workflow

**Entry point:** `app/workers/indexing_worker.py` → `IndexingWorker.index_all_artifacts()`

No LLM is used here. ChromaDB uses its own local embedding model (all-MiniLM-L6-v2).

```mermaid
graph TD
    JS["JsonStore — all extracted artifacts"] --> IW["IndexingWorker.index_all_artifacts()"]
    IW --> TYPES["Iterate 7 artifact types:\ndecisions, incidents, timeline, architecture,\nownership, unresolved, relationships"]
    TYPES --> LOAD["Load each artifact from JSON"]

    LOAD --> VS{"VectorStore\nconfigured?"}
    VS -->|Yes| VU["VectorStore.upsert_artifact()\nChromaDB — stores text + metadata\nEmbedding generated locally (no LLM API)"]
    VS -->|No| SKIP_V["Skip vector indexing"]

    LOAD --> GS{"GraphStore\nconfigured?"}
    GS -->|"artifact_type = relationships"| GR["GraphStore.upsert_relationship()"]
    GS -->|"all other types"| GN["GraphStore.upsert_artifact_node()"]
    GS -->|Not configured| SKIP_G["Skip graph indexing"]

    GN --> SAVE["GraphStore.save() — persist knowledge_graph.json"]
    GR --> SAVE
```

**Data written:**
- `data/embeddings/chroma/` — ChromaDB persistent files
- `data/graph/knowledge_graph.json` — NetworkX graph as JSON

---

## 5. Query Workflow (LangGraph Orchestration)

**Entry point:** `app/orchestration/graph.py`

```mermaid
graph TD
    UQ["User Query — Query Interface page"] --> PL["Planner Agent\nDetermines query type and retrieval strategy"]
    PL --> QT{"Query type?"}

    QT -->|"decision / general"| SEM["Semantic Retrieval\nChromaDB similarity search"]
    QT -->|"incident / timeline"| TL["Timeline Search\nDate-filtered event lookup"]
    QT -->|"ownership"| GR["Graph Traversal\nNetworkX relationship walk"]

    SEM --> AGG["Evidence Aggregation\nMerge results from multiple sources"]
    TL --> AGG
    GR --> AGG

    AGG --> RR["Reranking by relevance score"]
    RR --> ANS["Answer Generation Agent\nLLM synthesizes final answer with citations"]
    ANS --> RESP["Structured response:\nanswer + sources + confidence"]
```

### Hybrid Retrieval (within a single query)

```mermaid
graph LR
    Q["Query"] --> S["Semantic Search\nChromaDB top-K"]
    Q --> G["Graph Traversal\nRelated nodes"]
    Q --> T["Timeline Search\nDate-ordered events"]

    S --> M["Merge & Deduplicate"]
    G --> M
    T --> M
    M --> F["Final ranked result set"]
```

---

## 6. Background Worker Architecture

All pipeline stages run in a **daemon thread** spawned by the Streamlit UI. The UI polls `st.session_state.pipeline_stage` every 3 seconds and updates the progress display.

```mermaid
graph TD
    UI["Streamlit UI\n(main thread)"] -->|"threading.Thread(daemon=True)"| BG["Background Pipeline Thread"]

    BG --> S1["Stage 1 — GitHubIngestionWorkflow.run()\nasyncio event loop"]
    S1 -->|"Saves state to disk after each item"| DISK["data/state/*.json"]

    S1 --> S2["Stage 2 — ExtractionWorker.process_all()\nsame event loop, batches of 10"]
    S2 -->|"Saves artifacts to disk"| DISK

    S2 --> S3["Stage 3 — IndexingWorker.index_all_artifacts()"]
    S3 -->|"Updates ChromaDB + graph"| DISK

    BG -->|"Updates pipeline_stage in session_state"| UI
    UI -->|"Auto-rerun every 3s while running"| UI
```

**State machine:**

```
idle → ingesting → extracting → indexing → done
                                         ↘ error (any stage failure)
```

---

## 7. Error Handling

### Per-item failure (Extraction)

```mermaid
graph TD
    FAIL["Item extraction fails"] --> REC["processing_queue.record_failure(item, error)"]
    REC --> CHK{"Attempt < max_attempts (3)?"}
    CHK -->|Yes| RETRY["Item stays in queue — retried next batch"]
    CHK -->|No| DL["Moved to dead_letter queue\nLogged, not retried"]
```

### Pipeline-level failure

```mermaid
graph TD
    ERR["Unhandled exception in background thread"] --> LOG["print [PIPELINE] ❌ error message"]
    LOG --> PS["pipeline_stage = error\npipeline_error = traceback"]
    PS --> UI2["UI shows red error banner with message\nReset State button appears"]
    UI2 --> RST["User can Reset and retry from idle"]
```

### LLM unavailability

If LLM credentials are not configured:
- Each extractor calls `llm_config.validate_llm_ready()` before invoking LLM
- If not ready → logs a warning, returns `[]` (no artifacts extracted)
- Pipeline continues — ingestion and indexing still complete successfully
- **Extraction artifacts will simply be empty until LLM is configured**

---

## 8. LLM Provider Configuration

The system supports three providers, selected in the **Setup page** and stored in `.env`:

| Provider | Env var | Model default |
|---|---|---|
| Gemini | `GEMINI_API_KEY` | `gemini-1.5-flash` |
| Groq | `GROQ_API_KEY` | `llama3-8b-8192` |
| Watsonx | `WATSONX_API_KEY` + `WATSONX_PROJECT_ID` | configurable |

Provider is lazy-imported — only the selected provider's SDK is loaded when the LLM is first called.

---

## 9. Data Stores & Their Roles

| Store | Path | Technology | Used in stage |
|---|---|---|---|
| Raw storage | `data/raw/` | Plain JSON files | Written in Stage 1, read in Stage 2 |
| Extracted artifacts | `data/extracted/` | Plain JSON files | Written in Stage 2, read in Stage 3 |
| Ingestion state | `data/state/<source_id>.json` | JSON via `IngestionStateManager` | Written throughout Stage 1 |
| Processing queue | `data/state/processing_queue.json` | JSON via `ProcessingQueue` | Written in Stage 1, consumed in Stage 2 |
| Vector store | `data/embeddings/chroma/` | ChromaDB (persistent) | Written in Stage 3, queried at runtime |
| Knowledge graph | `data/graph/knowledge_graph.json` | NetworkX → JSON | Written in Stage 3, queried at runtime |

---

## 10. Ingestion Item Lifecycle

```mermaid
stateDiagram-v2
    [*] --> QUEUED : Discovered in GitHub
    QUEUED --> STORED : Raw data fetched & saved
    QUEUED --> SKIPPED : Already exists (skip_existing=True)
    QUEUED --> FAILED : API error or exception
    STORED --> [*] : Enqueued for extraction
    SKIPPED --> [*] : Enqueued for extraction (re-extraction)
    FAILED --> [*] : Logged, pipeline continues
```

---

## 11. Key Design Principles

### 1. Async-First
- All I/O-heavy operations use `asyncio` (GitHub API, LLM calls, file reads)
- Worker pool controlled via `asyncio.Semaphore(max_workers=3)`
- UI thread never blocks

### 2. Fault Tolerant
- Initial state written to disk before any GitHub API calls so the UI always knows ingestion has started
- Per-item try/except — one bad PR never kills the batch
- LLM extractor failure falls through to the next extractor gracefully

### 3. Resumable
- `IngestionSourceState` is saved after every item processed
- Re-running the pipeline with `skip_existing=True` skips already-fetched items
- Queue uses a dead-letter mechanism — failed items don't block the queue

### 4. Keyword Pre-filtering (Cost Control)
- All LLM extractors run a lightweight keyword check before calling the LLM
- Only PRs with relevant signals (e.g., "incident", "migrate", "?", etc.) trigger an API call
- Trivial PRs (typo fixes, dependabot bumps) are filtered without any LLM cost

### 5. Observable
- All pipeline stages print `[PIPELINE]` and `[EXTRACT]` prefixed log lines to stdout
- Streamlit dashboard auto-refreshes every 3s and shows stage progress
- Ingestion metrics (stored/skipped/failed counts) visible in real time

### 6. Idempotent
- Re-running with the same repo is safe — items already stored are skipped
- `JsonStore.store_artifact()` overwrites by artifact ID — no duplicates
- ChromaDB uses `upsert` — re-indexing the same artifact is safe