# Engineering Memory System - Streamlit UI

## Overview

This is the Streamlit-based user interface for the Engineering Memory System. It provides an interactive web application for configuring, monitoring, and querying your engineering knowledge base.

## Features

### 6 Main Pages

1. **Home** - System overview and status dashboard
2. **Setup** - Configure GitHub credentials and repository settings
3. **Processing Dashboard** - Monitor ingestion and extraction progress
4. **Query Interface** - Chat-based interface for querying engineering memory
5. **Timeline View** - Visual exploration of engineering events over time
6. **Knowledge Graph** - Interactive visualization of relationships
7. **Decision Explorer** - Browse and filter engineering decisions

## Installation

### Prerequisites

```bash
pip install streamlit pandas
```

### Optional Dependencies

For enhanced graph visualization:
```bash
pip install streamlit-agraph pyvis plotly
```

## Running the Application

### From the project root:

```bash
streamlit run app/ui/Home.py
```

### From the ui directory:

```bash
cd app/ui
streamlit run Home.py
```

The application will open in your default web browser at `http://localhost:8501`

## Configuration

### First-Time Setup

1. Navigate to the **Setup** page
2. Enter your GitHub Personal Access Token
3. Specify the repository owner and name
4. (Optional) Configure LLM API credentials
5. Save the configuration

### Environment Variables

The UI reads and writes configuration to `.env` file:

```env
GITHUB_TOKEN=your_github_token
REPO_OWNER=repository_owner
REPO_NAME=repository_name
LLM_API_KEY=your_llm_api_key
```

## Usage Guide

### 1. Initial Setup

- Go to **Setup** page
- Configure GitHub credentials
- Validate connection
- Save configuration

### 2. Start Processing

- Go to **Processing Dashboard**
- Click "Start Ingestion" to begin fetching data
- Monitor progress in real-time
- Wait for extraction to complete

### 3. Explore Data

Once processing is complete, you can:

- **Query Interface**: Ask natural language questions
- **Timeline View**: Browse events chronologically
- **Knowledge Graph**: Explore relationships
- **Decision Explorer**: Filter and search decisions

## Page Details

### Home Page

- System status overview
- Quick statistics
- Configuration status
- Navigation guide

### Setup Page

**Features:**
- GitHub repository configuration
- Token validation
- LLM API configuration
- Data directory status
- Advanced settings (rate limiting, workers)

### Processing Dashboard

**Features:**
- Ingestion progress tracking
- Extraction statistics by artifact type
- Processing queue status
- Indexing status (vector store, graph)
- Worker controls (pause/resume)
- Auto-refresh option

### Query Interface

**Features:**
- Multi-turn chat conversation
- Source-grounded answers
- Confidence scores
- Query filters (artifact types, services, date range)
- Example queries
- Chat history export
- Session statistics

### Timeline View

**Features:**
- Chronological event display
- Date range filtering
- Event type filtering
- Multiple view modes (Timeline, Table, Calendar)
- Event distribution chart
- Pagination
- Detailed event information

### Knowledge Graph

**Features:**
- Interactive graph visualization
- Node type filtering
- Relationship filtering
- Graph depth control
- Layout options
- Node search
- Graph explorer by type
- Export options (JSON, CSV)

### Decision Explorer

**Features:**
- Decision browsing and filtering
- Confidence score filtering
- Service and tag filtering
- Search functionality
- Multiple view modes (Cards, Table, Compact)
- Detailed decision information
- Export options (JSON, CSV)
- Statistics dashboard

## Data Flow

```
Setup → Configure credentials
  ↓
Processing Dashboard → Start ingestion
  ↓
Raw data stored → Extraction begins
  ↓
Artifacts extracted → Indexing begins
  ↓
Vector store + Graph updated
  ↓
Query Interface, Timeline, Graph, Decisions → Explore data
```

## Troubleshooting

### "No data available" messages

- Ensure ingestion has been started from Processing Dashboard
- Check that extraction has completed
- Verify data directories exist in `data/` folder

### Configuration not saving

- Check file permissions on `.env` file
- Ensure you're running from the correct directory
- Verify all required fields are filled

### Graph visualization not showing

- Install optional graph visualization libraries
- Check that `data/graph/knowledge_graph.json` exists
- Verify graph indexing has completed

### Query interface not working

- Ensure LLM API is configured (Step 4 integration)
- Check that extracted artifacts exist
- Verify vector store is initialized

## Development

### Adding New Pages

1. Create new file in `app/ui/pages/` with naming convention `N_Page_Name.py`
2. Import utilities from `app/ui/utils/`
3. Follow existing page structure
4. Page will automatically appear in sidebar

### Customizing Filters

Edit filter options in respective page files:
- Timeline filters: `4_Timeline_View.py`
- Decision filters: `6_Decision_Explorer.py`
- Graph filters: `5_Knowledge_Graph.py`

### Styling

Streamlit uses its own theming system. To customize:

1. Create `.streamlit/config.toml` in project root
2. Add theme configuration:

```toml
[theme]
primaryColor = "#FF4B4B"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"
```

## Architecture

```
app/ui/
├── Home.py                 # Main entrypoint
├── pages/                  # Page modules
│   ├── 1_Setup.py
│   ├── 2_Processing_Dashboard.py
│   ├── 3_Query_Interface.py
│   ├── 4_Timeline_View.py
│   ├── 5_Knowledge_Graph.py
│   └── 6_Decision_Explorer.py
├── components/             # Reusable UI components
├── utils/                  # Utility modules
│   ├── state.py           # Session state management
│   └── api.py             # Backend API integration
└── README.md              # This file
```

## API Integration

The UI integrates with backend services through `app/ui/utils/api.py`:

- **BackendAPI**: Main interface to backend
- **IngestionStateManager**: Ingestion status tracking
- **JsonStore**: Artifact storage access
- **GraphStore**: Knowledge graph access

## Performance Tips

1. **Auto-refresh**: Use sparingly on Processing Dashboard
2. **Pagination**: Enabled by default for large datasets
3. **Filters**: Apply filters before loading large datasets
4. **Export**: Use export features for offline analysis

## Security Notes

- GitHub tokens are masked in the UI
- Tokens are stored in `.env` file (add to `.gitignore`)
- Never commit `.env` file to version control
- Use read-only tokens when possible

## Future Enhancements

- Real-time WebSocket updates for processing status
- Advanced graph visualization with zoom/pan
- Custom dashboard widgets
- Saved query templates
- User authentication and multi-user support
- Export to various formats (PDF, Markdown, etc.)

## Support

For issues or questions:
1. Check this README
2. Review page-specific documentation
3. Check backend logs in `data/logs/`
4. Verify data directory structure

## License

Part of the Engineering Memory System project.