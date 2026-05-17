"""
Decision Explorer Page

Dedicated view for browsing and filtering extracted engineering decisions.
Provides search, filtering, and detailed views of decision artifacts.
"""

import streamlit as st
from pathlib import Path
import sys
from datetime import datetime
import pandas as pd

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.ui.utils.state import UIState
from app.ui.utils.api import BackendAPI


# Page configuration
st.set_page_config(
    page_title="Decision Explorer - Engineering Memory System",
    page_icon="🎯",
    layout="wide",
)

# Initialize session state
UIState.init_session_state()

# Initialize API
api = BackendAPI()


def render_decision_filters():
    """Render decision filter controls."""
    st.sidebar.header("🔍 Filters")
    
    # Confidence filter
    st.sidebar.subheader("Confidence Score")
    min_confidence = st.sidebar.slider(
        "Minimum Confidence",
        min_value=0.0,
        max_value=1.0,
        value=0.0,
        step=0.1,
        help="Filter decisions by minimum confidence score"
    )
    
    # Service filter
    st.sidebar.subheader("Related Services")
    services = st.sidebar.multiselect(
        "Services",
        options=["Authentication", "Payment", "API", "Database", "Frontend", "Backend", "Infrastructure"],
        default=[],
        help="Filter by related services"
    )
    
    # Tag filter
    st.sidebar.subheader("Tags")
    tags = st.sidebar.multiselect(
        "Tags",
        options=["Architecture", "Performance", "Security", "Scalability", "Technical Debt", "API Design"],
        default=[],
        help="Filter by decision tags"
    )
    
    # Contributor filter
    st.sidebar.subheader("Contributors")
    contributors = st.sidebar.multiselect(
        "Contributors",
        options=[],  # Would be populated from actual data
        default=[],
        help="Filter by contributors involved"
    )
    
    # Sort options
    st.sidebar.subheader("Sort By")
    sort_by = st.sidebar.selectbox(
        "Sort Field",
        options=["Confidence (High to Low)", "Confidence (Low to High)", "Date (Newest)", "Date (Oldest)", "Title (A-Z)"],
        index=0
    )
    
    return {
        'min_confidence': min_confidence,
        'services': services,
        'tags': tags,
        'contributors': contributors,
        'sort_by': sort_by,
    }


def render_decision_card(decision: dict):
    """
    Render a decision as a card.
    
    Args:
        decision: Decision dictionary
    """
    with st.container():
        # Header with title and confidence
        col1, col2 = st.columns([4, 1])
        
        with col1:
            title = decision.get('title', 'Untitled Decision')
            st.markdown(f"### {title}")
        
        with col2:
            confidence = decision.get('confidence', 0)
            color = "green" if confidence >= 0.7 else "orange" if confidence >= 0.5 else "red"
            st.markdown(f"<div style='text-align: right; color: {color}; font-weight: bold;'>{confidence:.0%}</div>", unsafe_allow_html=True)
        
        # Summary
        summary = decision.get('summary', '')
        if summary:
            st.markdown(summary)
        
        # Metadata row
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if 'contributors' in decision and decision['contributors']:
                st.caption(f"👤 {', '.join(decision['contributors'][:3])}")
        
        with col2:
            if 'related_services' in decision and decision['related_services']:
                st.caption(f"🔧 {', '.join(decision['related_services'][:3])}")
        
        with col3:
            if 'tags' in decision and decision['tags']:
                st.caption(f"🏷️ {', '.join(decision['tags'][:3])}")
        
        # Expandable details
        with st.expander("📄 Full Details"):
            # Reasoning
            if 'reasoning' in decision:
                st.markdown("**Reasoning:**")
                st.markdown(decision['reasoning'])
            
            # Description
            if 'description' in decision:
                st.markdown("**Description:**")
                st.markdown(decision['description'])
            
            # Alternatives considered
            if 'alternatives' in decision and decision['alternatives']:
                st.markdown("**Alternatives Considered:**")
                for alt in decision['alternatives']:
                    st.markdown(f"- {alt}")
            
            # Consequences
            if 'consequences' in decision and decision['consequences']:
                st.markdown("**Consequences:**")
                for cons in decision['consequences']:
                    st.markdown(f"- {cons}")
            
            # Source references
            if 'source_references' in decision:
                st.markdown("**Sources:**")
                for ref in decision['source_references']:
                    st.markdown(f"- [{ref.get('type', 'Unknown')} #{ref.get('number', '?')}]({ref.get('url', '#')})")
            
            # All tags
            if 'tags' in decision and decision['tags']:
                st.markdown("**All Tags:**")
                st.markdown(", ".join(f"`{tag}`" for tag in decision['tags']))
            
            # Metadata
            if 'extracted_at' in decision:
                st.caption(f"Extracted: {UIState.format_timestamp(decision['extracted_at'])}")
        
        st.markdown("---")


def render_decision_table(decisions: list):
    """
    Render decisions as a table.
    
    Args:
        decisions: List of decision dictionaries
    """
    table_data = []
    
    for decision in decisions:
        table_data.append({
            'Title': decision.get('title', 'Untitled'),
            'Confidence': f"{decision.get('confidence', 0):.0%}",
            'Services': ', '.join(decision.get('related_services', [])[:2]),
            'Tags': ', '.join(decision.get('tags', [])[:2]),
            'Contributors': ', '.join(decision.get('contributors', [])[:2]),
        })
    
    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_decision_stats(decisions: list):
    """
    Render decision statistics.
    
    Args:
        decisions: List of decision dictionaries
    """
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Decisions", len(decisions))
    
    with col2:
        if decisions:
            avg_confidence = sum(d.get('confidence', 0) for d in decisions) / len(decisions)
            st.metric("Avg Confidence", f"{avg_confidence:.0%}")
    
    with col3:
        # Count unique services
        all_services = set()
        for d in decisions:
            all_services.update(d.get('related_services', []))
        st.metric("Services Affected", len(all_services))
    
    with col4:
        # Count unique contributors
        all_contributors = set()
        for d in decisions:
            all_contributors.update(d.get('contributors', []))
        st.metric("Contributors", len(all_contributors))


def main():
    """Main decision explorer page."""
    
    st.title("🎯 Decision Explorer")
    st.markdown("Browse and explore engineering decisions extracted from your repository.")
    st.markdown("---")
    
    # Check if data is available
    availability = UIState.check_data_availability()
    
    if not availability.get('extracted'):
        st.warning("⚠️ No decision data available. Please run extraction first.")
        st.info("👉 Go to **Processing Dashboard** to start extraction")
        return
    
    # Get filters
    filters = render_decision_filters()
    
    # Search bar
    search_query = st.text_input(
        "🔍 Search decisions",
        placeholder="Search by title, summary, or reasoning...",
        help="Search across decision titles, summaries, and reasoning"
    )
    
    # Fetch decisions
    with st.spinner("Loading decisions..."):
        decisions = api.get_decisions(
            min_confidence=filters['min_confidence'],
            tags=filters['tags'] if filters['tags'] else None,
            services=filters['services'] if filters['services'] else None,
            limit=100
        )
    
    # Apply search filter
    if search_query:
        search_lower = search_query.lower()
        decisions = [
            d for d in decisions
            if search_lower in d.get('title', '').lower()
            or search_lower in d.get('summary', '').lower()
            or search_lower in d.get('reasoning', '').lower()
        ]
    
    # Apply sorting
    if filters['sort_by'] == "Confidence (High to Low)":
        decisions.sort(key=lambda x: x.get('confidence', 0), reverse=True)
    elif filters['sort_by'] == "Confidence (Low to High)":
        decisions.sort(key=lambda x: x.get('confidence', 0))
    elif filters['sort_by'] == "Title (A-Z)":
        decisions.sort(key=lambda x: x.get('title', ''))
    
    # Display statistics
    render_decision_stats(decisions)
    
    st.markdown("---")
    
    # View mode selection
    view_mode = st.radio(
        "View Mode",
        options=["Cards", "Table", "Compact"],
        horizontal=True
    )
    
    st.markdown("---")
    
    # Display decisions
    if decisions:
        if view_mode == "Cards":
            # Card view with pagination
            decisions_per_page = 5
            total_pages = (len(decisions) + decisions_per_page - 1) // decisions_per_page
            
            if total_pages > 1:
                page = st.number_input(
                    "Page",
                    min_value=1,
                    max_value=total_pages,
                    value=1,
                    step=1
                )
            else:
                page = 1
            
            start_idx = (page - 1) * decisions_per_page
            end_idx = start_idx + decisions_per_page
            
            for decision in decisions[start_idx:end_idx]:
                render_decision_card(decision)
            
            if total_pages > 1:
                st.info(f"Showing {start_idx + 1}-{min(end_idx, len(decisions))} of {len(decisions)} decisions (Page {page}/{total_pages})")
        
        elif view_mode == "Table":
            # Table view
            render_decision_table(decisions)
        
        else:  # Compact view
            # Compact list view
            for i, decision in enumerate(decisions):
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.markdown(f"**{decision.get('title', 'Untitled')}**")
                
                with col2:
                    confidence = decision.get('confidence', 0)
                    st.caption(f"Confidence: {confidence:.0%}")
                
                with col3:
                    if st.button("View", key=f"view_{i}"):
                        st.session_state.selected_decision = decision
                        st.rerun()
        
        # Export options
        st.markdown("---")
        st.subheader("📤 Export")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Export as JSON", use_container_width=True):
                import json
                st.download_button(
                    "Download JSON",
                    json.dumps(decisions, indent=2, default=str),
                    file_name="decisions.json",
                    mime="application/json"
                )
        
        with col2:
            if st.button("Export as CSV", use_container_width=True):
                csv_data = "Title,Confidence,Services,Tags,Contributors\n"
                for d in decisions:
                    csv_data += f'"{d.get("title", "")}",{d.get("confidence", 0):.2f},'
                    csv_data += f'"{", ".join(d.get("related_services", []))}","{", ".join(d.get("tags", []))}","{", ".join(d.get("contributors", []))}"\n'
                
                st.download_button(
                    "Download CSV",
                    csv_data,
                    file_name="decisions.csv",
                    mime="text/csv"
                )
    
    else:
        st.info("ℹ️ No decisions found matching the selected filters")
        st.markdown("Try adjusting the filters or check if decision extraction has been completed.")
    
    # Selected decision modal
    if 'selected_decision' in st.session_state and st.session_state.selected_decision:
        st.markdown("---")
        st.header("📍 Selected Decision")
        render_decision_card(st.session_state.selected_decision)
        
        if st.button("Close"):
            st.session_state.selected_decision = None
            st.rerun()


if __name__ == "__main__":
    main()

# Made with Bob
