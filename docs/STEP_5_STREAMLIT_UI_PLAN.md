# Step 5: Streamlit UI Implementation

## Objective

Implement the user interface using Streamlit to expose the ingestion, processing, querying, and visualization capabilities of the system. This step builds on top of the backend intelligence layer (Step 4), processing pipelines (Step 3), and data ingestion (Step 2) to provide an interactive, visual experience for the user.

## Scope

In scope:
- Multi-page Streamlit application setup.
- Configuration and Setup page for credentials and target repository.
- Processing Dashboard for monitoring active workers and pipeline status.
- Chat-based Query Interface for interacting with the engineering memory.
- Visual Timeline View for exploring engineering events over time.
- Interactive Knowledge Graph visualization for exploring relationships.
- Decision Explorer for browsing and filtering extracted decisions.

Not part of this step:
- Backend data extraction or ingestion logic.
- Model orchestration or querying pipelines (handled in Step 4).
- Production deployment or web hosting configuration (unless required for Streamlit specifically).

## Planned Pages

The application will be divided into the following 6 pages:

### Page 1: Setup and Configuration
**Purpose:** Collect necessary configuration, credentials, and target repository details.
**Features:**
- Inputs for repository details: Repository name and Owner name.
- Input for GitHub OAuth token or Personal Access Token (PAT).
- Inputs for required API keys (e.g., Watsonx/LLM API keys, ChromaDB connection details).
- Validation and save functionality for configuration (persisted to `.env` or configuration store).
- Status indicators for active connections.

### Page 2: Processing Dashboard
**Purpose:** Monitor the progress and health of the ingestion and extraction pipelines.
**Features:**
- **Ingestion Progress:** Visual indicators (progress bars, status text) showing the status of GitHub item ingestion (from Step 2).
- **Extracted Memories:** Metrics and counts of extracted artifacts (Decisions, Incidents, Timeline Events, etc. from Step 3).
- **Active Workers:** Status of extraction and indexing workers (running, idle, errors).
- **Indexing Status:** Stats from the ChromaDB vector index and NetworkX graph updates.

### Page 3: Query Interface
**Purpose:** The primary conversational interface to interact with the backend intelligence layer.
**Features:**
- Chat UI supporting multi-turn conversation.
- Input field for user queries.
- Display of source-grounded answers with citations and provenance links.
- Display of confidence scores and any query limitations returned by the Step 4 orchestrator.
- Expandable sections for detailed evidence, timeline context, or graph context if returned by the query planner.

### Page 4: Timeline View
**Purpose:** Visual exploration of the engineering timeline extracted from the repository.
**Features:**
- Visual timeline component (e.g., using Streamlit components or charts).
- Display of `TimelineEvent` artifacts over time.
- Filtering options (by event type, date range, related entities, tags).
- Clicking an event should show detailed summaries, related decisions, and source links.

### Page 5: Knowledge Graph
**Purpose:** Interactive visualization of relationships between artifacts, entities, and contributors.
**Features:**
- Interactive graph visualization rendering the NetworkX graph (`data/graph/knowledge_graph.json`).
- Node interactions (click to see details, expand relationships).
- Filtering nodes by type (Decision, Incident, Contributor, Service, etc.).
- Pan, zoom, and highlight capabilities.

### Page 6: Decision Explorer
**Purpose:** A dedicated view for browsing and filtering extracted engineering decisions.
**Features:**
- Tabular or card-based view of `Decision` artifacts.
- Search functionality across decision titles and summaries.
- Filtering by confidence score, related services, contributors, and tags.
- Detailed view on selection, showing reasoning, metadata, and raw source provenance.

## Integration Points

- The UI will invoke Python functions or API endpoints defined in the previous steps (e.g., `answer_query(request)` from Step 4, status endpoints from Step 3).
- The Setup page will directly influence the `app/config` or `.env` state, triggering re-initialization of required services.
- The Dashboard will poll or subscribe to worker states or read `data/snapshots/project_summary.json`.
- The Knowledge Graph will load `data/graph/knowledge_graph.json`.
- The Decision Explorer will load artifacts from `data/extracted/decisions/`.

## Planned Directory Structure

```text
app/ui/
+-- Home.py (Entrypoint)
+-- pages/
    +-- 1_Setup.py
    +-- 2_Processing_Dashboard.py
    +-- 3_Query_Interface.py
    +-- 4_Timeline_View.py
    +-- 5_Knowledge_Graph.py
    +-- 6_Decision_Explorer.py
+-- components/
    +-- chat.py
    +-- timeline.py
    +-- graph.py
+-- utils/
    +-- state.py
    +-- api.py
```

## Acceptance Criteria
- A Streamlit application can be started using `streamlit run`.
- All 6 defined pages are accessible via the sidebar navigation.
- The Setup page successfully saves configuration that the backend can use.
- The Dashboard accurately reflects data counts from the `data/extracted` directories and snapshots.
- The Query Interface can send requests to the Step 4 backend and display the structured responses.
- Timeline, Knowledge Graph, and Decision Explorer pages successfully read and display the artifacts generated in Step 3.
- Source provenance is visible wherever artifacts or answers are displayed.
