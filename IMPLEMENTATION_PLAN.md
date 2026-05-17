# Implementation Plan: Step 1 - Repository Structure

## Objective
Set up the foundational architecture for the Agentic Engineering Memory System with **autonomous background processing** that automatically discovers and processes all data when a source is connected, also then after each new source is connected. This updates the memory system with all relevant information from the source, ensuring that the system is always up-to-date and ready to provide accurate and relevant information at the time of query.

## Directory Structure Overview

```
psychic-fortnight/

├── app/
│
├── ingestion/
│   ├── github/
│   ├── mcp/
│   ├── files/
│   └── connectors/
│
├── extraction/
│   ├── decisions/
│   ├── incidents/
│   ├── architecture/
│   ├── ownership/
│   ├── unresolved/
│   └── timeline/
│
├── orchestration/
│   ├── graph.py
│   ├── state.py
│   ├── planner.py
│   ├── retrieval.py
│   ├── summarizer.py
│   └── answer.py
│
├── retrieval/
│   ├── semantic.py
│   ├── graph_search.py
│   ├── reranking.py
│   └── hybrid.py
│
├── memory/
│   ├── vector_store.py
│   ├── graph_store.py
│   ├── json_store.py
│   └── snapshots.py
│
├── workers/
│   ├── ingestion_worker.py
│   ├── extraction_worker.py
│   └── indexing_worker.py
│
├── models/
│   ├── decision.py
│   ├── incident.py
│   ├── timeline.py
│   └── relationship.py
│
├── ui/
│   ├── dashboard.py
│   ├── query_page.py
│   ├── timeline_view.py
│   └── graph_view.py
│
├── prompts/
│
├── config/
│
└── main.py
```
