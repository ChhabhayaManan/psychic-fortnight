"""
Engineering Memory System - Streamlit UI

Main entrypoint for the Streamlit application.
Provides navigation and overview of the system.
"""

import streamlit as st
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.ui.utils.state import UIState
from app.ui.utils.api import BackendAPI


# Page configuration
st.set_page_config(
    page_title="Engineering Memory System",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize session state
UIState.init_session_state()

# Initialize API
api = BackendAPI()


def main():
    """Main application entry point."""
    
    # Header
    st.title("🧠 Engineering Memory System")
    st.markdown("---")
    
    # Welcome message
    st.markdown("""
    Welcome to the **Engineering Memory System** - an intelligent platform for capturing,
    processing, and querying engineering knowledge from your GitHub repositories.
    
    ### What This System Does
    
    - **Ingests** pull requests and issues from GitHub repositories
    - **Extracts** engineering decisions, incidents, timeline events, and more
    - **Indexes** knowledge into vector embeddings and knowledge graphs
    - **Answers** natural language queries about your engineering history
    - **Visualizes** relationships, timelines, and decision patterns
    """)
    
    st.markdown("---")
    
    # System status overview
    st.header("📊 System Status")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # Check data availability
    availability = UIState.check_data_availability()
    
    with col1:
        st.metric(
            label="Raw Data",
            value="✅ Available" if availability.get('raw') else "❌ Not Available",
        )
    
    with col2:
        st.metric(
            label="Extracted Artifacts",
            value="✅ Available" if availability.get('extracted') else "❌ Not Available",
        )
    
    with col3:
        st.metric(
            label="Vector Index",
            value="✅ Available" if availability.get('embeddings') else "❌ Not Available",
        )
    
    with col4:
        st.metric(
            label="Knowledge Graph",
            value="✅ Available" if availability.get('graph') else "❌ Not Available",
        )
    
    # Configuration status
    st.markdown("---")
    st.header("⚙️ Configuration")
    
    config = UIState.load_config()
    config_complete = all([
        config.get('github_token'),
        config.get('repo_owner'),
        config.get('repo_name'),
    ])
    
    if config_complete:
        st.success("✅ System is configured")
        st.info(f"**Repository:** {config['repo_owner']}/{config['repo_name']}")
    else:
        st.warning("⚠️ System configuration incomplete")
        st.info("👉 Go to **Setup** page to configure the system")
    
    # Quick stats
    if availability.get('extracted'):
        st.markdown("---")
        st.header("📈 Quick Stats")
        
        stats = api.get_extraction_stats()
        
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
    
    # Navigation guide
    st.markdown("---")
    st.header("🧭 Navigation Guide")
    
    st.markdown("""
    Use the sidebar to navigate between different pages:
    
    1. **Setup** - Configure GitHub credentials and repository
    2. **Processing Dashboard** - Monitor ingestion and extraction progress
    3. **Query Interface** - Ask questions about your engineering history
    4. **Timeline View** - Explore events chronologically
    5. **Knowledge Graph** - Visualize relationships between artifacts
    6. **Decision Explorer** - Browse and filter engineering decisions
    """)
    
    # Getting started
    if not config_complete:
        st.markdown("---")
        st.header("🚀 Getting Started")
        
        st.markdown("""
        To get started with the Engineering Memory System:
        
        1. Go to the **Setup** page
        2. Enter your GitHub Personal Access Token
        3. Specify the repository owner and name
        4. Save the configuration
        5. Start the ingestion process from the **Processing Dashboard**
        6. Once processing completes, explore your engineering memory!
        """)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: gray; padding: 20px;'>
        <p>Engineering Memory System v1.0</p>
        <p>Built with Streamlit, LangGraph, ChromaDB, and NetworkX</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()

# Made with Bob
