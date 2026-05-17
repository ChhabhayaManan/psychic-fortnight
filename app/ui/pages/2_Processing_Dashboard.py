"""
Processing Dashboard Page

Monitors ingestion, extraction and indexing progress.
One-click automatic pipeline: ingest → extract → index.
"""

import streamlit as st
from pathlib import Path
import sys
from datetime import datetime
import time
import threading
import asyncio
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.ui.utils.state import UIState, PipelineControl
from app.ui.utils.api import BackendAPI

# Page configuration
st.set_page_config(
    page_title="Processing Dashboard - Engineering Memory System",
    page_icon="📊",
    layout="wide",
)

# Initialize session state
UIState.init_session_state()

# Initialize API and Control
api = BackendAPI()
control = PipelineControl()


# ─── helpers ──────────────────────────────────────────────────────────────────

def _stage_icon(stage: str) -> str:
    icons = {
        'idle': '⚪',
        'ingesting': '🔄',
        'extracting': '🔄',
        'indexing': '🔄',
        'done': '✅',
        'error': '❌',
    }
    return icons.get(stage, '⚪')


def _get_source_id(config: dict) -> str:
    return f"{config['repo_owner']}_{config['repo_name']}"


def _wipe_ingestion_state(source_id: str):
    """Delete the persisted ingestion state and queue so the pipeline starts fresh."""
    import shutil
    state_base = Path('data/state')
    state_file = state_base / 'ingestion' / f'{source_id}.json'
    queue_file = state_base / 'processing_queue' / 'queue.json'
    if state_file.exists():
        state_file.unlink()
        print(f"[RESET] Deleted state file: {state_file}")
    if queue_file.exists():
        queue_file.unlink()
        print(f"[RESET] Cleared processing queue")


def _run_stage_ingestion(owner: str, repo: str, token: str, fresh_start: bool = False, auto_next: bool = False, fetch_limit: Optional[int] = None):
    """Run Stage 1: Ingestion."""
    from app.ingestion.github.client import GitHubClient
    from app.memory.raw_storage import RawDataStorage
    from app.models.ingestion_state import IngestionStateManager, ProcessingQueue
    from app.ingestion.github.workflow import GitHubIngestionWorkflow
    from app.utils.rate_limiter import RateLimiter
    from app.ui.utils.state import UIState, PipelineControl

    control = PipelineControl()
    data_path = Path('data')
    config = UIState.load_config()
    verify_ssl = config.get('verify_ssl', True)
    pr_limit = config.get('pr_limit')
    issue_limit = config.get('issue_limit')

    control.set_stage('ingesting')
    control.reset_stop()
    print(f"\n[PIPELINE] ▶ STAGE 1 — Ingestion: {owner}/{repo} (fresh_start={fresh_start}, fetch_limit={fetch_limit})")

    if fresh_start:
        source_id = f"{owner}_{repo}"
        _wipe_ingestion_state(source_id)
        print(f"[PIPELINE] ♻ State wiped — will re-fetch all items from GitHub")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # Increase rate limit for discovery if needed, or use high-volume settings
        rate_limit_requests = config.get('rate_limit_requests', 100)
        rate_limit_period = config.get('rate_limit_period', 60)
        
        rate_limiter = RateLimiter(max_requests=rate_limit_requests, period=rate_limit_period)
        client = GitHubClient(token=token, rate_limiter=rate_limiter, verify_ssl=verify_ssl)
        storage = RawDataStorage(data_path / 'raw')
        state_manager = IngestionStateManager(data_path / 'state')
        processing_queue = ProcessingQueue(data_path / 'state')

        workflow = GitHubIngestionWorkflow(
            owner=owner,
            repo=repo,
            client=client,
            storage=storage,
            state_manager=state_manager,
            processing_queue=processing_queue,
            max_workers=3,
            stop_check=control.should_stop,
            pr_limit=pr_limit,
            issue_limit=issue_limit
        )

        ingestion_state = loop.run_until_complete(workflow.run(fetch_limit=fetch_limit))
        
        if control.should_stop():
            print("[PIPELINE] 🛑 Ingestion stopped by user")
            control.set_stage('idle')
            return False
        else:
            print(f"[PIPELINE] ✓ Ingestion complete — "
                  f"total={ingestion_state.total_count}  "
                  f"stored={ingestion_state.stored_count}  "
                  f"skipped={ingestion_state.skipped_count}  "
                  f"failed={ingestion_state.failed_count}")
            
            return True
            
    except Exception as e:
        control.set_error(str(e))
        print(f"\n[PIPELINE] ❌ Ingestion failed: {e}\n")
        return False
    finally:
        loop.close()


def _run_stage_extraction(auto_next: bool = False, batch_size: int = 100):
    """Run Stage 2: Extraction."""
    from app.memory.json_store import JsonStore
    from app.models.ingestion_state import ProcessingQueue
    from app.workers.extraction_worker import ExtractionWorker
    from app.ui.utils.state import PipelineControl

    control = PipelineControl()
    data_path = Path('data')
    control.set_stage('extracting')
    print(f"\n[PIPELINE] ▶ STAGE 2 — Extraction (batch={batch_size})")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        json_store = JsonStore(data_path / 'extracted')
        processing_queue = ProcessingQueue(data_path / 'state')
        extraction_worker = ExtractionWorker(
            json_store=json_store,
            processing_queue=processing_queue,
            max_workers=3,
            stop_check=control.should_stop
        )
        # Only process a batch to keep the loop tight
        extraction_stats = loop.run_until_complete(extraction_worker.process_queue(batch_size=batch_size))
        
        if control.should_stop():
            print("[PIPELINE] 🛑 Extraction stopped by user")
            control.set_stage('idle')
            return False
        else:
            print(f"[PIPELINE] ✓ Extraction batch complete — "
                  f"processed={extraction_stats.get('processed', 0)}  "
                  f"artifacts={extraction_stats.get('artifacts_created', 0)}  "
                  f"failed={extraction_stats.get('failed', 0)}")

            return True

    except Exception as e:
        control.set_error(str(e))
        print(f"\n[PIPELINE] ❌ Extraction failed: {e}\n")
        return False
    finally:
        loop.close()


def _run_stage_indexing():
    """Run Stage 3: Indexing."""
    from app.memory.json_store import JsonStore
    from app.workers.indexing_worker import IndexingWorker
    from app.ui.utils.state import PipelineControl

    control = PipelineControl()
    data_path = Path('data')
    control.set_stage('indexing')
    print(f"\n[PIPELINE] ▶ STAGE 3 — Indexing")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        json_store = JsonStore(data_path / 'extracted')
        try:
            from app.memory.vector_store import VectorStore
            from app.memory.graph_store import GraphStore
            vector_store = VectorStore(data_path / 'embeddings' / 'chroma')
            graph_store = GraphStore(data_path / 'graph')
        except Exception as e:
            print(f"[PIPELINE] ⚠ Could not init vector/graph store: {e} — skipping indexing")
            vector_store = None
            graph_store = None

        indexing_worker = IndexingWorker(
            json_store=json_store,
            vector_store=vector_store,
            graph_store=graph_store,
            stop_check=control.should_stop
        )
        indexing_stats = loop.run_until_complete(indexing_worker.index_all_artifacts())
        
        if control.should_stop():
            print("[PIPELINE] 🛑 Indexing stopped by user")
            control.set_stage('idle')
        else:
            print(f"[PIPELINE] ✓ Indexing complete — "
                  f"total={indexing_stats.get('total_artifacts', 0)}  "
                  f"vector={indexing_stats.get('vector_indexed', 0)}  "
                  f"graph={indexing_stats.get('graph_indexed', 0)}")

    except Exception as e:
        control.set_error(str(e))
        print(f"\n[PIPELINE] ❌ Indexing failed: {e}\n")
    finally:
        loop.close()


def _run_full_pipeline(owner: str, repo: str, token: str, fresh_start: bool = False, continuous: bool = False):
    """Run ingestion → extraction → indexing sequentially, optionally in a loop."""
    from app.ui.utils.state import PipelineControl
    control = PipelineControl()
    
    batch_size = 100
    
    while True:
        # 1. Ingest a chunk of 100
        success = _run_stage_ingestion(owner, repo, token, fresh_start, auto_next=True, fetch_limit=batch_size)
        fresh_start = False # Only wipe on first iteration if requested
        if not success or control.should_stop():
            break

        # 2. Extract those 100
        success = _run_stage_extraction(auto_next=True, batch_size=batch_size)
        if not success or control.should_stop():
            break

        # 3. Index everything found so far
        _run_stage_indexing()
        
        # If not continuous, stop after one chunk
        if not continuous:
            break
            
        print("\n[PIPELINE] 🔁 Continuous mode — starting next chunk...")
    
    if control.get_stage() != 'error' and not control.should_stop():
        control.set_stage('done')


# ─── page render ──────────────────────────────────────────────────────────────

def main():
    """Main dashboard page."""

    st.title("📊 Processing Dashboard")
    st.markdown("Automatically ingest, extract, and index your GitHub repository data.")
    st.markdown("---")

    # ── Config check ───────────────────────────────────────────────────────────
    config = UIState.load_config()
    if not config.get('repo_owner') or not config.get('repo_name'):
        st.warning("⚠️ Repository not configured. Go to the **Setup** page first.")
        return

    source_id = _get_source_id(config)
    repo_label = f"{config['repo_owner']}/{config['repo_name']}"

    # ── Pipeline status banner ─────────────────────────────────────────────────
    stage = control.get_stage()
    status_map = {
        'idle':      ('ℹ️ Ready', 'info'),
        'ingesting': ('🔄 Stage 1 / 3 — Ingesting Data from GitHub…', 'info'),
        'extracting':('🔄 Stage 2 / 3 — Extracting knowledge artifacts…', 'info'),
        'indexing':  ('🔄 Stage 3 / 3 — Indexing to ChromaDB & Knowledge Graph…', 'info'),
        'done':      ('✅ Pipeline complete! All data has been processed.', 'success'),
        'error':     ('❌ Pipeline encountered an error.', 'error'),
    }
    msg, kind = status_map.get(stage, ('', 'info'))
    getattr(st, kind)(msg)
    if stage == 'error':
        error_msg = control.get_error()
        if error_msg:
            st.code(error_msg, language='text')

    # ── Pipeline progress steps ────────────────────────────────────────────────
    stages_order = ['ingesting', 'extracting', 'indexing', 'done']
    labels = ['1 — Ingest GitHub Data', '2 — Extract Artifacts', '3 — Index Knowledge', '✅ Done']

    if stage != 'idle':
        cols = st.columns(4)
        stage_idx = stages_order.index(stage) if stage in stages_order else -1
        for i, (col, label) in enumerate(zip(cols, labels)):
            with col:
                if i < stage_idx or stage == 'done':
                    st.success(f"✅ {label}")
                elif i == stage_idx and stage != 'done':
                    st.info(f"🔄 {label}")
                else:
                    st.markdown(f"⚪ {label}")

    st.markdown("---")

    # ── Controls ──────────────────────────────────────────────────────────────
    col_btn, col_cont, col_stop = st.columns([2, 2, 1])

    with col_btn:
        can_start = stage in ('idle', 'done', 'error')
        if can_start:
            if not config.get('github_token'):
                st.error("❌ GitHub token missing")
            else:
                if st.button("🚀 Process Next 100 Items", type="primary", use_container_width=True):
                    control.set_stage('ingesting')
                    control.reset_stop()
                    t = threading.Thread(
                        target=_run_full_pipeline,
                        args=(config['repo_owner'], config['repo_name'], config['github_token'], False, False),
                        daemon=True
                    )
                    t.start()
                    st.rerun()
        else:
            st.button("⏳ Pipeline Running…", disabled=True, use_container_width=True)

    with col_cont:
        if can_start:
            if st.button("♻️ Continuous Mode (Chunked)", use_container_width=True):
                control.set_stage('ingesting')
                control.reset_stop()
                t = threading.Thread(
                    target=_run_full_pipeline,
                    args=(config['repo_owner'], config['repo_name'], config['github_token'], False, True),
                    daemon=True
                )
                t.start()
                st.rerun()
        else:
            st.button("🔄 Continuous Processing...", disabled=True, use_container_width=True)

    with col_stop:
        if stage in ('ingesting', 'extracting', 'indexing'):
            if st.button("🛑 Stop", type="secondary", use_container_width=True):
                control.request_stop()
                st.warning("Stopping...")
        else:
            if st.button("🗑️ Reset All", use_container_width=True):
                _wipe_ingestion_state(source_id)
                st.rerun()

    # ── Stage Control (Individual Steps) ──────────────────────────────────────
    with st.expander("🛠 Advanced Stage Control"):
        st.markdown("Run individual stages of the pipeline for debugging or partial updates.")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("1️⃣ Run Ingestion Only", disabled=not can_start, use_container_width=True):
                control.set_stage('ingesting')
                t = threading.Thread(
                    target=_run_stage_ingestion,
                    args=(config['repo_owner'], config['repo_name'], config['github_token'], False, False),
                    daemon=True
                )
                t.start()
                st.rerun()
        with c2:
            if st.button("2️⃣ Run Extraction Only", disabled=not can_start, use_container_width=True):
                control.set_stage('extracting')
                t = threading.Thread(target=_run_stage_extraction, args=(False,), daemon=True)
                t.start()
                st.rerun()
        with c3:
            if st.button("3️⃣ Run Indexing Only", disabled=not can_start, use_container_width=True):
                control.set_stage('indexing')
                t = threading.Thread(target=_run_stage_indexing, daemon=True)
                t.start()
                st.rerun()

    # Auto-refresh while running
    if stage in ('ingesting', 'extracting', 'indexing'):
        st.caption("🔄 Auto-refreshing every 3 seconds…")
        time.sleep(3)
        st.rerun()

    st.markdown("---")

    # ── Ingestion stats ────────────────────────────────────────────────────────
    st.header("📥 Ingestion Status")
    status = api.get_ingestion_status(source_id)

    if status:
        c1, c2, c3, c4 = st.columns(4)
        
        # Display Discovery progress if total_count is 0 but stage is ingesting
        display_status = status['status'].upper()
        if display_status == "NOT STARTED" and stage == "ingesting":
            display_status = "DISCOVERING..."
            
        c1.metric("Status", display_status)
        c2.metric("Discovered", status['discovered_count'])
        c3.metric("Stored", status['stored_count'])

        disc = status['discovered_count'] or 1
        pct = int(status['stored_count'] / disc * 100)
        c4.metric("Progress", f"{pct}%")

        st.progress(min(status['stored_count'] / disc, 1.0))

        with st.expander("📊 Detailed Stats"):
            d1, d2 = st.columns(2)
            with d1:
                st.text(f"Queued:  {status['queued_count']}")
                st.text(f"Skipped: {status['skipped_count']}")
                st.text(f"Failed:  {status['failed_count']}")
            with d2:
                st.text(f"Started:      {UIState.format_timestamp(status['started_at'])}")
                st.text(f"Last updated: {UIState.format_timestamp(status['last_updated'])}")
    else:
        st.info(f"ℹ️ No ingestion data yet for **{repo_label}**. Press **Start Full Pipeline** above.")

    st.markdown("---")

    # ── Extraction stats ───────────────────────────────────────────────────────
    st.header("🔍 Extraction Status")
    stats = api.get_extraction_stats()
    total = sum(stats.values())

    c1, c2, c3 = st.columns(3)
    c1.metric("Decisions", stats.get('decisions', 0))
    c1.metric("Incidents", stats.get('incidents', 0))
    c2.metric("Timeline Events", stats.get('timeline', 0))
    c2.metric("Architecture", stats.get('architecture', 0))
    c3.metric("Ownership", stats.get('ownership', 0))
    c3.metric("Unresolved", stats.get('unresolved', 0))

    st.metric("Total Artifacts", total)

    if total > 0:
        with st.expander("📈 Distribution"):
            import pandas as pd
            df = pd.DataFrame([{"Type": k.title(), "Count": v} for k, v in stats.items() if v > 0])
            if not df.empty:
                st.bar_chart(df.set_index("Type"))

    st.markdown("---")

    # ── Processing queue ───────────────────────────────────────────────────────
    st.header("📋 Processing Queue")
    q = api.get_processing_queue_status()
    qc1, qc2 = st.columns([1, 3])
    qc1.metric("Pending Items", q['pending_count'])
    with qc2:
        if q['pending_count'] > 0:
            st.info(f"ℹ️ {q['pending_count']} item(s) awaiting extraction")
        else:
            st.success("✅ Queue is empty")

    if q.get('items'):
        with st.expander("📄 Queue Preview"):
            for item in q['items'][:5]:
                st.text(f"• {item.get('item_type','?').upper()} #{item.get('item_number','?')} — {item.get('source_id','?')}")

    st.markdown("---")

    # ── Indexing status ────────────────────────────────────────────────────────
    st.header("🗂️ Index Status")
    avail = UIState.check_data_availability()
    ic1, ic2 = st.columns(2)

    with ic1:
        st.subheader("Vector Store (ChromaDB)")
        if avail.get('embeddings'):
            st.success("✅ Active")
            st.caption("Semantic search ready")
        else:
            st.warning("⚠️ Not yet built")

    with ic2:
        st.subheader("Knowledge Graph")
        if avail.get('graph'):
            st.success("✅ Active")
            graph_data = api.get_graph_data()
            if graph_data:
                st.caption(f"Nodes: {len(graph_data.get('nodes', []))}  |  Edges: {len(graph_data.get('links', []))}")
        else:
            st.warning("⚠️ Not yet built")

    # ── Manual refresh ─────────────────────────────────────────────────────────
    st.markdown("---")
    if st.button("🔄 Refresh Page", use_container_width=True):
        st.session_state.last_refresh = datetime.now().isoformat()
        st.rerun()

    if st.session_state.get('last_refresh'):
        st.caption(f"Last refreshed: {UIState.format_timestamp(st.session_state.last_refresh)}")


if __name__ == "__main__":
    main()

# Made with Bob
