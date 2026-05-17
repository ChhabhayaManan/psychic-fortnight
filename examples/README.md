# Examples

This directory contains example scripts demonstrating how to use the Agentic Engineering Memory System.

## GitHub Ingestion Example

**File:** `github_ingestion_example.py`

Demonstrates how to:
- Connect to GitHub using OAuth token
- Discover all PRs and Issues in a repository
- Fetch complete data (metadata, comments, reviews)
- Store as RAW JSON files

### Prerequisites

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure GitHub token:**
   
   Add your GitHub Personal Access Token to `.env`:
   ```env
   GITHUB_TOKEN=ghp_your_token_here
   ```

   To create a token:
   - Go to GitHub Settings → Developer settings → Personal access tokens
   - Generate new token (classic)
   - Select scopes: `repo` (for private repos) or `public_repo` (for public only)

### Usage

```bash
python examples/github_ingestion_example.py
```

The script will:
1. Prompt for repository owner and name
2. Validate connection
3. Discover all PRs and Issues
4. Fetch first 5 items as example
5. Store RAW data in `data/raw/github/{owner}_{repo}/`

### Example Output

```
GitHub Repository Ingestion Example
====================================

Enter repository owner (e.g., 'facebook'): facebook
Enter repository name (e.g., 'react'): react

🔍 Validating connection to facebook/react...
✅ Connected to facebook/react

🔍 Discovering PRs and Issues...

📊 Discovery Results:
  - PRs found: 1234
  - Issues found: 567
  - Total items: 1801

⚠️  This will fetch and store 1801 items
Do you want to proceed? (yes/no): yes

📥 Fetching first 5 items as example...

[1/5] Fetching pr #12345...
  ✅ Stored at: data/raw/github/facebook_react/prs/12345.json

[2/5] Fetching issue #6789...
  ✅ Stored at: data/raw/github/facebook_react/issues/6789.json

...

✅ Example ingestion complete!

RAW data stored in: data/raw/github/facebook_react/
```

### Data Structure

Stored JSON files contain:
- **Source metadata** (repository, URL, type)
- **Item metadata** (title, state, dates, author, labels)
- **Description** (full text)
- **Comments** (all comments with authors and timestamps)
- **Reviews** (for PRs - review state and comments)
- **Commits** (for PRs - commit messages and authors)

### Next Steps

For production use:
1. Implement full worker pool for parallel processing
2. Add checkpoint management for resumable ingestion
3. Integrate with Discovery Agent for autonomous operation
4. Add progress tracking and monitoring

See `docs/STEP_2_GITHUB_INGESTION_PLAN.md` for complete implementation plan.