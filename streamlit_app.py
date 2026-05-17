"""
Engineering Memory Knowledge — Streamlit entry point.
Used for Streamlit Cloud deployment and local execution.
"""

import asyncio
import json
import sys
import threading
import time
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from app.config import get_settings
from app.memory.json_store import JsonStore
from app.models.ingestion_state import ProcessingQueue
from app.ui.utils.api import BackendAPI
from app.ui.utils.state import PipelineControl, UIState

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Engineering Memory Knowledge",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Session state ─────────────────────────────────────────────────────────────
UIState.init_session_state()
for key, default in [
    ("chat_history", []),
    ("pipeline_stage", "idle"),
    ("pending_query", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

settings = get_settings()
api      = BackendAPI()
control  = PipelineControl()

config     = UIState.load_config()
source_id  = f"{config.get('repo_owner', '')}_{config.get('repo_name', '')}"
repo_label = f"{config.get('repo_owner', '?')}/{config.get('repo_name', '?')}"

if source_id and source_id != "_":
    api.set_project(source_id)
    paths = settings.get_project_paths(source_id)
else:
    paths = None


# ── Pipeline runner (background thread) ──────────────────────────────────────
def _run_pipeline(owner, repo, token):
    from app.ingestion.github.client import GitHubClient
    from app.ingestion.github.workflow import GitHubIngestionWorkflow
    from app.memory.raw_storage import RawDataStorage
    from app.models.ingestion_state import IngestionStateManager, ProcessingQueue
    from app.utils.rate_limiter import RateLimiter
    from app.workers.extraction_worker import ExtractionWorker

    src  = f"{owner}_{repo}"
    p    = settings.get_project_paths(src)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        st.session_state.pipeline_stage = "ingesting"
        client  = GitHubClient(token=token, rate_limiter=RateLimiter(100, 60))
        storage = RawDataStorage(p["raw"])
        sm      = IngestionStateManager(p["state"])
        pq      = ProcessingQueue(p["state"])
        wf = GitHubIngestionWorkflow(
            owner=owner, repo=repo, client=client, storage=storage,
            state_manager=sm, processing_queue=pq,
            max_workers=10, skip_existing=True, stop_check=control.should_stop,
        )
        loop.run_until_complete(wf.run())
        if control.should_stop():
            st.session_state.pipeline_stage = "idle"
            return

        st.session_state.pipeline_stage = "extracting"
        js = JsonStore(p["extracted"])
        ew = ExtractionWorker(
            json_store=js, processing_queue=pq,
            max_workers=3, stop_check=control.should_stop,
        )
        loop.run_until_complete(ew.process_all())
        st.session_state.pipeline_stage = "done"
    except Exception as e:
        st.session_state.pipeline_stage = "error"
        print(f"[PIPELINE] error: {e}")
    finally:
        loop.close()
        control.reset_stop()


# ── Header ────────────────────────────────────────────────────────────────────
st.title("🧠 Engineering Memory Knowledge")
st.caption(f"Repository: **{repo_label}**")
st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_query, tab_dash, tab_timeline, tab_graph, tab_decisions = st.tabs([
    "💬 Query", "📊 Pipeline", "🕐 Timeline", "🕸 Knowledge Graph", "⚖️ Decisions"
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — QUERY
# ══════════════════════════════════════════════════════════════════════════════
with tab_query:
    st.subheader("Ask anything about the repository")

    examples = [
        "What major architectural decisions were made?",
        "Summarise the key incidents",
        "Who owns the core components?",
        "What unresolved questions exist?",
    ]
    cols = st.columns(len(examples))
    for col, ex in zip(cols, examples):
        if col.button(ex, use_container_width=True, key=f"ex_{ex[:20]}"):
            st.session_state.pending_query = ex
            st.rerun()

    st.divider()

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("sources"):
                with st.expander("Sources"):
                    for s in msg["sources"]:
                        label = s if isinstance(s, str) else s.get("url", str(s))
                        st.markdown(f"- {label}")

    typed_query  = st.chat_input("Ask anything about the codebase…")
    active_query = typed_query or st.session_state.pop("pending_query", None)

    if active_query:
        st.session_state.chat_history.append({"role": "user", "content": active_query})
        with st.chat_message("user"):
            st.markdown(active_query)

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                try:
                    resp = api.query_memory(active_query)
                except Exception as e:
                    resp = {"answer": f"Error: {e}", "sources": [], "confidence": 0.0}

            answer  = resp.get("answer") or "No answer generated."
            sources = resp.get("sources", [])
            conf    = resp.get("confidence", 0.0)

            st.markdown(answer)
            if conf:
                st.caption(f"Confidence: {conf:.0%}")
            if sources:
                with st.expander("Sources"):
                    for s in sources:
                        label = s if isinstance(s, str) else s.get("url", str(s))
                        st.markdown(f"- {label}")

        st.session_state.chat_history.append({
            "role": "assistant",
            "content": answer,
            "sources": sources,
        })

    if st.session_state.chat_history:
        if st.button("Clear conversation", key="clear_chat"):
            st.session_state.chat_history = []
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — PIPELINE DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
with tab_dash:
    stage   = st.session_state.pipeline_stage
    running = stage in ("ingesting", "extracting")

    STATUS = {
        "idle":       ("Ready — click Start Pipeline to begin.", "info"),
        "ingesting":  ("Stage 1/2 — Ingesting from GitHub…", "info"),
        "extracting": ("Stage 2/2 — Extracting knowledge artifacts…", "info"),
        "done":       ("Pipeline complete!", "success"),
        "error":      ("Pipeline error — check logs.", "error"),
    }
    msg, kind = STATUS.get(stage, ("", "info"))
    getattr(st, kind)(msg)

    c1, c2, c3 = st.columns([3, 2, 2])
    with c1:
        token = config.get("github_token", "")
        owner = config.get("repo_owner", "")
        repo  = config.get("repo_name", "")
        if not running:
            if st.button("Start Pipeline", type="primary", use_container_width=True,
                         disabled=not (token and owner and repo)):
                control.reset_stop()
                st.session_state.pipeline_stage = "ingesting"
                threading.Thread(
                    target=_run_pipeline, args=(owner, repo, token), daemon=True,
                ).start()
                st.rerun()
        else:
            st.button("Running…", disabled=True, use_container_width=True)
    with c2:
        if running and st.button("Stop", type="secondary", use_container_width=True):
            control.request_stop()
            st.warning("Stop requested…")
    with c3:
        if stage in ("done", "error") and st.button("Reset", use_container_width=True):
            st.session_state.pipeline_stage = "idle"
            st.rerun()

    st.divider()
    st.subheader("Extracted Artifacts")
    if paths:
        js     = JsonStore(paths["extracted"])
        counts = js.get_all_counts()
        total  = sum(counts.values())
        mcols  = st.columns(len(counts))
        for col, (k, v) in zip(mcols, counts.items()):
            col.metric(k.title(), v)
        st.metric("Total", total)
    else:
        st.info("No project configured.")

    st.divider()
    st.subheader("Extraction Queue")
    if paths:
        try:
            pq = ProcessingQueue(paths["state"])
            q1, q2 = st.columns(2)
            q1.metric("Queued",      pq.size())
            q2.metric("Dead-letter", pq.dead_letter_size())
        except Exception as e:
            st.warning(f"Could not read queue: {e}")

    if running:
        time.sleep(3)
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — TIMELINE
# ══════════════════════════════════════════════════════════════════════════════
with tab_timeline:
    st.subheader("Engineering Timeline")

    if not paths:
        st.info("No project configured.")
    else:
        js  = JsonStore(paths["extracted"])
        ids = js.list_artifacts("timeline")

        if not ids:
            st.info("No timeline events extracted yet.")
        else:
            search = st.text_input("Filter timeline", placeholder="Type to search…", key="tl_search")
            events = []
            for eid in ids:
                ev = js.get_artifact("timeline", eid)
                if not ev:
                    continue
                title   = getattr(ev, "title", None) or str(eid)
                summary = getattr(ev, "summary", None) or ""
                ts      = getattr(ev, "timestamp", None)
                etype   = getattr(ev, "event_type", None) or ""
                if search and search.lower() not in f"{title} {summary} {etype}".lower():
                    continue
                events.append((ts, title, summary, etype, ev))

            events.sort(key=lambda x: str(x[0] or ""))

            for ts, title, summary, etype, ev in events:
                ts_str = str(ts)[:10] if ts else "Unknown date"
                with st.expander(f"**{ts_str}** — {title}" + (f"  `{etype}`" if etype else "")):
                    if summary:
                        st.markdown(summary)
                    entities = getattr(ev, "related_entities", []) or []
                    if entities:
                        st.markdown("**Entities:** " + ", ".join(f"`{e}`" for e in entities))

            st.caption(f"{len(events)} events shown")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — KNOWLEDGE GRAPH
# ══════════════════════════════════════════════════════════════════════════════
with tab_graph:
    st.subheader("Knowledge Graph")

    if not paths:
        st.info("No project configured.")
    else:
        graph_file = paths["graph"] / "knowledge_graph.json"
        if not graph_file.exists():
            st.info("Knowledge graph not yet built. Run indexing first.")
        else:
            with open(graph_file, "r", encoding="utf-8") as f:
                gdata = json.load(f)

            nodes = gdata.get("nodes", [])
            edges = gdata.get("edges", [])

            g1, g2 = st.columns(2)
            g1.metric("Nodes", len(nodes))
            g2.metric("Edges", len(edges))

            st.divider()

            if nodes:
                from collections import Counter
                type_counts = Counter(
                    n.get("type", n.get("artifact_type", "unknown")) for n in nodes
                )
                st.markdown("**Node types:**")
                tc_cols = st.columns(min(len(type_counts), 4))
                for col, (t, c) in zip(tc_cols, type_counts.most_common()):
                    col.metric(t.title(), c)

            st.divider()

            search_g = st.text_input("Search nodes", placeholder="Name or type…", key="graph_search")
            shown = 0
            for node in nodes:
                label = node.get("label") or node.get("id") or str(node)
                ntype = node.get("type") or node.get("artifact_type") or ""
                if search_g and search_g.lower() not in f"{label} {ntype}".lower():
                    continue
                with st.expander(f"**{label}** `{ntype}`"):
                    nid = node.get("id")
                    connected = [
                        e for e in edges
                        if e.get("source") == nid or e.get("target") == nid
                    ]
                    if connected:
                        st.markdown(f"**Connections ({len(connected)}):**")
                        for e in connected[:10]:
                            src = e.get("source", "")
                            tgt = e.get("target", "")
                            rel = e.get("relation") or e.get("type") or "→"
                            other = tgt if src == nid else src
                            st.markdown(f"- `{rel}` → `{other}`")
                    else:
                        st.markdown("_No connections_")
                shown += 1
                if shown >= 50:
                    st.info(f"Showing 50/{len(nodes)} nodes. Use search to narrow down.")
                    break


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — DECISIONS
# ══════════════════════════════════════════════════════════════════════════════
with tab_decisions:
    st.subheader("Engineering Decisions")

    if not paths:
        st.info("No project configured.")
    else:
        js   = JsonStore(paths["extracted"])
        dids = js.list_artifacts("decisions")

        if not dids:
            st.info("No decisions extracted yet.")
        else:
            search_d = st.text_input("Filter decisions", placeholder="Type to search…", key="dec_search")
            shown = 0
            for did in dids:
                d = js.get_artifact("decisions", did)
                if not d:
                    continue
                title      = getattr(d, "title", None) or str(did)
                summary    = getattr(d, "summary", None) or ""
                rationale  = getattr(d, "rationale", None) or ""
                confidence = getattr(d, "confidence", None)
                tags       = getattr(d, "tags", []) or []

                if search_d and search_d.lower() not in f"{title} {summary} {rationale}".lower():
                    continue

                conf_badge = f"  ·  {confidence:.0%}" if confidence else ""
                with st.expander(f"**{title}**{conf_badge}"):
                    if summary:
                        st.markdown(f"**Summary:** {summary}")
                    if rationale:
                        st.markdown(f"**Rationale:** {rationale}")
                    if tags:
                        st.markdown("**Tags:** " + ", ".join(f"`{t}`" for t in tags))

                shown += 1
                if shown >= 50:
                    st.info(f"Showing 50/{len(dids)} decisions. Use search to narrow down.")
                    break

            st.caption(f"{shown} decisions shown")
