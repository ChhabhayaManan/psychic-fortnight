# First Complete Flow: Autonomous Processing → Query

## Overview

This document details the **first complete autonomous flow** to implement, following the principle of building one end-to-end workflow with autonomous processing before expanding.

**Key Difference**: Instead of manually processing individual PRs, the system autonomously discovers and processes ALL data once a source is connected.

## Flow Diagram

```
User Connects GitHub Repo
    ↓
Autonomous Discovery (finds ALL PRs/Issues)
    ↓
Queue All Items
    ↓
Background Workers (parallel processing)
    ↓
    ├─> Raw Storage
    ├─> Decision Extraction
    └─> Vector Embedding
    ↓
User Queries Anytime (progressive results)
    ↓
Semantic Retrieval
    ↓
Question Answering with Sources
```

## Implementation Steps

### Step 1: Source Connection & Discovery

**Goal**: Connect GitHub repo and autonomously discover all data

**Components**:
- `app/core/source_manager.py` - Manage connected sources
- `app/core/discovery_agent.py` - Auto-discover all data
- `app/ingestion/github/client.py` - GitHub API client
- `data/raw/github/` - Raw storage
- `data/state/` - Processing state & checkpoints

**Implementation**:
```python
# User connects source
source_manager.connect_github_repo(repo_url, token)

# System automatically discovers ALL data
discovery_agent = DiscoveryAgent()
items = await discovery_agent.discover_github_data(repo)
# Returns: all PRs, Issues, Comments, Reviews

# Queue all items for processing
for item in items:
    await ingestion_queue.put(item)

# Save checkpoint
checkpoint_manager.save({
    "source": repo,
    "total_items": len(items),
    "discovered_at": datetime.now()
})
```


### Step 2: Autonomous Background Processing

**Goal**: Process all queued items in parallel without user intervention

**Components**:
- `app/core/orchestrator.py` - Coordinate processing
- `app/workers/worker_pool.py` - Manage parallel workers
- `app/workers/base.py` - Base worker class
- `app/extraction/decisions/extractor.py` - Decision extractor
- `app/models/decision.py` - Decision model
- `data/extracted/decisions/` - Extracted storage

**Implementation**:
```python
# Start worker pool (3 workers by default)
worker_pool = WorkerPool(num_workers=3)
await worker_pool.start()

# Each worker processes items from queue
async def worker_process():
    while True:
        item = await ingestion_queue.get()
        
        # Store raw
        save_raw_json(item, f"data/raw/github/{item.type}_{item.id}.json")
        
        # Extract decision
        decision = await decision_extractor.extract(item)
        
        # Validate confidence
        if decision and decision.confidence > 0.7:
            save_decision(decision, "data/extracted/decisions/")
            
            # Generate embedding immediately
            embedding = embeddings_model.embed(decision.summary)
            vector_store.add(decision.id, embedding, decision.metadata)
        
        # Save checkpoint
        checkpoint_manager.update_progress(item.id)
```


### Step 3: Progressive Availability

**Goal**: User can query immediately while processing continues

**Components**:
- `app/core/progress_tracker.py` - Track processing status
- `app/retrieval/semantic.py` - Semantic search
- `app/memory/vector_store.py` - ChromaDB interface

**Implementation**:
```python
# User queries while processing is ongoing
progress = progress_tracker.get_status()
# Returns: {
#   "total_items": 200,
#   "processed": 50,
#   "progress": 25%,
#   "memories_extracted": 15
# }

# Query works with whatever is processed so far
query = "Why did we migrate to gRPC?"
results = vector_store.search(query, n_results=5)

# Results improve as more data is processed
# Time 0: 0 results
# Time 1min: 3 results (15% processed)
# Time 5min: 8 results (75% processed)
# Time 10min: 12 results (100% processed)
```


### Step 4: Continuous Monitoring

**Goal**: Automatically detect and process new data

**Components**:
- `app/core/orchestrator.py` - Monitor for updates
- `app/utils/rate_limiter.py` - Respect API limits

**Implementation**:
```python
# After initial processing completes
async def monitor_source(source):
    while True:
        # Wait 5 minutes
        await asyncio.sleep(300)
        
        # Check for new PRs/Issues
        new_items = await discovery_agent.discover_new(source)
        
        if new_items:
            # Queue new items
            for item in new_items:
                await ingestion_queue.put(item)
            
            # Workers automatically process them
            logger.info(f"Found {len(new_items)} new items")
```


### Step 5: Query & Answer Generation

**Goal**: Generate answer with full source provenance

**Components**:
- `app/retrieval/semantic.py` - Semantic search
- `app/orchestration/answer.py` - Answer generator
- `app/prompts/answer_generation.py` - Answer prompt

**Implementation**:
```python
# User query (works anytime, even during processing)
query = "Why did we migrate to gRPC?"

# Generate query embedding
query_embedding = embeddings_model.embed(query)

# Semantic search
results = vector_store.search(
    query_embedding=query_embedding,
    n_results=5,
    filter={"confidence": {"$gte": 0.7}}
)

# Generate answer with evidence
answer = answer_generator.generate(
    query=query,
    evidence=results
)

# Response includes full provenance
response = {
    "answer": answer,
    "sources": [
        {
            "decision": d.title,
            "pr": d.source_refs[0].url,
            "contributor": d.source_refs[0].contributor,
            "confidence": d.confidence
        }
        for d in results
    ],
    "processing_status": progress_tracker.get_status()
}
```


## Detailed Component Specifications

### 1. GitHub Client

**File**: `app/ingestion/github/client.py`

**Key Methods**:
```python
class GitHubClient:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.github.com"
    
    def get_pr(self, repo: str, pr_number: int) -> dict:
        """Fetch PR with comments and reviews"""
        pass
    
    def get_pr_files(self, repo: str, pr_number: int) -> list:
        """Fetch changed files"""
        pass
```

### 2. Decision Extractor

**File**: `app/extraction/decisions/extractor.py`

**Key Methods**:
```python
class DecisionExtractor(BaseExtractor):
    def __init__(self, llm_config: dict):
        super().__init__(llm_config)
        self.prompt = load_prompt("decision_extraction")
    
    async def extract(self, pr_data: dict) -> Decision:
        """Extract decision from PR"""
        # Build context
        context = self._build_context(pr_data)
        
        # LLM extraction
        result = await self.llm.ainvoke(
            self.prompt.format(context=context)
        )
        
        # Parse and validate
        decision = self._parse_decision(result)
        decision.confidence = self._calculate_confidence(decision)
        
        return decision
```

### 3. Vector Store

**File**: `app/memory/vector_store.py`

**Key Methods**:
```python
class VectorStore:
    def __init__(self, persist_directory: str):
        self.client = chromadb.PersistentClient(
            path=persist_directory
        )
        self.collection = self.client.get_or_create_collection(
            name="decisions"
        )
    
    def add(self, id: str, embedding: list, metadata: dict):
        """Add document to vector store"""
        pass
    
    def search(self, query_embedding: list, n_results: int = 5):
        """Semantic search"""
        pass
```

### 4. Answer Generator

**File**: `app/orchestration/answer.py`

**Key Methods**:
```python
class AnswerGenerator:
    def __init__(self, llm_config: dict):
        self.llm = create_llm(llm_config)
        self.prompt = load_prompt("answer_generation")
    
    async def generate(self, query: str, evidence: List[Decision]) -> str:
        """Generate answer from evidence"""
        # Format evidence
        context = self._format_evidence(evidence)
        
        # Generate answer
        answer = await self.llm.ainvoke(
            self.prompt.format(
                query=query,
                context=context
            )
        )
        
        return answer
```

## Prompts

### Decision Extraction Prompt

**File**: `app/prompts/decision_extraction.py`

```python
DECISION_EXTRACTION_PROMPT = """
You are analyzing a GitHub Pull Request to extract architectural decisions.

PR Context:
{context}

Extract the following information:

1. Decision Title: A clear, concise title
2. Summary: What decision was made?
3. Reasoning: Why was this decision made?
4. Related Services: Which services are affected?
5. Contributors: Who was involved?

Output as JSON:
{{
  "title": "...",
  "summary": "...",
  "reasoning": "...",
  "related_services": [...],
  "contributors": [...]
}}

Only extract if this PR represents a significant architectural decision.
If not, return null.
"""
```

### Answer Generation Prompt

**File**: `app/prompts/answer_generation.py`

```python
ANSWER_GENERATION_PROMPT = """
You are answering a question about engineering decisions.

Question: {query}

Evidence:
{context}

Generate a clear, concise answer based ONLY on the provided evidence.
Include specific details and reasoning.
If the evidence doesn't fully answer the question, say so.

Answer:
"""
```

## Success Criteria

- [ ] Can fetch GitHub PR via API
- [ ] Can store raw PR data
- [ ] Can extract decision with >0.7 confidence
- [ ] Can generate embeddings
- [ ] Can store in ChromaDB
- [ ] Can perform semantic search
- [ ] Can generate answer with sources
- [ ] End-to-end flow works for one PR

## Next Expansions

After autonomous flow works:

1. **Multiple sources**: Add MCP connectors (Slack, Jira)
2. **All extraction types**: Incidents, Timeline, Ownership, Architecture
3. **Knowledge graph**: Build relationships between memories
4. **LangGraph orchestration**: Dynamic query workflows
5. **Advanced retrieval**: Graph traversal + hybrid search
6. **Full UI**: Streamlit with progress dashboard

## Key Learnings

### What Works
- Simple, focused flow
- Clear data models
- Source provenance
- Confidence filtering

### What to Avoid
- Processing all PRs at once
- Complex orchestration too early
- Multiple extraction types simultaneously
- UI before backend works

## Estimated Timeline

- **Day 1**: Source Manager + Discovery Agent
- **Day 2**: Worker Pool + Background Processing
- **Day 3**: Decision extraction + Checkpointing
- **Day 4**: Vector store + Progressive availability
- **Day 5**: Continuous monitoring
- **Day 6**: Query + Answer generation
- **Day 7**: Refinement + demo

## Demo Script

```python
# 1. Connect source (system takes over automatically)
source_manager.connect_github_repo("myorg/myrepo", token)
print("Source connected - autonomous processing started")

# 2. Check progress (while processing)
await asyncio.sleep(30)  # Wait 30 seconds
status = progress_tracker.get_status()
print(f"Progress: {status['progress']}% ({status['processed']}/{status['total_items']})")
print(f"Memories extracted: {status['memories_extracted']}")

# 3. Query immediately (even during processing)
query = "Why did we choose this approach?"
results = vector_store.search(query)
print(f"Found {len(results)} relevant decisions (so far)")

# 4. Wait for more processing
await asyncio.sleep(60)
results = vector_store.search(query)
print(f"Found {len(results)} relevant decisions (updated)")

# 5. Generate answer
answer = await answer_gen.generate(query, results)
print(f"Answer: {answer}")
print(f"Sources: {[r.source_refs[0].url for r in results]}")

# 6. System continues monitoring for new data automatically
print("System now monitoring for new PRs/Issues...")
```

This demonstrates autonomous processing with progressive availability.