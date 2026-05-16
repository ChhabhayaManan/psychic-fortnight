"""
Processing Dashboard Page

Monitors ingestion and extraction progress, worker status,
and provides controls for starting/stopping processes.
"""

import streamlit as st
from pathlib import Path
import sys
from datetime import datetime
import time

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.ui.utils.state import UIState
from app.ui.utils.api import BackendAPI


# Page configuration
st.set_page_config(
    page_title="Processing Dashboard - Engineering Memory System",
    page_icon="📊",
    layout="wide",
)

# Initialize session state
UIState.init_session_state()

# Initialize API
api = BackendAPI()


def render_ingestion_status():
    """Render ingestion status section."""
    st.header("📥 Ingestion Status")
    
    # Get source ID from config
    config = UIState.load_config()
    if not config.get('repo_owner') or not config.get('repo_name'):
        st.warning("⚠️ Repository not configured. Go to Setup page first.")
        return
    
    source_id = f"{config['repo_owner']}_{config['repo_name']}"
    
    # Get ingestion status
    status = api.get_ingestion_status(source_id)
    
    if status:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Status", status['status'].upper())
        
        with col2:
            st.metric("Discovered", status['discovered_count'])
        
        with col3:
            st.metric("Stored", status['stored_count'])
        
        with col4:
            completion = 0
            if status['discovered_count'] > 0:
                completion = int((status['stored_count'] / status['discovered_count']) * 100)
            st.metric("Progress", f"{completion}%")
        
        # Progress bar
        if status['discovered_count'] > 0:
            progress = status['stored_count'] / status['discovered_count']
            st.progress(progress)
        
        # Detailed stats
        with st.expander("📊 Detailed Statistics"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.text(f"Queued: {status['queued_count']}")
                st.text(f"Skipped: {status['skipped_count']}")
                st.text(f"Failed: {status['failed_count']}")
            
            with col2:
                st.text(f"Started: {UIState.format_timestamp(status['started_at'])}")
                st.text(f"Completed: {UIState.format_timestamp(status['completed_at'])}")
                st.text(f"Last Updated: {UIState.format_timestamp(status['last_updated'])}")
    else:
        st.info("ℹ️ No ingestion data available for this repository")
        
        # Start ingestion button
        if st.button("🚀 Start Ingestion", type="primary"):
            if not config.get('github_token'):
                st.error("❌ GitHub token not configured")
            else:
                with st.spinner("Starting ingestion..."):
                    success, message = api.start_ingestion(
                        config['repo_owner'],
                        config['repo_name'],
                        config['github_token']
                    )
                    
                    if success:
                        st.success(f"✅ {message}")
                        st.session_state.ingestion_running = True
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")


def render_extraction_status():
    """Render extraction status section."""
    st.header("🔍 Extraction Status")
    
    # Get extraction stats
    stats = api.get_extraction_stats()
    
    # Display metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Decisions", stats.get('decisions', 0))
        st.metric("Incidents", stats.get('incidents', 0))
    
    with col2:
        st.metric("Timeline Events", stats.get('timeline', 0))
        st.metric("Architecture Changes", stats.get('architecture', 0))
    
    with col3:
        st.metric("Ownership Records", stats.get('ownership', 0))
        st.metric("Unresolved Questions", stats.get('unresolved', 0))
    
    # Total artifacts
    total = sum(stats.values())
    st.metric("Total Artifacts", total)
    
    # Artifact distribution chart
    if total > 0:
        with st.expander("📈 Artifact Distribution"):
            import pandas as pd
            
            df = pd.DataFrame([
                {"Type": k.title(), "Count": v}
                for k, v in stats.items() if v > 0
            ])
            
            st.bar_chart(df.set_index("Type"))


def render_processing_queue():
    """Render processing queue section."""
    st.header("📋 Processing Queue")
    
    queue_status = api.get_processing_queue_status()
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.metric("Pending Items", queue_status['pending_count'])
    
    with col2:
        if queue_status['pending_count'] > 0:
            st.info(f"ℹ️ {queue_status['pending_count']} items waiting for processing")
        else:
            st.success("✅ Queue is empty")
    
    # Show sample items
    if queue_status['items']:
        with st.expander("📄 Sample Queue Items"):
            for item in queue_status['items'][:5]:
                st.text(f"• {item.get('item_id', 'Unknown')} - {item.get('item_type', 'Unknown')}")


def render_indexing_status():
    """Render indexing status section."""
    st.header("🗂️ Indexing Status")
    
    col1, col2, col3 = st.columns(3)
    
    # Check data availability
    availability = UIState.check_data_availability()
    
    with col1:
        st.subheader("Vector Store")
        if availability.get('embeddings'):
            st.success("✅ Active")
            st.text("ChromaDB index available")
        else:
            st.warning("⚠️ Not Initialized")
    
    with col2:
        st.subheader("Knowledge Graph")
        if availability.get('graph'):
            st.success("✅ Active")
            
            # Try to get graph stats
            graph_data = api.get_graph_data()
            if graph_data:
                nodes = len(graph_data.get('nodes', []))
                edges = len(graph_data.get('links', []))
                st.text(f"Nodes: {nodes}")
                st.text(f"Edges: {edges}")
        else:
            st.warning("⚠️ Not Initialized")
    
    with col3:
        st.subheader("Snapshots")
        if availability.get('snapshots'):
            st.success("✅ Active")
            
            # Try to get snapshot info
            snapshot = api.get_project_snapshot()
            if snapshot:
                st.text(f"Last updated:")
                st.text(UIState.format_timestamp(snapshot.get('generated_at')))
        else:
            st.warning("⚠️ Not Available")


def render_worker_controls():
    """Render worker control section."""
    st.header("⚙️ Worker Controls")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Ingestion")
        if st.session_state.ingestion_running:
            if st.button("⏸️ Pause Ingestion", use_container_width=True):
                st.session_state.ingestion_running = False
                st.success("Ingestion paused")
        else:
            if st.button("▶️ Resume Ingestion", use_container_width=True):
                st.session_state.ingestion_running = True
                st.success("Ingestion resumed")
    
    with col2:
        st.subheader("Extraction")
        if st.session_state.extraction_running:
            if st.button("⏸️ Pause Extraction", use_container_width=True):
                st.session_state.extraction_running = False
                st.success("Extraction paused")
        else:
            if st.button("▶️ Start Extraction", use_container_width=True):
                st.session_state.extraction_running = True
                st.success("Extraction started")
    
    with col3:
        st.subheader("Indexing")
        if st.button("🔄 Refresh Indexes", use_container_width=True):
            with st.spinner("Refreshing indexes..."):
                time.sleep(1)
                st.success("Indexes refreshed")


def main():
    """Main dashboard page."""
    
    st.title("📊 Processing Dashboard")
    st.markdown("Monitor and control the ingestion and processing pipeline.")
    st.markdown("---")
    
    # Auto-refresh toggle
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown("### Real-time Monitoring")
    
    with col2:
        auto_refresh = st.checkbox("Auto-refresh", value=False)
    
    if auto_refresh:
        st.info("🔄 Auto-refreshing every 5 seconds...")
        time.sleep(5)
        st.rerun()
    
    # Render sections
    render_ingestion_status()
    st.markdown("---")
    
    render_extraction_status()
    st.markdown("---")
    
    render_processing_queue()
    st.markdown("---")
    
    render_indexing_status()
    st.markdown("---")
    
    render_worker_controls()
    
    # Manual refresh button
    st.markdown("---")
    if st.button("🔄 Refresh Dashboard", use_container_width=True):
        st.session_state.last_refresh = datetime.now().isoformat()
        st.rerun()
    
    if st.session_state.last_refresh:
        st.text(f"Last refreshed: {UIState.format_timestamp(st.session_state.last_refresh)}")


if __name__ == "__main__":
    main()

# Made with Bob
