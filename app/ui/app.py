"""
Streamlit UI for the Agentic Engineering Memory System.

This is the main UI interface for interacting with the memory system.
"""

import streamlit as st

from app.config import get_settings
from app.utils import get_logger

# Page configuration
st.set_page_config(
    page_title="Engineering Memory System",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize
logger = get_logger(__name__)
settings = get_settings()


def main():
    """Main UI application."""

    # Header
    st.title("🧠 Agentic Engineering Memory System")
    st.markdown("""
    An autonomous system that extracts, connects, and retrieves architectural decisions,
    incidents, timelines, and organizational knowledge from software development workflows.
    """)

    # Sidebar
    with st.sidebar:
        st.header("Navigation")
        page = st.radio(
            "Select Page",
            ["Dashboard", "Sources", "Search", "Timeline", "Settings"],
            label_visibility="collapsed"
        )

    # Main content based on selected page
    if page == "Dashboard":
        show_dashboard()
    elif page == "Sources":
        show_sources()
    elif page == "Search":
        show_search()
    elif page == "Timeline":
        show_timeline()
    elif page == "Settings":
        show_settings()


def show_dashboard():
    """Show dashboard page."""
    st.header("📊 Dashboard")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Connected Sources", "0")
    with col2:
        st.metric("Decisions Extracted", "0")
    with col3:
        st.metric("Incidents Tracked", "0")
    with col4:
        st.metric("Processing Status", "Idle")

    st.divider()

    st.subheader("Recent Activity")
    st.info("No activity yet. Connect a source to start autonomous processing.")


def show_sources():
    """Show sources management page."""
    st.header("🔗 Knowledge Sources")

    st.markdown("""
    Connect knowledge sources to enable autonomous processing. Once connected,
    the system will automatically discover and process all data in the background.
    """)

    st.subheader("Add New Source")

    source_type = st.selectbox(
        "Source Type",
        ["GitHub Repository", "GitLab Repository", "Jira Project"]
    )

    if source_type == "GitHub Repository":
        col1, col2 = st.columns(2)
        with col1:
            owner = st.text_input("Repository Owner")
        with col2:
            repo = st.text_input("Repository Name")

        if st.button("Connect Repository", type="primary"):
            if owner and repo:
                st.success(f"Repository {owner}/{repo} will be connected (implementation pending)")
            else:
                st.error("Please provide both owner and repository name")

    st.divider()

    st.subheader("Connected Sources")
    st.info("No sources connected yet.")


def show_search():
    """Show search page."""
    st.header("🔍 Search Memory")

    query = st.text_input(
        "Search for decisions, incidents, or knowledge",
        placeholder="e.g., Why did we switch to microservices?"
    )

    if query:
        st.info("Search functionality will be implemented in the next phase.")


def show_timeline():
    """Show timeline page."""
    st.header("📅 Engineering Timeline")

    st.markdown("""
    View the evolution of your engineering decisions and architecture over time.
    """)

    st.info("Timeline visualization will be implemented in the next phase.")


def show_settings():
    """Show settings page."""
    st.header("⚙️ Settings")

    st.subheader("Processing Configuration")

    col1, col2 = st.columns(2)

    with col1:
        st.number_input("Max Workers", value=settings.max_workers, min_value=1, max_value=20)
        st.number_input("Batch Size", value=settings.batch_size, min_value=1, max_value=100)

    with col2:
        st.number_input("Rate Limit (req/min)", value=settings.rate_limit_requests, min_value=1)
        st.number_input("Checkpoint Interval", value=settings.checkpoint_interval, min_value=10)

    st.divider()

    st.subheader("Confidence Thresholds")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.slider("Decision Confidence", 0.0, 1.0, settings.min_decision_confidence)
    with col2:
        st.slider("Incident Confidence", 0.0, 1.0, settings.min_incident_confidence)
    with col3:
        st.slider("Relationship Confidence", 0.0, 1.0, settings.min_relationship_confidence)

    if st.button("Save Settings"):
        st.success("Settings saved (implementation pending)")


if __name__ == "__main__":
    main()

# Made with Bob
