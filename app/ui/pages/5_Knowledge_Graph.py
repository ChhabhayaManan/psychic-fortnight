"""
Knowledge Graph Page

Interactive visualization of relationships between artifacts, entities, and contributors.
Displays the NetworkX knowledge graph with filtering and exploration capabilities.
"""

import streamlit as st
from pathlib import Path
import sys
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.ui.utils.state import UIState
from app.ui.utils.api import BackendAPI


# Page configuration
st.set_page_config(
    page_title="Knowledge Graph - Engineering Memory System",
    page_icon="🕸️",
    layout="wide",
)

# Initialize session state
UIState.init_session_state()

# Initialize API
api = BackendAPI()


def render_graph_filters():
    """Render graph filter controls."""
    st.sidebar.header("🔍 Filters")
    
    # Node type filter
    st.sidebar.subheader("Node Types")
    node_types = st.sidebar.multiselect(
        "Show Nodes",
        options=["Decision", "Incident", "Timeline Event", "Architecture", "Service", "Contributor", "Source"],
        default=["Decision", "Service", "Contributor"]
    )
    
    # Relationship filter
    st.sidebar.subheader("Relationships")
    show_relationships = st.sidebar.multiselect(
        "Show Edges",
        options=["Related To", "Caused By", "Resolved By", "Contributed To", "Affects", "References"],
        default=["Related To", "Affects"]
    )
    
    # Depth filter
    st.sidebar.subheader("Graph Depth")
    max_depth = st.sidebar.slider(
        "Maximum Depth",
        min_value=1,
        max_value=5,
        value=2,
        help="Maximum number of hops from selected nodes"
    )
    
    # Layout options
    st.sidebar.subheader("Layout")
    layout = st.sidebar.selectbox(
        "Layout Algorithm",
        options=["Force-Directed", "Hierarchical", "Circular", "Radial"],
        index=0
    )
    
    return {
        'node_types': node_types,
        'show_relationships': show_relationships,
        'max_depth': max_depth,
        'layout': layout,
    }


def render_graph_stats(graph_data: dict):
    """
    Render graph statistics.
    
    Args:
        graph_data: Graph data dictionary
    """
    nodes = graph_data.get('nodes', [])
    edges = graph_data.get('links', [])
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Nodes", len(nodes))
    
    with col2:
        st.metric("Total Edges", len(edges))
    
    with col3:
        # Count node types
        node_types = set(n.get('type', 'Unknown') for n in nodes)
        st.metric("Node Types", len(node_types))
    
    with col4:
        # Calculate average degree
        if nodes:
            avg_degree = (2 * len(edges)) / len(nodes)
            st.metric("Avg Connections", f"{avg_degree:.1f}")


def render_node_details(node: dict):
    """
    Render detailed information for a selected node.
    
    Args:
        node: Node dictionary
    """
    st.subheader(f"📍 {node.get('label', 'Unknown Node')}")
    
    # Node type
    node_type = node.get('type', 'Unknown')
    st.markdown(f"**Type:** `{node_type}`")
    
    # Node ID
    st.markdown(f"**ID:** `{node.get('id', 'N/A')}`")
    
    # Metadata
    if 'metadata' in node:
        with st.expander("📊 Metadata"):
            st.json(node['metadata'])
    
    # Connections
    if 'connections' in node:
        st.markdown(f"**Connections:** {len(node['connections'])}")
        
        with st.expander("🔗 Connected Nodes"):
            for conn in node['connections'][:10]:
                st.markdown(f"- {conn.get('label', 'Unknown')} ({conn.get('type', 'Unknown')})")


def render_graph_visualization(graph_data: dict, filters: dict):
    """
    Render interactive graph visualization.
    
    Args:
        graph_data: Graph data dictionary
        filters: Filter settings
    """
    st.subheader("🕸️ Graph Visualization")
    
    # Filter nodes and edges based on filters
    filtered_nodes = [
        n for n in graph_data.get('nodes', [])
        if n.get('type') in filters['node_types']
    ]
    
    filtered_edges = [
        e for e in graph_data.get('links', [])
        if e.get('type') in filters['show_relationships']
    ]
    
    # Display filtered stats
    st.info(f"Showing {len(filtered_nodes)} nodes and {len(filtered_edges)} edges")
    
    # For now, display as JSON (would use a proper graph viz library in production)
    with st.expander("📄 Graph Data (JSON)"):
        st.json({
            'nodes': filtered_nodes[:20],  # Show first 20 nodes
            'edges': filtered_edges[:50],  # Show first 50 edges
        })
    
    # Note about visualization
    st.warning("""
    **Note:** Interactive graph visualization requires additional libraries like:
    - `streamlit-agraph` for force-directed graphs
    - `pyvis` for NetworkX visualization
    - `plotly` for custom graph layouts
    
    For now, explore nodes using the search and filter features below.
    """)


def render_node_search(graph_data: dict):
    """
    Render node search interface.
    
    Args:
        graph_data: Graph data dictionary
    """
    st.subheader("🔍 Search Nodes")
    
    nodes = graph_data.get('nodes', [])
    
    # Search input
    search_query = st.text_input(
        "Search by name or ID",
        placeholder="Enter node name or ID..."
    )
    
    if search_query:
        # Filter nodes by search query
        matching_nodes = [
            n for n in nodes
            if search_query.lower() in n.get('label', '').lower()
            or search_query.lower() in n.get('id', '').lower()
        ]
        
        if matching_nodes:
            st.success(f"Found {len(matching_nodes)} matching nodes")
            
            # Display matching nodes
            for node in matching_nodes[:10]:
                with st.expander(f"{node.get('label', 'Unknown')} ({node.get('type', 'Unknown')})"):
                    render_node_details(node)
        else:
            st.info("No matching nodes found")


def render_graph_explorer(graph_data: dict):
    """
    Render graph exploration interface.
    
    Args:
        graph_data: Graph data dictionary
    """
    st.subheader("🧭 Graph Explorer")
    
    nodes = graph_data.get('nodes', [])
    
    # Group nodes by type
    nodes_by_type = {}
    for node in nodes:
        node_type = node.get('type', 'Unknown')
        if node_type not in nodes_by_type:
            nodes_by_type[node_type] = []
        nodes_by_type[node_type].append(node)
    
    # Display nodes by type
    for node_type, type_nodes in nodes_by_type.items():
        with st.expander(f"{node_type} ({len(type_nodes)} nodes)"):
            # Show first 10 nodes of this type
            for node in type_nodes[:10]:
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"**{node.get('label', 'Unknown')}**")
                
                with col2:
                    if st.button("View", key=f"view_{node.get('id')}"):
                        st.session_state.selected_node = node
            
            if len(type_nodes) > 10:
                st.caption(f"... and {len(type_nodes) - 10} more")


def main():
    """Main knowledge graph page."""
    
    st.title("🕸️ Knowledge Graph")
    st.markdown("Explore relationships between artifacts, entities, and contributors.")
    st.markdown("---")
    
    # Check if graph data is available
    availability = UIState.check_data_availability()
    
    if not availability.get('graph'):
        st.warning("⚠️ Knowledge graph not available. Please run indexing first.")
        st.info("👉 Go to **Processing Dashboard** to start indexing")
        return
    
    # Load graph data
    with st.spinner("Loading knowledge graph..."):
        graph_data = api.get_graph_data()
    
    if not graph_data:
        st.error("❌ Failed to load graph data")
        return
    
    # Get filters
    filters = render_graph_filters()
    
    # Display graph statistics
    render_graph_stats(graph_data)
    
    st.markdown("---")
    
    # Main content area
    tab1, tab2, tab3 = st.tabs(["📊 Visualization", "🔍 Search", "🧭 Explorer"])
    
    with tab1:
        render_graph_visualization(graph_data, filters)
    
    with tab2:
        render_node_search(graph_data)
    
    with tab3:
        render_graph_explorer(graph_data)
    
    # Selected node details
    if 'selected_node' in st.session_state and st.session_state.selected_node:
        st.markdown("---")
        st.header("📍 Selected Node")
        render_node_details(st.session_state.selected_node)
        
        if st.button("Clear Selection"):
            st.session_state.selected_node = None
            st.rerun()
    
    # Export options
    st.markdown("---")
    st.subheader("📤 Export")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Export as JSON", use_container_width=True):
            st.download_button(
                "Download JSON",
                json.dumps(graph_data, indent=2),
                file_name="knowledge_graph.json",
                mime="application/json"
            )
    
    with col2:
        if st.button("Export Node List", use_container_width=True):
            nodes_csv = "ID,Label,Type\n"
            for node in graph_data.get('nodes', []):
                nodes_csv += f"{node.get('id', '')},{node.get('label', '')},{node.get('type', '')}\n"
            
            st.download_button(
                "Download CSV",
                nodes_csv,
                file_name="graph_nodes.csv",
                mime="text/csv"
            )
    
    with col3:
        if st.button("Export Edge List", use_container_width=True):
            edges_csv = "Source,Target,Type\n"
            for edge in graph_data.get('links', []):
                edges_csv += f"{edge.get('source', '')},{edge.get('target', '')},{edge.get('type', '')}\n"
            
            st.download_button(
                "Download CSV",
                edges_csv,
                file_name="graph_edges.csv",
                mime="text/csv"
            )


if __name__ == "__main__":
    main()

# Made with Bob
