# Step 2: Automatic GitHub Ingestion and Raw Storage

## Objective

Implement GitHub ingestion as the first stage of the automatic source-processing
workflow.

When a GitHub source is connected, the system validates repository access,
discovers repository activity, creates ingestion work, fetches raw records,
stores those records with provenance, and hands stored raw item references to
the Step 3 processing pipeline.

Step 2 preserves original source material. It does not create derived memory
artifacts.

## Automatic Flow

```text
Connect GitHub source
  -> validate repository access
  -> persist source metadata
  -> discover all PRs and issues
  -> create ingestion queue items
  -> fetch raw PR and issue records
  -> store raw JSON under data/raw/github/{source_id}/
  -> persist ingestion state
  -> enqueue stored raw item references for Step 3 processing
```

This matches the autonomous flow: source connection starts discovery, discovery
creates work, ingestion stores raw source data, and the next processing stage
continues without the user selecting individual PRs or issues.

## Scope

In scope:

- GitHub API access through PyGithub.
- Repository validation by `owner/repo`.
- Discovery of all open and closed pull requests.
- Discovery of all open and closed issues, excluding PR-backed issues.
- Creation of ingestion queue items from discovered PRs and issues.
- Fetching complete raw PR records.
- Fetching complete raw issue records.
- Filesystem raw JSON storage.
- Source metadata storage.
- Ingestion state suitable for progress and resumption.
- Handoff records for Step 3.

Not part of this step:

- Derived-memory processing.
- User-facing source dashboards.
- Later knowledge-base stages.

## Current Repo State

These files are the Step 2 working surface:

- `app/ingestion/base.py`
- `app/ingestion/github/client.py`
- `app/ingestion/github/ingestion.py`
- `app/memory/raw_storage.py`
- `app/models/ingestion.py`
- `app/models/processing_state.py`
- `app/utils/rate_limiter.py`
- `examples/github_ingestion_example.py`

Any Step 2 implementation should improve these files in place and add only the
small workflow-state pieces needed to connect ingestion to the future automatic
pipeline.

## Architecture

```text
Source connection
    |
    v
GitHubIngestion
    - validate source
    - discover PR and issue numbers
    - create ingestion items
    |
    v
GitHubClient
    - load repository
    - list PRs
    - list issues
    - fetch raw PR details
    - fetch raw issue details
    |
    v
RawDataStorage
    - store source metadata
    - store PR JSON
    - store issue JSON
    - detect already stored items
    |
    v
Processing handoff
    - source_id
    - item_type
    - item_number
    - raw_data_path
```

## Implementation Checkpoints

### 1. GitHub Client

Use `app/ingestion/github/client.py` as the GitHub API boundary.

Required behavior:

- `get_repository(owner, repo)` loads the repository identified by `owner/repo`.
- `list_pull_requests(repo, state="all")` returns open and closed PRs.
- `list_issues(repo, state="all")` returns open and closed issues and filters
  out GitHub issue objects that represent PRs.
- `get_pr_details(pr)` returns raw PR data:
  - source type, repository, PR number, URL
  - title, state, created/updated/closed/merged timestamps
  - author, labels, milestone, assignees
  - full description
  - review comments
  - reviews
  - commits
  - changed-file count, additions, deletions, merge metadata
  - ingestion timestamp
- `get_issue_details(issue)` returns raw issue data:
  - source type, repository, issue number, URL
  - title, state, created/updated/closed timestamps
  - author, labels, milestone, assignees
  - full description
  - comments
  - ingestion timestamp
- GitHub calls pass through the existing `RateLimiter` boundary where
  practical.

### 2. Discovery and Queue Items

Use `app/ingestion/github/ingestion.py` and `app/models/ingestion.py`.

Required behavior:

- `GitHubIngestion.validate()` confirms the repository is accessible.
- `GitHubIngestion.get_source_id()` returns the source id in `owner_repo`
  format.
- `GitHubIngestion.discover()`:
  - loads the repository if needed
  - discovers all PR numbers
  - discovers all non-PR issue numbers
  - returns a `DiscoveryResult`
  - stores repository metadata through `RawDataStorage`
- `DiscoveryResult.to_items()` converts discovered numbers into `IngestionItem`
  objects with ids in the form `{source_id}_pr_{number}` or
  `{source_id}_issue_{number}`.
- Queue item metadata must contain enough information to fetch and store one
  raw record without re-running discovery.

### 3. Raw Storage

Use `app/memory/raw_storage.py` as the only raw storage layer for Step 2.

Required storage layout:

```text
data/raw/github/
+-- {source_id}/
    +-- metadata.json
    +-- prs/
    |   +-- 1.json
    |   +-- ...
    +-- issues/
        +-- 1.json
        +-- ...
```

Required behavior:

- `store_pr(source_id, pr_number, data)` writes
  `data/raw/github/{source_id}/prs/{pr_number}.json`.
- `store_issue(source_id, issue_number, data)` writes
  `data/raw/github/{source_id}/issues/{issue_number}.json`.
- `store_source_metadata(source_id, metadata)` writes
  `data/raw/github/{source_id}/metadata.json`.
- Stored PR and issue files include `_storage_metadata` with:
  - `stored_at`
  - `source_id`
  - `item_type`
  - `item_number`
- `get_pr()` and `get_issue()` load stored JSON if present.
- `exists(source_id, item_type, item_number)` returns whether raw data has
  already been stored.

Raw storage must preserve original source provenance. Do not replace source
content with summaries.

### 4. Ingestion State and Handoff

Step 2 must produce state that later automatic workflow components can consume.

Each stored raw record should be representable as:

```json
{
  "source_id": "owner_repo",
  "item_type": "pr",
  "item_number": 145,
  "raw_data_path": "data/raw/github/owner_repo/prs/145.json"
}
```

Required behavior:

- Store source-level discovery counts and timestamps.
- Track queued, stored, skipped, and failed ingestion items.
- Skip already stored raw files unless an explicit refresh mode is added later.
- Hand off stored raw item references to the Step 3 processing queue.
- Preserve enough state to resume ingestion without duplicating raw records.

## Public Interfaces

### `GitHubClient`

- `get_repository(owner, repo)`
- `list_pull_requests(repo, state="all")`
- `list_issues(repo, state="all")`
- `get_pr_details(pr)`
- `get_issue_details(issue)`

### `GitHubIngestion`

- `validate()`
- `discover()`
- `fetch(item_id)`
- `fetch_pr(pr_number)`
- `fetch_issue(issue_number)`
- `get_source_id()`

### `RawDataStorage`

- `store_pr(source_id, pr_number, data)`
- `store_issue(source_id, issue_number, data)`
- `get_pr(source_id, pr_number)`
- `get_issue(source_id, issue_number)`
- `exists(source_id, item_type, item_number)`
- `store_source_metadata(source_id, metadata)`
- `get_source_metadata(source_id)`

## Raw Data Contract

### Pull Request JSON

```json
{
  "source": {
    "type": "github",
    "repository": "owner/repo",
    "pr_number": 145,
    "url": "https://github.com/owner/repo/pull/145"
  },
  "metadata": {
    "title": "Add authentication service",
    "state": "closed",
    "created_at": "2024-01-10T10:00:00",
    "updated_at": "2024-01-15T15:30:00",
    "closed_at": "2024-01-15T15:30:00",
    "merged_at": "2024-01-15T15:30:00",
    "author": "alice",
    "labels": ["feature", "backend"],
    "milestone": "v2.0",
    "assignees": ["bob"]
  },
  "description": "Full PR description text...",
  "comments": [],
  "reviews": [],
  "commits": [],
  "files_changed": 15,
  "additions": 450,
  "deletions": 120,
  "merged": true,
  "mergeable": null,
  "ingested_at": "2026-05-16T10:00:00",
  "_storage_metadata": {
    "stored_at": "2026-05-16T10:00:05",
    "source_id": "owner_repo",
    "item_type": "pr",
    "item_number": 145
  }
}
```

### Issue JSON

```json
{
  "source": {
    "type": "github",
    "repository": "owner/repo",
    "issue_number": 89,
    "url": "https://github.com/owner/repo/issues/89"
  },
  "metadata": {
    "title": "Payment service outage",
    "state": "closed",
    "created_at": "2024-01-12T08:00:00",
    "updated_at": "2024-01-12T13:00:00",
    "closed_at": "2024-01-12T14:00:00",
    "author": "dave",
    "labels": ["bug", "critical"],
    "milestone": null,
    "assignees": ["alice", "bob"]
  },
  "description": "Full issue description...",
  "comments": [],
  "ingested_at": "2026-05-16T10:00:00",
  "_storage_metadata": {
    "stored_at": "2026-05-16T10:00:05",
    "source_id": "owner_repo",
    "item_type": "issue",
    "item_number": 89
  }
}
```

## Manual Verification

Use `examples/github_ingestion_example.py` until the automatic runner exists.

1. Configure `.env` with a valid `GITHUB_TOKEN`.
2. Run:

   ```bash
   python examples/github_ingestion_example.py
   ```

3. Enter a repository owner and name.
4. Confirm the script validates the repository connection.
5. Confirm PR and issue counts are discovered.
6. Fetch a small sample.
7. Inspect generated files under `data/raw/github/{source_id}/`.
8. Confirm stored raw item references can be created from the stored paths.

## Acceptance Criteria

- A valid GitHub token can connect to a repository.
- All open and closed PR numbers are discovered.
- All open and closed issue numbers are discovered, excluding PR-backed issues.
- Raw PR and issue JSON files preserve source, metadata, text, discussion, and
  storage metadata.
- Repository metadata is saved once per source.
- Existing stored items can be detected with `RawDataStorage.exists()`.
- Ingestion produces stored raw item references for Step 3.
- Ingestion state can represent queued, stored, skipped, and failed items.

## Configuration

Minimum configuration needed for Step 2:

```env
GITHUB_TOKEN=ghp_your_token_here
RAW_DATA_DIR=./data/raw
STATE_DIR=./data/state
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60
```

`.env.example` must never contain a real GitHub token.

## Summary

Step 2 creates the automatic raw source-of-truth layer:

```text
GitHub source
    -> discovery
    -> ingestion queue
    -> raw JSON storage
    -> ingestion state
    -> raw item handoff
```

The next step consumes the stored raw item references and turns them into
structured memory artifacts.
