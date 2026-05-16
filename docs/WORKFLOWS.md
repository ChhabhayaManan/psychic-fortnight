# System Workflows

## Overview

This document details the key workflows in the Agentic Engineering Memory System, showing how data flows through the system and how different components interact.

## 1. Ingestion Workflow

### GitHub PR Ingestion

```mermaid
graph TD
    A[User Connects GitHub Repo] --> B[GitHub Connector]
    B --> C[Fetch PRs/Issues/Comments]
    C --> D[Store Raw JSON]
    D --> E[Add to Ingestion Queue]
    E --> F[Ingestion Worker]
    F --> G[Parse & Validate]
    G --> H[Deduplication Check]
    H --> I{Already Exists?}
    I -->|Yes| J[Skip]
    I -->|No| K[Add to Extraction Queue]
    K --> L[Extraction Worker]
```

### File Upload Ingestion

```mermaid
graph TD
    A[User Uploads File] --> B[File Handler]
    B --> C[Validate Format]
    C --> D{Valid?}
    D -->|No| E[Error Message]
    D -->|Yes| F[Store Raw File]
    F --> G[Extract Text Content]
    G --> H[Add to Extraction Queue]
```

## 2. Extraction Workflow

### Decision Extraction

```mermaid
graph TD
    A[Raw PR/Issue Data] --> B[Decision Extractor Agent]
    B --> C[LLM Analysis]
    C --> D[Extract Decision Elements]
    D --> E[Calculate Confidence Score]
    E --> F{Confidence > 0.7?}
    F -->|No| G[Discard]
    F -->|Yes| H[Create Decision Object]
    H --> I[Add Source References]
    I --> J[Store in data/extracted/decisions/]
    J --> K[Generate Embeddings]
    K --> L[Update Vector Store]
    L --> M[Update Knowledge Graph]
    M --> N[Refresh Project Snapshot]
```

### Multi-Agent Extraction Pipeline

```mermaid
graph TD
    A[Raw Data] --> B[Decision Extractor]
    A --> C[Incident Extractor]
    A --> D[Architecture Extractor]
    A --> E[Ownership Extractor]
    A --> F[Timeline Extractor]
    
    B --> G[Confidence Filter]
    C --> G
    D --> G
    E --> G
    F --> G
    
    G --> H[Deduplication]
    H --> I[Relationship Builder]
    I --> J[Storage Layer]
```

## 3. Query Workflow

### Dynamic Query Orchestration (LangGraph)

```mermaid
graph TD
    A[User Query] --> B[Planner Agent]
    B --> C{Query Type?}
    
    C -->|Decision| D[Decision Strategy]
    C -->|Incident| E[Incident Strategy]
    C -->|Timeline| F[Timeline Strategy]
    C -->|Ownership| G[Ownership Strategy]
    
    D --> H[Semantic Retrieval]
    E --> H
    F --> I[Timeline Search]
    G --> J[Graph Traversal]
    
    H --> K[Evidence Aggregation]
    I --> K
    J --> K
    
    K --> L[Reranking]
    L --> M[Summarization Agent]
    M --> N[Answer Generation]
    N --> O[Response with Sources]
```

### Retrieval Strategies

#### Semantic Search
```mermaid
graph LR
    A[Query] --> B[Generate Embedding]
    B --> C[ChromaDB Search]
    C --> D[Top K Results]
    D --> E[Filter by Confidence]
    E --> F[Return Memories]
```

#### Graph Traversal
```mermaid
graph TD
    A[Starting Entity] --> B[Find Related Nodes]
    B --> C[Traverse Relationships]
    C --> D[Collect Connected Memories]
    D --> E[Calculate Relevance]
    E --> F[Return Subgraph]
```

#### Hybrid Retrieval
```mermaid
graph TD
    A[Query] --> B[Semantic Search]
    A --> C[Graph Traversal]
    A --> D[Timeline Search]
    
    B --> E[Results Set 1]
    C --> F[Results Set 2]
    D --> G[Results Set 3]
    
    E --> H[Merge & Deduplicate]
    F --> H
    G --> H
    
    H --> I[Rerank by Relevance]
    I --> J[Final Results]
```

## 4. Background Processing Workflow

### Async Worker Architecture

```mermaid
graph TD
    A[Main Application] --> B[Task Queue]
    B --> C[Ingestion Worker]
    B --> D[Extraction Worker]
    B --> E[Indexing Worker]
    
    C --> F[Process Raw Data]
    D --> G[Extract Memories]
    E --> H[Update Indexes]
    
    F --> I[Update Status]
    G --> I
    H --> I
    
    I --> J[Notify UI]
```

### Resumable Processing

```mermaid
graph TD
    A[Worker Starts] --> B[Load Checkpoint]
    B --> C[Get Next Batch]
    C --> D[Process Items]
    D --> E[Save Checkpoint]
    E --> F{More Items?}
    F -->|Yes| C
    F -->|No| G[Complete]
    
    H[Worker Crash] --> I[Restart]
    I --> B
```

## 5. Memory Update Workflow

### Knowledge Graph Update

```mermaid
graph TD
    A[New Memory Created] --> B[Extract Entities]
    B --> C[Identify Relationships]
    C --> D[Load Existing Graph]
    D --> E[Add New Nodes]
    E --> F[Add New Edges]
    F --> G[Calculate Centrality]
    G --> H[Update Graph Metrics]
    H --> I[Save Graph]
    I --> J[Trigger Snapshot Refresh]
```

### Snapshot Generation

```mermaid
graph TD
    A[Trigger Event] --> B[Collect All Memories]
    B --> C[Group by Type]
    C --> D[Calculate Statistics]
    D --> E[Identify Key Decisions]
    E --> F[Map Ownership]
    F --> G[Build Timeline]
    G --> H[Generate Summary]
    H --> I[Save Snapshot]
    I --> J[Update UI Dashboard]
```

## 6. Deduplication Workflow

### Semantic Deduplication

```mermaid
graph TD
    A[New Memory] --> B[Generate Embedding]
    B --> C[Search Similar Memories]
    C --> D{Similarity > 0.9?}
    D -->|Yes| E[Check Source Refs]
    D -->|No| F[Accept as New]
    E --> G{Same Source?}
    G -->|Yes| H[Discard Duplicate]
    G -->|No| I[Merge Memories]
    I --> J[Update Confidence]
    J --> F
```

## 7. Confidence Scoring Workflow

### Multi-Factor Confidence

```mermaid
graph TD
    A[Extracted Memory] --> B[LLM Confidence Score]
    A --> C[Source Quality Score]
    A --> D[Evidence Strength Score]
    A --> E[Contributor Reputation]
    
    B --> F[Weighted Average]
    C --> F
    D --> F
    E --> F
    
    F --> G{Score > 0.7?}
    G -->|Yes| H[Accept]
    G -->|No| I[Reject]
```

## 8. Timeline Construction Workflow

```mermaid
graph TD
    A[All Memories] --> B[Extract Timestamps]
    B --> C[Sort Chronologically]
    C --> D[Group by Service/Component]
    D --> E[Identify Key Events]
    E --> F[Build Event Chains]
    F --> G[Calculate Durations]
    G --> H[Generate Timeline View]
```

## 9. Relationship Building Workflow

```mermaid
graph TD
    A[New Memory] --> B[Extract Entities]
    B --> C[Identify Mentions]
    C --> D[Find Related Memories]
    D --> E[Calculate Relationship Type]
    E --> F[Assign Confidence]
    F --> G{Confidence > 0.6?}
    G -->|Yes| H[Create Edge]
    G -->|No| I[Skip]
    H --> J[Update Graph]
```

## 10. Error Handling Workflow

### Graceful Degradation

```mermaid
graph TD
    A[Operation Fails] --> B{Retry Count < 3?}
    B -->|Yes| C[Wait with Backoff]
    C --> D[Retry Operation]
    D --> E{Success?}
    E -->|Yes| F[Continue]
    E -->|No| B
    B -->|No| G[Log Error]
    G --> H[Mark as Failed]
    H --> I[Notify User]
    I --> J[Continue with Next Item]
```

## Key Workflow Principles

### 1. Async-First
- All heavy operations are async
- User never waits for processing
- Background workers handle load

### 2. Resumable
- Checkpoints at each stage
- Can restart from failure point
- No data loss on crash

### 3. Incremental
- Process in batches
- Update incrementally
- No full reprocessing needed

### 4. Observable
- Status updates at each stage
- Progress tracking
- Error visibility

### 5. Idempotent
- Safe to retry operations
- Deduplication prevents duplicates
- Consistent state

## Workflow States

### Ingestion States
- `queued` - Waiting to be processed
- `processing` - Currently being ingested
- `completed` - Successfully ingested
- `failed` - Error occurred
- `skipped` - Duplicate detected

### Extraction States
- `pending` - Waiting for extraction
- `extracting` - LLM processing
- `validating` - Confidence check
- `accepted` - Passed validation
- `rejected` - Failed validation

### Memory States
- `draft` - Initial extraction
- `validated` - Confidence checked
- `indexed` - Added to vector store
- `graphed` - Added to knowledge graph
- `active` - Available for retrieval

## Performance Considerations

### Batch Processing
- Process 10 items per batch
- Parallel extraction agents
- Async I/O operations

### Caching
- Cache embeddings
- Cache graph queries
- Cache LLM responses (where appropriate)

### Optimization
- Lazy loading of large graphs
- Pagination for results
- Incremental indexing