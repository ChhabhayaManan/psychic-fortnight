"""
Engineering Memory Knowledge — Streamlit UI
Fixed target: IBM/mcp-context-forge

Run locally:
  C:\\Users\\Manan\\AppData\\Roaming\\Python\\Python313\\Scripts\\streamlit.exe run app.py

GitHub token and repo are read from Streamlit secrets / environment — never asked from the user.
User only provides WatsonX credentials (API key, project ID, URL).
"""

import asyncio
import json
import os
import sys
import threading
import time
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

# ── Fixed constants ────────────────────────────────────────────────────────────
REPO_OWNER = "IBM"
REPO_NAME  = "mcp-context-forge"
SOURCE_ID  = f"{REPO_OWNER}_{REPO_NAME}"
WATSONX_DEFAULT_URL = "https://us-south.ml.cloud.ibm.com"
WATSONX_DEFAULT_MODEL = "meta-llama/llama-3-3-70b-instruct"

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="Engineering Memory Knowledge",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Bootstrap secrets into os.environ (Streamlit Cloud secrets) ───────────────
def _load_secrets():
    """Push Streamlit secrets into os.environ so pydantic-settings picks them up."""
    try:
        for k, v in st.secrets.items():
            if isinstance(v, str):
                os.environ.setdefault(k, v)
    except Exception:
        pass  # Running locally without secrets file — fine

_load_secrets()

# ── Session-state defaults ────────────────────────────────────────────────────
_SS_DEFAULTS = {
    "chat_history": [],
    "pipeline_stage": "idle",
    "pending_query": None,
    "wx_configured": False,
}
for _k, _v in _SS_DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ── WatsonX credential helpers ────────────────────────────────────────────────
def _inject_watsonx(api_key: str, project_id: str, url: str, model: str):
    """Inject WatsonX creds into os.environ and reload settings so LLM works."""
    os.environ["WATSONX_API_KEY"]    = api_key
    os.environ["WATSONX_PROJECT_ID"] = project_id
    os.environ["WATSONX_URL"]        = url
    os.environ["LLM_API_KEY"]        = api_key
    os.environ["LLM_PROVIDER"]       = "Watsonx"
    os.environ["LLM_MODEL"]          = model
    os.environ["REPO_OWNER"]         = REPO_OWNER
    os.environ["REPO_NAME"]          = REPO_NAME
    # Reload settings so the LLM config picks up the new values
    from app.config.settings import reload_settings
    reload_settings()
    # Reset cached LLM instance so it's re-created with new creds
    try:
        from app.config.llm_config import get_llm_config
        get_llm_config().reset()
    except Exception:
        pass


def _watsonx_ready() -> bool:
    return bool(
        os.environ.get("WATSONX_API_KEY")
        and os.environ.get("WATSONX_PROJECT_ID")
    )


# ── GitHub token (from secrets / env only — not from user) ───────────────────
def _github_token() -> str:
    return (
        os.environ.get("GITHUB_TOKEN")
        or os.environ.get("github_token")
        or ""
    )


# ── Lazy imports (after sys.path is set) ─────────────────────────────────────
from app.config import get_settings
from app.memory.json_store import JsonStore
from app.models.ingestion_state import ProcessingQueue
from app.ui.utils.api import BackendAPI
from app.ui.utils.state import PipelineControl, UIState

settings = get_settings()
api      = BackendAPI()
control  = PipelineControl()

api.set_project(SOURCE_ID)
paths = settings.get_project_paths(SOURCE_ID)


# ── Sidebar — WatsonX setup ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ WatsonX Setup")
    st.caption("Your IBM watsonx.ai credentials")

    # Pre-fill from env/secrets if already set
    _default_key   = os.environ.get("WATSONX_API_KEY", "")
    _default_pid   = os.environ.get("WATSONX_PROJECT_ID", "")
    _default_url   = os.environ.get("WATSONX_URL", WATSONX_DEFAULT_URL)
    _default_model = os.environ.get("LLM_MODEL", WATSONX_DEFAULT_MODEL)

    wx_key   = st.text_input("API Key",    value=_default_key,   type="password", key="wx_key_input")
    wx_pid   = st.text_input("Project ID", value=_default_pid,   key="wx_pid_input")
    wx_url   = st.text_input("URL",        value=_default_url,   key="wx_url_input")
    wx_model = st.text_input("Model ID",   value=_default_model, key="wx_model_input",
                             help="e.g. meta-llama/llama-3-3-70b-instruct")

    if st.button("Apply credentials", type="primary", use_container_width=True):
        if wx_key and wx_pid:
            _inject_watsonx(wx_key.strip(), wx_pid.strip(),
                            wx_url.strip() or WATSONX_DEFAULT_URL,
                            wx_model.strip() or WATSONX_DEFAULT_MODEL)
            st.session_state.wx_configured = True
            st.success("✅ Credentials applied")
        else:
            st.error("API Key and Project ID are required.")

    st.divider()

    if _watsonx_ready():
        st.success("✅ WatsonX ready")
    else:
        st.warning("⚠️ Enter credentials above to enable query answering")

    st.divider()
    st.caption(f"📦 Repo: **{REPO_OWNER}/{REPO_NAME}**")
    github_ok = bool(_github_token())
    if github_ok:
        st.success("✅ GitHub token loaded")
    else:
        st.warning("⚠️ No GitHub token found in secrets")


# ── Header ────────────────────────────────────────────────────────────────────
st.title("🧠 Engineering Memory Knowledge")
st.caption(f"Repository: **{REPO_OWNER}/{REPO_NAME}**")
st.divider()


# ── Pipeline runner (background thread) ──────────────────────────────────────
def _run_pipeline():
    from app.ingestion.github.client import GitHubClient
    from app.ingestion.github.workflow import GitHubIngestionWorkflow
    from app.memory.raw_storage import RawDataStorage
    from app.models.ingestion_state import IngestionStateManager, ProcessingQueue
    from app.utils.rate_limiter import RateLimiter
    from app.workers.extraction_worker import ExtractionWorker

    token = _github_token()
    p     = settings.get_project_paths(SOURCE_ID)
    loop  = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        st.session_state.pipeline_stage = "ingesting"
        client  = GitHubClient(token=token, rate_limiter=RateLimiter(100, 60))
        storage = RawDataStorage(p["raw"])
        sm      = IngestionStateManager(p["state"])
        pq      = ProcessingQueue(p["state"])
        wf = GitHubIngestionWorkflow(
            owner=REPO_OWNER, repo=REPO_NAME,
            client=client, storage=storage,
            state_manager=sm, processing_queue=pq,
            max_workers=10, skip_existing=True,
            stop_check=control.should_stop,
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


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_query, tab_dash, tab_timeline, tab_graph, tab_decisions = st.tabs([
    "💬 Query", "📊 Pipeline", "🕐 Timeline", "🕸 Knowledge Graph", "⚖️ Decisions"
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — QUERY
# ══════════════════════════════════════════════════════════════════════════════
with tab_query:
    st.subheader("Ask anything about the repository")

    if not _watsonx_ready():
        st.warning("⚠️ Enter your WatsonX credentials in the sidebar to enable AI-powered answers.")

    # Example query buttons
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

    # Render chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("sources"):
                with st.expander("Sources"):
                    for s in msg["sources"]:
                        label = s if isinstance(s, str) else s.get("url", str(s))
                        st.markdown(f"- {label}")

    # Resolve query (typed or from example button)
    typed_query  = st.chat_input("Ask anything about IBM/mcp-context-forge…")
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
            "role": "assistant", "content": answer, "sources": sources,
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
        token_ok = bool(_github_token())
        if not running:
            btn = st.button("Start Pipeline", type="primary", use_container_width=True,
                            disabled=not token_ok)
            if not token_ok:
                st.caption("⚠️ No GitHub token found in secrets")
            if btn:
                control.reset_stop()
                st.session_state.pipeline_stage = "ingesting"
                threading.Thread(target=_run_pipeline, daemon=True).start()
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
    js     = JsonStore(paths["extracted"])
    counts = js.get_all_counts()
    total  = sum(counts.values())
    mcols  = st.columns(len(counts))
    for col, (k, v) in zip(mcols, counts.items()):
        col.metric(k.title(), v)
    st.metric("Total", total)

    st.divider()
    st.subheader("Extraction Queue")
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
            nid = node.get("id")
            connected = [e for e in edges if e.get("source") == nid or e.get("target") == nid]
            with st.expander(f"**{label}** `{ntype}`"):
                if connected:
                    st.markdown(f"**Connections ({len(connected)}):**")
                    for e in connected[:10]:
                        rel   = e.get("relation") or e.get("type") or "→"
                        other = e.get("target") if e.get("source") == nid else e.get("source")
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
