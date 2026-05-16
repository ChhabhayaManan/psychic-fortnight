# Setup Guide

## Prerequisites

- Python 3.10 or higher
- Git
- API keys for LLM providers (watsonx.ai, OpenAI, Anthropic, or Groq)
- GitHub personal access token (for GitHub ingestion)

## Installation

### 1. Clone Repository

```bash
git clone <repository-url>
cd psychic-fortnight
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and add your credentials:

```env
# LLM Provider (choose one or multiple)
WATSONX_API_KEY=your_watsonx_key
WATSONX_PROJECT_ID=your_project_id
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GROQ_API_KEY=your_groq_key

# Default LLM Provider
DEFAULT_LLM_PROVIDER=watsonx  # or openai, anthropic, groq

# GitHub Integration
GITHUB_TOKEN=your_github_token

# MCP Servers (optional)
MCP_GITHUB_ENABLED=true
MCP_SLACK_ENABLED=false
MCP_JIRA_ENABLED=false

# Storage Paths
DATA_DIR=./data
RAW_DATA_DIR=./data/raw
EXTRACTED_DATA_DIR=./data/extracted
GRAPH_DATA_DIR=./data/graph
SNAPSHOTS_DIR=./data/snapshots
EMBEDDINGS_DIR=./data/embeddings

# Processing Configuration
CONFIDENCE_THRESHOLD=0.7
MAX_WORKERS=3
BATCH_SIZE=10

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/app.log
```

### 5. Initialize Data Directories

The application will automatically create required directories on first run, or you can create them manually:

```bash
mkdir -p data/raw/github data/raw/mcp data/raw/uploads
mkdir -p data/extracted/decisions data/extracted/incidents data/extracted/timeline data/extracted/ownership
mkdir -p data/graph data/snapshots data/embeddings
mkdir -p logs
```

## Running the Application

### Start Streamlit UI

```bash
streamlit run main.py
```

The application will be available at `http://localhost:8501`

### Start Background Workers

In a separate terminal:

```bash
python -m app.workers.ingestion_worker
```

## Configuration

### LLM Provider Setup

#### watsonx.ai (IBM)

1. Get API key from IBM Cloud
2. Create a project and get project ID
3. Add to `.env`:
   ```env
   WATSONX_API_KEY=your_key
   WATSONX_PROJECT_ID=your_project_id
   DEFAULT_LLM_PROVIDER=watsonx
   ```

#### OpenAI

1. Get API key from OpenAI
2. Add to `.env`:
   ```env
   OPENAI_API_KEY=your_key
   DEFAULT_LLM_PROVIDER=openai
   ```

#### Anthropic

1. Get API key from Anthropic
2. Add to `.env`:
   ```env
   ANTHROPIC_API_KEY=your_key
   DEFAULT_LLM_PROVIDER=anthropic
   ```

### GitHub Integration

1. Create a GitHub personal access token with `repo` scope
2. Add to `.env`:
   ```env
   GITHUB_TOKEN=your_token
   ```

### MCP Server Configuration

MCP (Model Context Protocol) servers enable integration with external tools.

#### GitHub MCP

```env
MCP_GITHUB_ENABLED=true
MCP_GITHUB_TOKEN=your_github_token
```

#### Slack MCP (optional)

```env
MCP_SLACK_ENABLED=true
MCP_SLACK_TOKEN=your_slack_token
MCP_SLACK_WORKSPACE=your_workspace
```

## Usage

### 1. Connect Sources

Navigate to "Connect Sources" page in the UI:
- Add GitHub repository URL
- Configure MCP servers
- Upload files

### 2. Monitor Processing

Check "Processing Dashboard" to see:
- Ingestion progress
- Extracted memories
- Worker status

### 3. Query Knowledge

Use "Query Interface" to ask questions:
- "Why did we migrate to Kafka?"
- "What caused the payment outage?"
- "Who owns the auth service?"

### 4. Explore Memories

Browse extracted knowledge:
- Timeline view
- Knowledge graph
- Decision explorer

## Troubleshooting

### Issue: Dependencies not installing

**Solution**: Ensure Python 3.10+ is installed
```bash
python --version
```

### Issue: API key errors

**Solution**: Verify `.env` file has correct keys and is in project root

### Issue: ChromaDB errors

**Solution**: Delete and reinitialize ChromaDB
```bash
rm -rf data/embeddings/chroma.db
```

### Issue: Workers not processing

**Solution**: Check logs
```bash
tail -f logs/app.log
```

## Development

### Code Formatting

```bash
black app/
ruff check app/
```

### Type Checking

```bash
mypy app/
```

## Project Structure

```
psychic-fortnight/
├── app/              # Application code
├── data/             # Data storage (gitignored)
├── docs/             # Documentation
├── .env              # Environment variables (gitignored)
├── main.py           # Entry point
└── requirements.txt  # Dependencies
```

## Next Steps

1. Connect your first data source (GitHub repository)
2. Wait for initial ingestion to complete
3. Ask your first question
4. Explore the knowledge graph

## Support

For issues and questions:
- Check documentation in `docs/`
- Review architecture in `docs/ARCHITECTURE.md`
- Check logs in `logs/app.log`