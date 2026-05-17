# 🧠 Engineering Memory System

An autonomous system that converts fragmented engineering activity into structured, queryable organizational memory. It automatically ingests data from development platforms, extracts high-value artifacts using LLMs, and builds a connected knowledge graph of decisions, incidents, and architectural evolution.

## 🎯 The Problem

Engineering knowledge is often lost because it's buried in:
- Thousands of Pull Requests and Issues
- Fragmented comment threads and code reviews
- Transient incident discussions
- Individual developers' memories

This system ensures that **why** things were done is as accessible as **what** was done.

## ✨ Core Capabilities

### 🕵️ Autonomous Extraction
The system uses specialized LLM agents (supporting Watsonx, Gemini, and Groq) to identify and extract:
- **Architectural Decisions (ADRs):** Captures the reasoning behind technical choices.
- **Incidents & Post-mortems:** Identifies root causes and resolutions from bug fixes.
- **Technical Timeline:** Maps the evolution of the codebase over time.
- **System Architecture:** Tracks changes to components and dependencies.
- **Expertise & Ownership:** Identifies which contributors own specific domains.
- **Unresolved Questions:** Surfaces TBDs and open questions from discussions.
- **Relationships:** Links related decisions, incidents, and changes.

### 🔍 Intelligent Retrieval
- **Natural Language Querying:** Ask questions like "Why did we choose gRPC over REST?" or "Who should I talk to about the authentication service?"
- **Context-Aware Answers:** Orchestrated via LangGraph to synthesize answers from vector and graph data.
- **Traceable Evidence:** Every answer includes direct citations to source PRs and issues.

### ⚡ Production-Ready Pipeline
- **Generic Repository Support:** Works with any GitHub repository.
- **One-Click Ingestion:** Fully automated pipeline from discovery to indexing.
- **Resumable Processing:** Uses persistent state and checkpoints to handle large datasets.
- **Rate-Limit Aware:** Built-in token bucket rate limiting for stable API interaction.

## 🛠️ System Architecture

1.  **Ingestion:** Scans repository history, fetches raw JSON data, and stores it locally.
2.  **Extraction:** Parallel LLM agents process raw data using keyword pre-filtering for cost efficiency.
3.  **Indexing:** Stores structured artifacts in ChromaDB (Vector) and NetworkX (Graph).
4.  **Orchestration:** LangGraph-based RAG pipeline for complex multi-hop queries.

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.11+
- Virtual environment (e.g., `starstruck`)
- IBM Watsonx.ai, Google Gemini, or Groq API credentials
- GitHub Personal Access Token (for private repos or higher rate limits)

### 2. Installation
```bash
git clone https://github.com/IBM/mcp-context-forge.git
cd mcp-context-forge
# Use your virtual env
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 3. Configuration
Copy `.env.example` to `.env` and fill in your credentials.
- **Watsonx:** Requires `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, and `LLM_MODEL`.
- **GitHub:** `GITHUB_TOKEN` is recommended to avoid rate limits.

### 4. Running the Application
```bash
streamlit run streamlit_app.py
```
Navigate to the **Setup** page in the UI to verify your connection, then use the **Processing Dashboard** to start the autonomous pipeline.

## 🔮 Future Developments

- **MCP Server Integration:** Expose the engineering memory as a Model Context Protocol (MCP) server, allowing AI agents (like Claude or Gemini) to query the knowledge base directly.
- **Multi-Source Connectors:** Integration with GitLab, Bitbucket, Jira, and Slack for a unified memory across all tools.
- **Automated ADR Generation:** Automatically drafting ADRs from PR discussions.
- **Cross-Repository Memory:** Analyzing patterns and dependencies across an entire organization's portfolio.
- **Deeper Code Analysis:** Integrating AST-based analysis with the conversational history.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---
Built with ❤️ by the Psychic Fortnight team for the IBM Watsonx.ai Hackathon.
