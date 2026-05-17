# Autonomous Background Processing Architecture

## Core Concept

**Once a knowledge source is connected, the system autonomously processes ALL data without user intervention.**

## User Flow

```
User connects GitHub repo
    ↓
System automatically:
  1. Discovers all PRs/Issues
  2. Queues for processing
  3. Extracts memories
  4. Builds knowledge graph
  5. Updates continuously
    ↓
User can query immediately
(while processing continues in background)
```

## Key Principles

### 1. Autonomous Discovery
- System discovers all available data
- No manual selection needed
- Continuous monitoring for new data

### 2. Automatic Processing
- Background workers start immediately
- Process until completion
- Resume on restart

### 3. Progressive Availability
- Partial results available immediately
- Knowledge base grows over time
- No "waiting" state for users

### 4. Continuous Sync
- Monitor for new PRs/Issues
- Auto-process new content
- Keep knowledge base current

## Architecture Changes

### Before (Manual Trigger)
```
User → Select PR → Process → Query
```

### After (Autonomous)
```
User → Connect Source → [Auto Processing] → Query Anytime
```

## Component Design

### 1. Source Manager

**Purpose**: Manage connected knowledge sources

```python
class SourceManager:
    """Manages connected knowledge sources"""
    
    def connect_github_repo(self, repo_url: str, token: str):
        """
        Connect GitHub repository
        - Validates access
        - Discovers all PRs/Issues
        - Starts autonomous processing
        - Monitors for updates
        """
        
    def connect_mcp_server(self, server_config: dict):
        """
        Connect MCP server
        - Establishes connection
        - Discovers available data
        - Starts processing pipeline
        """
    
    def get_processing_status(self) -> dict:
        """
        Returns current processing state:
        - Total items discovered
        - Items processed
        - Items in queue
        - Estimated completion
        """
```

### 2. Discovery Agent

**Purpose**: Automatically discover all available data

```python
class DiscoveryAgent:
    """Discovers all data from connected sources"""
    
    async def discover_github_data(self, repo: str) -> DiscoveryResult:
        """
        Discovers:
        - All PRs (open + closed)
        - All Issues (open + closed)
        - All comments
        - All reviews
        - File changes
        
        Returns: List of items to process
        """
    
    async def discover_mcp_data(self, server: str) -> DiscoveryResult:
        """
        Discovers data from MCP server
        """
```

### 3. Processing Orchestrator

**Purpose**: Coordinate autonomous processing

```python
class ProcessingOrchestrator:
    """Orchestrates autonomous background processing"""
    
    def __init__(self):
        self.discovery_agent = DiscoveryAgent()
        self.ingestion_queue = Queue()
        self.extraction_queue = Queue()
        self.workers = []
        self.is_running = False
    
    async def start_processing(self, source: Source):
        """
        1. Discover all data
        2. Queue for processing
        3. Start workers
        4. Monitor progress
        5. Handle new data
        """
        
        # Discover
        items = await self.discovery_agent.discover(source)
        
        # Queue
        for item in items:
            await self.ingestion_queue.put(item)
        
        # Start workers
        await self.start_workers()
        
        # Monitor for new data
        await self.monitor_source(source)
    
    async def monitor_source(self, source: Source):
        """
        Continuously monitor for new data:
        - New PRs
        - New Issues
        - New comments
        - Updates to existing items
        """
```

### 4. Worker Pool

**Purpose**: Process items autonomously

```python
class WorkerPool:
    """Manages pool of background workers"""
    
    def __init__(self, num_workers: int = 3):
        self.workers = []
        self.num_workers = num_workers
    
    async def start(self):
        """Start all workers"""
        for i in range(self.num_workers):
            worker = Worker(id=i)
            self.workers.append(worker)
            asyncio.create_task(worker.run())
    
    async def stop(self):
        """Gracefully stop all workers"""
        for worker in self.workers:
            await worker.stop()
```

### 5. Progress Tracker

**Purpose**: Track processing progress

```python
class ProgressTracker:
    """Tracks autonomous processing progress"""
    
    def __init__(self):
        self.total_items = 0
        self.processed_items = 0
        self.failed_items = 0
        self.in_progress = 0
    
    def get_status(self) -> ProcessingStatus:
        """
        Returns:
        - Progress percentage
        - Items per minute
        - Estimated completion time
        - Current phase
        """
    
    def is_complete(self) -> bool:
        """Check if all processing is complete"""
        return self.processed_items + self.failed_items == self.total_items
```

## Processing Pipeline

### Phase 1: Discovery

```
Source Connected
    ↓
Discover All Data
    ↓
Create Processing Plan
    ↓
Queue All Items
```

### Phase 2: Ingestion

```
For each item in queue:
    ↓
Fetch Raw Data
    ↓
Store in data/raw/
    ↓
Add to Extraction Queue
```

### Phase 3: Extraction

```
For each raw item:
    ↓
Run Extraction Agents:
  - Decision Extractor
  - Incident Extractor
  - Timeline Extractor
  - Ownership Extractor
    ↓
Filter by Confidence
    ↓
Deduplicate
    ↓
Store Memories
```

### Phase 4: Indexing

```
For each memory:
    ↓
Generate Embeddings
    ↓
Update Vector Store
    ↓
Update Knowledge Graph
    ↓
Refresh Snapshot
```

### Phase 5: Monitoring

```
Continuously:
    ↓
Check for New Data
    ↓
Queue New Items
    ↓
Process Incrementally
```

## State Management

### Processing States

```python
class ProcessingState(Enum):
    IDLE = "idle"                    # No sources connected
    DISCOVERING = "discovering"      # Finding all data
    QUEUED = "queued"               # Items queued
    PROCESSING = "processing"        # Active processing
    MONITORING = "monitoring"        # Watching for updates
    PAUSED = "paused"               # Temporarily stopped
    ERROR = "error"                 # Error occurred
```

### Persistence

```python
# Save state to resume after restart
{
  "sources": [
    {
      "type": "github",
      "repo": "owner/repo",
      "last_sync": "2024-01-15T10:00:00Z",
      "total_items": 150,
      "processed_items": 120,
      "state": "processing"
    }
  ],
  "queues": {
    "ingestion": ["item1", "item2"],
    "extraction": ["item3", "item4"]
  },
  "checkpoints": {
    "last_pr_number": 145,
    "last_issue_number": 89
  }
}
```

## UI Integration

### Dashboard View

```
┌─────────────────────────────────────────┐
│ Connected Sources                       │
├─────────────────────────────────────────┤
│ ✓ GitHub: owner/repo                    │
│   Status: Processing                    │
│   Progress: 120/150 items (80%)         │
│   ETA: 15 minutes                       │
│                                         │
│ ✓ MCP: Slack Workspace                  │
│   Status: Monitoring                    │
│   Last sync: 2 minutes ago              │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ Processing Activity                     │
├─────────────────────────────────────────┤
│ [████████████░░░░] 80%                  │
│                                         │
│ Current Phase: Extraction               │
│ Items/min: 8                            │
│ Workers: 3 active                       │
│                                         │
│ Memories Extracted:                     │
│ • Decisions: 45                         │
│ • Incidents: 12                         │
│ • Timeline Events: 89                   │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ Query Interface                         │
├─────────────────────────────────────────┤
│ Ask questions while processing...      │
│ (Results improve as more data loads)   │
└─────────────────────────────────────────┘
```

### Source Connection Flow

```
1. User clicks "Connect Source"
2. Selects GitHub / MCP / File Upload
3. Provides credentials
4. System validates access
5. Discovery starts automatically
6. Processing begins immediately
7. User can query right away
8. Dashboard shows progress
```

## Configuration

### Auto-Processing Settings

```env
# Autonomous Processing
AUTO_PROCESS_ON_CONNECT=true
MAX_WORKERS=3
BATCH_SIZE=10
PROCESS_RATE_LIMIT=100  # items per minute

# Discovery Settings
DISCOVER_ALL_PRS=true
DISCOVER_ALL_ISSUES=true
DISCOVER_CLOSED_ITEMS=true
MAX_ITEMS_PER_SOURCE=10000

# Monitoring
SYNC_INTERVAL=300  # seconds (5 minutes)
ENABLE_CONTINUOUS_SYNC=true

# Processing Priorities
PRIORITY_RECENT_ITEMS=true
PRIORITY_HIGH_ACTIVITY=true
```

## Error Handling

### Resilient Processing

```python
async def process_item(item):
    """Process with automatic retry"""
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            result = await extract_memory(item)
            return result
        except Exception as e:
            retry_count += 1
            if retry_count == max_retries:
                # Log failure, continue with next item
                log_failed_item(item, e)
                return None
            await asyncio.sleep(2 ** retry_count)  # Exponential backoff
```

### Graceful Degradation

- If extraction fails, store raw data
- If one agent fails, others continue
- If rate limited, slow down automatically
- If connection lost, resume when restored

## Performance Optimization

### Parallel Processing

```python
# Process multiple items concurrently
async def process_batch(items):
    tasks = [process_item(item) for item in items]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

### Rate Limiting

```python
# Respect API rate limits
class RateLimiter:
    def __init__(self, max_per_minute: int):
        self.max_per_minute = max_per_minute
        self.tokens = max_per_minute
        self.last_update = time.time()
    
    async def acquire(self):
        """Wait if rate limit reached"""
        while self.tokens <= 0:
            await asyncio.sleep(1)
            self._refill_tokens()
        self.tokens -= 1
```

### Incremental Indexing

```python
# Update indexes incrementally
def update_vector_store(new_memories):
    """Add only new memories, don't rebuild entire index"""
    for memory in new_memories:
        vector_store.add(memory)
```

## Success Metrics

### Processing Efficiency
- Items processed per minute
- Success rate (>95%)
- Average processing time per item
- Worker utilization

### System Health
- Queue depth
- Error rate
- Memory usage
- API rate limit status

### User Experience
- Time to first result
- Query response time
- Knowledge base completeness
- Update latency

## Implementation Priority

1. **Source Manager** - Connect and validate sources
2. **Discovery Agent** - Find all available data
3. **Processing Orchestrator** - Coordinate autonomous processing
4. **Worker Pool** - Process items in background
5. **Progress Tracker** - Show status to user
6. **Monitoring** - Continuous sync for new data

This ensures the system works autonomously from the moment a source is connected.