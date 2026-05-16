# Quick Start Guide

Get the Agentic Engineering Memory System up and running in minutes.

## Prerequisites

- Python 3.11 or higher
- Git
- IBM watsonx.ai account (for LLM access)
- GitHub Personal Access Token (optional, for GitHub integration)

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd psychic-fortnight
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy the example environment file:

```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

Edit `.env` and add your credentials:

```env
# Required: IBM watsonx.ai credentials
WATSONX_API_KEY=your_watsonx_api_key_here
WATSONX_PROJECT_ID=your_project_id_here

# Optional: GitHub token for private repositories
GITHUB_TOKEN=your_github_token_here

# Optional: Adjust processing settings
MAX_WORKERS=5
BATCH_SIZE=10
```

### 5. Verify Installation

```bash
python -c "from app.config import get_settings; print('Configuration loaded successfully')"
```

## Running the Application

### Start the UI

```bash
python main.py
```

The Streamlit UI will open automatically at `http://localhost:8501`

### Alternative: Direct Streamlit Launch

```bash
streamlit run app/ui/app.py
```

## First Steps

### 1. Connect a Knowledge Source

1. Navigate to the **Sources** page in the UI
2. Select "GitHub Repository"
3. Enter the repository owner and name
4. Click "Connect Repository"

The system will automatically:
- Discover all PRs and Issues
- Queue them for processing
- Extract decisions, incidents, and timelines
- Build relationships between entities
- Enable immediate querying (results improve as processing continues)

### 2. Monitor Processing

1. Go to the **Dashboard** page
2. View real-time processing status
3. See extracted decisions and incidents
4. Track progress metrics

### 3. Search Memory

1. Navigate to the **Search** page
2. Ask natural language questions:
   - "Why did we switch to microservices?"
   - "What caused the authentication outage?"
   - "How did our database architecture evolve?"
3. Get context-aware answers with source references

## Project Structure

```
psychic-fortnight/
├── app/
│   ├── config/          # Configuration management
│   ├── models/          # Pydantic data models
│   ├── core/            # Autonomous processing core
│   ├── ingestion/       # Data ingestion (GitHub, etc.)
│   ├── extraction/      # Memory extraction agents
│   ├── orchestration/   # LangGraph workflows
│   ├── retrieval/       # Search and retrieval
│   ├── memory/          # Storage layer
│   ├── workers/         # Background worker pool
│   ├── ui/              # Streamlit interface
│   ├── prompts/         # LLM prompts
│   └── utils/           # Utilities
├── data/                # Storage (gitignored)
│   ├── raw/             # Raw source data
│   ├── extracted/       # Extracted memories
│   ├── graph/           # Knowledge graph
│   ├── embeddings/      # Vector database
│   └── state/           # Processing checkpoints
├── docs/                # Documentation
├── main.py              # Entry point
├── pyproject.toml       # Project configuration
└── requirements.txt     # Dependencies
```

## Key Features

### Autonomous Processing

Once you connect a source, the system:
- **Discovers** all available data automatically
- **Processes** in the background with checkpoints
- **Extracts** decisions, incidents, timelines
- **Connects** related entities
- **Enables** immediate querying

### Progressive Availability

- Query immediately after connecting a source
- Results improve as processing continues
- No waiting for complete processing

### Resumable Workflows

- Processing survives crashes
- Resumes from last checkpoint
- No duplicate processing

### Source Provenance

- Every memory links to its source
- No hallucinations
- Traceable to original PR/Issue/Comment

## Configuration

### Processing Settings

Edit `.env` to adjust:

```env
# Worker Configuration
MAX_WORKERS=5              # Concurrent workers
BATCH_SIZE=10              # Items per batch
CHECKPOINT_INTERVAL=50     # Items between checkpoints

# Rate Limiting
RATE_LIMIT_REQUESTS=100    # Max requests per period
RATE_LIMIT_PERIOD=60       # Period in seconds

# Confidence Thresholds
MIN_DECISION_CONFIDENCE=0.7
MIN_INCIDENT_CONFIDENCE=0.6
MIN_RELATIONSHIP_CONFIDENCE=0.5

# LLM Configuration
LLM_MODEL=meta-llama/llama-3-1-70b-instruct
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=2048
```

### Logging

Logs are stored in `logs/` directory:
- JSON format for structured logging
- Daily rotation
- Configurable log level

```env
LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT=json         # json or text
```

## Troubleshooting

### Import Errors

If you see import errors, ensure:
1. Virtual environment is activated
2. Dependencies are installed: `pip install -r requirements.txt`
3. You're in the project root directory

### API Key Issues

If you see authentication errors:
1. Verify `.env` file exists
2. Check API keys are correct
3. Ensure no extra spaces in `.env` values

### Processing Not Starting

If processing doesn't start:
1. Check logs in `logs/` directory
2. Verify GitHub token (if using private repos)
3. Check rate limits haven't been exceeded

### UI Not Loading

If Streamlit UI doesn't load:
1. Check port 8501 is available
2. Try: `streamlit run app/ui/app.py --server.port=8502`
3. Check firewall settings

## Next Steps

1. **Connect Your First Repository**: Start with a small repo to test
2. **Explore Extracted Memories**: Review decisions and incidents
3. **Query the System**: Ask questions about your engineering history
4. **Monitor Processing**: Watch the autonomous system work
5. **Add More Sources**: Scale to multiple repositories

## Getting Help

- Check `docs/` for detailed documentation
- Review `IMPLEMENTATION_PLAN.md` for architecture details
- See `docs/WORKFLOWS.md` for processing workflows
- Read `docs/AUTONOMOUS_FLOW_DIAGRAM.md` for system flow

## Development

### Running Tests

```bash
pytest tests/
```

### Code Quality

```bash
# Format code
black app/

# Type checking
mypy app/

# Linting
ruff check app/
```

### Adding New Features

1. Review `IMPLEMENTATION_PLAN.md`
2. Follow existing patterns in `app/`
3. Add tests for new functionality
4. Update documentation

## What's Next?

The system is designed for continuous improvement:
- More extraction types (ownership, questions, etc.)
- Additional source integrations (GitLab, Jira, etc.)
- Advanced search capabilities
- Timeline visualizations
- Relationship graphs
- Export capabilities

Start exploring your engineering memory! 🧠