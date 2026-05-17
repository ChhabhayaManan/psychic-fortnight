"""
Standalone indexing script.
Run this after stopping extraction to index all extracted artifacts
into the vector store (ChromaDB) and graph store so the UI and
query interface can use them.

Usage:
    python run_indexing.py
"""

import asyncio
import io
import sys
from pathlib import Path

# Force UTF-8 output on Windows to avoid cp1252 encoding errors
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent))

from app.config import get_settings
from app.memory.json_store import JsonStore
from app.memory.vector_store import VectorStore
from app.memory.graph_store import GraphStore
from app.workers.indexing_worker import IndexingWorker

OWNER = "IBM"
REPO  = "mcp-context-forge"


async def main():
    settings = get_settings()
    source_id = f"{OWNER}_{REPO}"
    paths = settings.get_project_paths(source_id)

    print(f"\n[INDEX] Loading artifacts from: {paths['extracted']}")
    json_store = JsonStore(paths["extracted"])
    counts = json_store.get_all_counts()
    total = sum(counts.values())
    print(f"[INDEX] Found {total} artifacts: {counts}")

    # Init stores
    try:
        vector_store = VectorStore(paths["chroma"])
        print(f"[INDEX] Vector store ready: {paths['chroma']}")
    except Exception as e:
        print(f"[INDEX] WARN VectorStore init failed: {e}")
        vector_store = None

    try:
        graph_store = GraphStore(paths["graph"])
        print(f"[INDEX] Graph store ready: {paths['graph']}")
    except Exception as e:
        print(f"[INDEX] WARN GraphStore init failed: {e}")
        graph_store = None

    worker = IndexingWorker(
        json_store=json_store,
        vector_store=vector_store,
        graph_store=graph_store,
    )

    print("\n[INDEX] >> Starting indexing...\n")
    result = await worker.index_all_artifacts()

    print(f"\n[INDEX] DONE!")
    print(f"  Total artifacts : {result['total_artifacts']}")
    print(f"  Vector indexed  : {result['vector_indexed']}")
    print(f"  Graph indexed   : {result['graph_indexed']}")
    print(f"  Vector failed   : {result['vector_failed']}")
    print(f"  Graph failed    : {result['graph_failed']}")

    if result["failures"]:
        print(f"\n[INDEX] WARN {len(result['failures'])} failures:")
        for f in result["failures"][:10]:
            print(f"  - {f['artifact_type']} / {f['artifact_id']} ({f['stage']}): {f['error']}")


if __name__ == "__main__":
    asyncio.run(main())
