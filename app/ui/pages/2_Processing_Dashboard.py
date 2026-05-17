"""Processing Dashboard — clean one-click pipeline UI."""

import asyncio
import threading
import time
import sys
from pathlib import Path
from typing import Optional

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.ui.utils.state import UIState, PipelineControl
from app.ui.utils.api import BackendAPI
from app.config import get_settings

st.set_page_config(
    page_title="Processing Dashboard",
    page_icon="📊",
    layout="wide",
)

# ── Session state defaults (must run before any access) ───────────────────────
if "pipeline_stage" not in st.session_state:
    st.session_state.pipeline_stage = "idle"
if "pipeline_error" not in st.session_state:
    st.session_state.pipeline_error = ""
if "stop_requested" not in st.session_state:
    st.session_state.stop_requested = False

UIState.init_session_state()
api = BackendAPI()
control = PipelineControl()
settings = get_settings()


# ─── Background pipeline ───────────────────────────────────────────────────────

def _wipe_state(source_id: str):
    """Wipe project-specific ingestion state and queue."""
    paths = settings.get_project_paths(source_id)
    base = paths["state"]
    for p in [
        base / "ingestion" / f"{source_id}.json",
        base / "processing_queue" / "queue.json",
    ]:
        if p.exists():
            p.unlink()
            print(f"[RESET] Deleted {p}")


def _run_pipeline(owner: str, repo: str, token: str, fresh: bool = False):
    """Full pipeline: ingest → extract → index. Runs in a daemon thread."""
    from app.ingestion.github.client import GitHubClient
    from app.memory.raw_storage import RawDataStorage
    from app.memory.json_store import JsonStore
    from app.models.ingestion_state import IngestionStateManager, ProcessingQueue
    from app.ingestion.github.workflow import GitHubIngestionWorkflow
    from app.workers.extraction_worker import ExtractionWorker
    from app.workers.indexing_worker import IndexingWorker
    from app.utils.rate_limiter import RateLimiter

    source_id = f"{owner}_{repo}"
    paths = settings.get_project_paths(source_id)

    if fresh:
        _wipe_state(source_id)
        print(f"[PIPELINE] Fresh start — state wiped for {source_id}")

    # ── Stage 1: Ingestion ────────────────────────────────────────────────────
    st.session_state.pipeline_stage = "ingesting"
    print(f"\n[PIPELINE] ▶ Stage 1 — Ingesting {owner}/{repo}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        rate_limiter = RateLimiter(max_requests=100, period=60)
        client = GitHubClient(token=token, rate_limiter=rate_limiter)
        storage = RawDataStorage(paths["raw"])
        state_manager = IngestionStateManager(paths["state"])
        processing_queue = ProcessingQueue(paths["state"])

        workflow = GitHubIngestionWorkflow(
            owner=owner,
            repo=repo,
            client=client,
            storage=storage,
            state_manager=state_manager,
            processing_queue=processing_queue,
            max_workers=5,
            skip_existing=True,
            stop_check=control.should_stop,
        )

        ingestion_state = loop.run_until_complete(workflow.run())

        if control.should_stop():
            print("[PIPELINE] 🛑 Stopped during ingestion")
            st.session_state.pipeline_stage = "idle"
            return

        print(f"[PIPELINE] ✓ Ingestion complete — "
              f"total={ingestion_state.total_count}  "
              f"stored={ingestion_state.stored_count}  "
              f"skipped={ingestion_state.skipped_count}  "
              f"failed={ingestion_state.failed_count}")

        # ── Stage 2: Extraction ───────────────────────────────────────────────
        st.session_state.pipeline_stage = "extracting"
        print(f"\n[PIPELINE] ▶ Stage 2 — Extracting artifacts")

        json_store = JsonStore(paths["extracted"])
        extraction_worker = ExtractionWorker(
            json_store=json_store,
            processing_queue=processing_queue,
            max_workers=3,
            stop_check=control.should_stop,
        )
        extraction_stats = loop.run_until_complete(extraction_worker.process_all())

        if control.should_stop():
            print("[PIPELINE] 🛑 Stopped during extraction")
            st.session_state.pipeline_stage = "idle"
            return

        print(f"[PIPELINE] ✓ Extraction complete — "
              f"processed={extraction_stats.get('processed', 0)}  "
              f"artifacts={extraction_stats.get('artifacts_created', 0)}")

        # ── Stage 3: Indexing ─────────────────────────────────────────────────
        st.session_state.pipeline_stage = "indexing"
        print(f"\n[PIPELINE] ▶ Stage 3 — Indexing")

        try:
            from app.memory.vector_store import VectorStore
            from app.memory.graph_store import GraphStore
            vector_store = VectorStore(paths["chroma"])
            graph_store = GraphStore(paths["graph"])
        except Exception as e:
            print(f"[PIPELINE] ⚠ Store init failed: {e} — skipping indexing")
            vector_store = None
            graph_store = None

        indexing_worker = IndexingWorker(
            json_store=json_store,
            vector_store=vector_store,
            graph_store=graph_store,
            stop_check=control.should_stop,
        )
        indexing_stats = loop.run_until_complete(indexing_worker.index_all_artifacts())

        print(f"[PIPELINE] ✓ Indexing complete — "
              f"total={indexing_stats.get('total_artifacts', 0)}  "
              f"vector={indexing_stats.get('vector_indexed', 0)}")

        st.session_state.pipeline_stage = "done"
        print(f"\n[PIPELINE] ✅ All done for {owner}/{repo}\n")

    except Exception as e:
        st.session_state.pipeline_stage = "error"
        st.session_state.pipeline_error = str(e)
        print(f"\n[PIPELINE] ❌ Pipeline error: {e}\n")
        import traceback; traceback.print_exc()
    finally:
        loop.close()
        control.reset_stop()


# ─── Page ─────────────────────────────────────────────────────────────────────

def main():
    st.title("📊 Processing Dashboard")

    config = UIState.load_config()
    if not config.get("repo_owner") or not config.get("repo_name"):
        st.warning("⚠️ No repository configured — go to **Setup** first.")
        return

    source_id = f"{config['repo_owner']}_{config['repo_name']}"
    repo_label = f"{config['repo_owner']}/{config['repo_name']}"
    stage = st.session_state.pipeline_stage
    running = stage in ("ingesting", "extracting", "indexing")

    # ── Status banner ──────────────────────────────────────────────────────────
    STATUS = {
        "idle":       ("ℹ️ Ready to start.", "info"),
        "ingesting":  ("🔄 Stage 1/3 — Ingesting from GitHub…", "info"),
        "extracting": ("🔄 Stage 2/3 — Extracting knowledge artifacts…", "info"),
        "indexing":   ("🔄 Stage 3/3 — Indexing to ChromaDB & Knowledge Graph…", "info"),
        "done":       ("✅ Pipeline complete!", "success"),
        "error":      ("❌ Pipeline error.", "error"),
    }
    msg, kind = STATUS.get(stage, ("", "info"))
    getattr(st, kind)(msg)
    if stage == "error" and st.session_state.get("pipeline_error"):
        st.code(st.session_state.pipeline_error, language="text")

    # ── Stage progress bar ─────────────────────────────────────────────────────
    if stage != "idle":
        stage_map = {"ingesting": 1, "extracting": 2, "indexing": 3, "done": 4, "error": 0}
        c1, c2, c3, c4 = st.columns(4)
        idx = stage_map.get(stage, 0)
        for i, (col, label) in enumerate(zip(
            [c1, c2, c3, c4],
            ["1 — Ingest", "2 — Extract", "3 — Index", "✅ Done"]
        ), start=1):
            with col:
                if stage == "done" or i < idx:
                    st.success(f"✅ {label}")
                elif i == idx:
                    st.info(f"🔄 {label}")
                else:
                    st.markdown(f"⚪ {label}")

    st.markdown("---")

    # ── Controls ───────────────────────────────────────────────────────────────
    col_start, col_stop, col_fresh = st.columns([3, 2, 2])

    with col_start:
        if not running:
            if not config.get("github_token"):
                st.error("❌ GitHub token not configured — go to Setup first.")
            else:
                btn_label = "🚀 Start Workflow" if stage in ("idle", "error") else "🔄 Re-run Workflow"
                if st.button(btn_label, type="primary", use_container_width=True):
                    control.reset_stop()
                    st.session_state.pipeline_stage = "ingesting"
                    st.session_state.pipeline_error = ""
                    threading.Thread(
                        target=_run_pipeline,
                        args=(config["repo_owner"], config["repo_name"], config["github_token"], False),
                        daemon=True,
                    ).start()
                    st.rerun()
        else:
            st.button("⏳ Running…", disabled=True, use_container_width=True)

    with col_stop:
        if running:
            if st.button("🛑 Stop Workflow", type="secondary", use_container_width=True):
                control.request_stop()
                st.warning("Stop requested — finishing current item…")
        else:
            if stage in ("done", "error") and st.button("🗑 Reset", use_container_width=True):
                st.session_state.pipeline_stage = "idle"
                st.session_state.pipeline_error = ""
                st.rerun()

    with col_fresh:
        if not running and config.get("github_token"):
            if st.button("🗑️ Fresh Start", use_container_width=True,
                         help="Wipe cached state and re-fetch everything from GitHub"):
                _wipe_state(source_id)
                control.reset_stop()
                st.session_state.pipeline_stage = "ingesting"
                st.session_state.pipeline_error = ""
                threading.Thread(
                    target=_run_pipeline,
                    args=(config["repo_owner"], config["repo_name"], config["github_token"], True),
                    daemon=True,
                ).start()
                st.rerun()

    # ── Auto-refresh ───────────────────────────────────────────────────────────
    if running:
        ar_col, _ = st.columns([1, 3])
        with ar_col:
            auto_refresh = st.checkbox("Auto-refresh (3s)", value=True)
        if auto_refresh:
            time.sleep(3)
            st.rerun()

    st.markdown("---")

    # ── Ingestion Status ───────────────────────────────────────────────────────
    st.subheader("📥 Ingestion Status")
    status = api.get_ingestion_status(source_id)

    if status:
        discovered = status.get("discovered_count", 0) or 0
        stored = status.get("stored_count", 0) or 0
        skipped = status.get("skipped_count", 0) or 0
        failed = status.get("failed_count", 0) or 0
        ing_status = status.get("status", "—").upper()

        # Show DISCOVERING if stage is ingesting but totals still zero
        if ing_status in ("", "NONE", "—") and stage == "ingesting":
            ing_status = "DISCOVERING…"

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Status", ing_status)
        m2.metric("Discovered", f"{discovered:,}")
        m3.metric("Stored", f"{stored:,}")
        m4.metric("Skipped", f"{skipped:,}")
        m5.metric("Failed", f"{failed:,}")

        # Progress bar — treat discovered as total; if not known use stored+queued
        total_known = discovered if discovered > 0 else (stored + status.get("queued_count", 0))
        if total_known > 0:
            pct = min((stored + skipped) / total_known, 1.0)
            st.progress(pct, text=f"{int(pct*100)}% — {stored+skipped:,}/{total_known:,} processed")
        else:
            st.progress(0.0, text="Waiting for discovery…")
    else:
        st.info(f"ℹ️ No ingestion data yet for **{repo_label}**. Press **Start Workflow** above.")

    st.markdown("---")

    # ── Extraction Queue ───────────────────────────────────────────────────────
    st.subheader("📋 Extraction Queue")
    try:
        from app.models.ingestion_state import ProcessingQueue
        paths = settings.get_project_paths(source_id)
        pq = ProcessingQueue(paths["state"])
        q_active = pq.size()
        q_dead = pq.dead_letter_size()

        qc1, qc2, qc3 = st.columns(3)
        qc1.metric("Queued (pending)", f"{q_active:,}")
        qc2.metric("Dead-letter (failed)", f"{q_dead:,}")
        qc3.metric("Stage", stage.capitalize())
    except Exception as e:
        st.warning(f"Could not read queue: {e}")

    st.markdown("---")

    # ── Extraction Status ──────────────────────────────────────────────────────
    st.subheader("🔍 Extraction Status")
    stats = api.get_extraction_stats(source_id)
    total_artifacts = sum(stats.values())

    e1, e2, e3 = st.columns(3)
    e1.metric("Decisions", stats.get("decisions", 0))
    e1.metric("Incidents", stats.get("incidents", 0))
    e2.metric("Timeline Events", stats.get("timeline", 0))
    e2.metric("Architecture", stats.get("architecture", 0))
    e3.metric("Ownership", stats.get("ownership", 0))
    e3.metric("Unresolved Q's", stats.get("unresolved", 0))

    st.metric("Total Artifacts", total_artifacts)

    if total_artifacts > 0:
        with st.expander("📈 Artifact distribution"):
            import pandas as pd
            df = pd.DataFrame(
                [{"Type": k.title(), "Count": v} for k, v in stats.items() if v > 0]
            )
            if not df.empty:
                st.bar_chart(df.set_index("Type"))

    st.markdown("---")

    # ── Indexing Status ────────────────────────────────────────────────────────
    st.subheader("🗄️ Index Status")
    try:
        from app.memory.json_store import JsonStore
        paths = settings.get_project_paths(source_id)
        js = JsonStore(paths["extracted"])
        idx_stats = js.get_stats()

        i1, i2 = st.columns(2)
        i1.metric("Artifacts on disk", idx_stats.get("total", 0))
        i2.metric("Artifact types", idx_stats.get("type_count", 0))
    except Exception:
        st.info("Indexing stats unavailable until indexing has run.")


main()
