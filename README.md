# 🧠 Agentic Engineering Memory System

> An autonomous system that continuously extracts, connects, and retrieves architectural decisions, incidents, timelines, and organizational knowledge from software development workflows.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🎯 What Is This?

Engineering knowledge disappears because:
- Discussions are fragmented across PRs, issues, and comments
- Architectural decisions are buried in code reviews
- Incident context is lost after resolution
- Team knowledge lives in people's heads

**This system converts chaotic engineering activity into structured organizational memory.**

## ✨ Key Features

### 🤖 Fully Autonomous
- **Connect once, forget forever**: Just connect a GitHub repo
- **Automatic discovery**: Finds all PRs, issues, and discussions
- **Background processing**: Works continuously without intervention
- **Self-healing**: Resumes from checkpoints after crashes

### 🎯 What It Remembers

| Memory Type | Examples |
|------------|----------|
| **Decisions** | "Why did we switch to microservices?" |
| **Incidents** | "What caused the auth outage?" |
| **Timeline** | "How did our architecture evolve?" |
| **Ownership** | "Who understands the payment service?" |
| **Relationships** | "What decisions led to this incident?" |

### 🔍 Intelligent Retrieval
- Natural language queries
- Context-aware answers
- Source provenance (no hallucinations)
- Progressive results (query while processing)

### 📊 Built for Scale
- Concurrent processing with worker pools
- Rate limiting and backoff
- Checkpoint-based resumption
- Efficient vector and graph storage

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- IBM watsonx.ai account
- GitHub Personal Access Token (optional)

### Installation

```bash
# Clone repository
git clone <repository-url>
cd psychic-fortnight

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Run

```bash
python main.py
```

The UI opens at `http://localhost:8501`

**See [QUICKSTART.md](QUICKSTART.md) for detailed setup instructions.**

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        USER INTERFACE                        │
│                    (Streamlit Dashboard)                     │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────┐
│                   ORCHESTRATION LAYER                        │
│              (LangGraph Autonomous Workflows)                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Discovery  │  │  Processing  │  │  Monitoring  │     │
│  │    Agent     │  │  Coordinator │  │    Agent     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────┐
│                    PROCESSING LAYER                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Ingestion   │  │  Extraction  │  │  Retrieval   │     │
│  │   Workers    │  │    Agents    │  │   Engines    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────┐
│                     STORAGE LAYER                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Raw Data    │  │   Vector DB  │  │  Knowledge   │     │
│  │   (JSON)     │  │  (ChromaDB)  │  │    Graph     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## 🔄 How It Works

### 1. Connect Source
```python
# User connects GitHub repository
source = connect_github_repo("owner/repo")
```

### 2. Autonomous Discovery
```
Discovery Agent:
├── Scans repository
├── Finds all PRs (open + closed)
├── Finds all Issues (open + closed)
├── Queues for processing
└── Continues monitoring for new items
```

### 3. Background Processing
```
Worker Pool:
├── Fetches raw data (PR/Issue/Comments)
├── Stores raw data (provenance)
├── Extracts memories (LLM agents)
│   ├── Decisions
│   ├── Incidents
│   ├── Timeline events
│   └── Relationships
├── Generates embeddings (vector search)
├── Updates knowledge graph
└── Creates checkpoints (resumable)
```

### 4. Intelligent Retrieval
```
User Query: "Why did we remove Redis?"

Retrieval Engine:
├── Vector search (semantic similarity)
├── Graph traversal (related decisions)
├── Temporal filtering (timeline context)
├── Confidence scoring
└── Returns: Decision + Sources + Related Context
```

## 📁 Project Structure

```
psychic-fortnight/
├── app/
│   ├── core/              # Autonomous processing core
│   │   ├── source_manager.py
│   │   ├── discovery_agent.py
│   │   ├── orchestrator.py
│   │   └── checkpoint_manager.py
│   ├── ingestion/         # Data collection
│   │   └── github/
│   ├── extraction/        # Memory extraction
│   │   ├── decisions/
│   │   ├── incidents/
│   │   └── timeline/
│   ├── orchestration/     # LangGraph workflows
│   ├── retrieval/         # Search strategies
│   ├── memory/            # Storage layer
│   ├── workers/           # Background workers
│   ├── models/            # Pydantic schemas
│   ├── config/            # Configuration
│   ├── ui/                # Streamlit interface
│   └── utils/             # Utilities
├── data/                  # Storage (gitignored)
│   ├── raw/               # Raw source data
│   ├── extracted/         # Extracted memories
│   ├── graph/             # Knowledge graph
│   ├── embeddings/        # Vector database
│   └── state/             # Processing checkpoints
├── docs/                  # Documentation
├── tests/                 # Test suite
├── main.py                # Entry point
└── requirements.txt       # Dependencies
```

## 🛠️ Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Orchestration** | LangGraph | Autonomous workflow management |
| **Agents** | LangChain | LLM-powered extraction agents |
| **LLM** | IBM watsonx.ai | Language understanding |
| **Vector DB** | ChromaDB | Semantic search |
| **Graph DB** | NetworkX | Relationship storage |
| **UI** | Streamlit | Interactive dashboard |
| **Models** | Pydantic | Data validation |
| **API** | PyGithub | GitHub integration |

## 📖 Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Get started in 5 minutes
- **[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)** - Detailed architecture
- **[docs/AUTONOMOUS_FLOW_DIAGRAM.md](docs/AUTONOMOUS_FLOW_DIAGRAM.md)** - System flow
- **[docs/WORKFLOWS.md](docs/WORKFLOWS.md)** - Processing workflows
- **[docs/SETUP.md](docs/SETUP.md)** - Development setup

## 🎯 Use Cases

### For Engineering Teams
- **Onboarding**: New engineers understand past decisions
- **Incident Response**: Quick access to similar past incidents
- **Architecture Reviews**: See evolution of system design
- **Knowledge Retention**: Preserve institutional knowledge

### For Engineering Managers
- **Decision Tracking**: Understand why choices were made
- **Team Insights**: See who owns what knowledge
- **Risk Assessment**: Identify unresolved technical concerns
- **Timeline Analysis**: Track architectural evolution

### For Technical Writers
- **Documentation**: Auto-generate architecture docs
- **Decision Records**: Extract ADRs from discussions
- **Incident Reports**: Compile post-mortems
- **Knowledge Base**: Build searchable knowledge base

## 🔮 Roadmap

### Phase 1: Foundation (Current)
- [x] Core models and configuration
- [x] Autonomous processing framework
- [x] Basic UI
- [ ] GitHub ingestion
- [ ] Decision extraction
- [ ] Vector search

### Phase 2: Intelligence
- [ ] Incident extraction
- [ ] Timeline generation
- [ ] Relationship inference
- [ ] Advanced search
- [ ] Graph visualization

### Phase 3: Scale
- [ ] Multi-repository support
- [ ] GitLab integration
- [ ] Jira integration
- [ ] Export capabilities
- [ ] API access

### Phase 4: Advanced
- [ ] Predictive insights
- [ ] Anomaly detection
- [ ] Automated documentation
- [ ] Team analytics
- [ ] Custom extractors

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📝 License

MIT License - see [LICENSE](LICENSE) for details

## 🙏 Acknowledgments

Built with:
- [LangGraph](https://github.com/langchain-ai/langgraph) - Autonomous workflows
- [LangChain](https://github.com/langchain-ai/langchain) - LLM framework
- [IBM watsonx.ai](https://www.ibm.com/watsonx) - Enterprise LLM
- [ChromaDB](https://www.trychroma.com/) - Vector database
- [Streamlit](https://streamlit.io/) - UI framework

## 📧 Contact

Questions? Issues? Ideas?
- Open an issue on GitHub
- Check existing documentation
- Review implementation plan

---

**Remember**: This is not a chatbot, not a RAG app, not a GitHub summarizer.

**This is an autonomous engineering memory operating system.** 🧠

Start building your organizational memory today!
