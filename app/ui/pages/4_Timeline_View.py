"""
Timeline View Page

Visual exploration of engineering timeline events extracted from the repository.
Supports filtering by date range, event type, and related entities.
"""

import streamlit as st
from pathlib import Path
import sys
from datetime import datetime, timedelta
import pandas as pd

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.ui.utils.state import UIState
from app.ui.utils.api import BackendAPI


# Page configuration
st.set_page_config(
    page_title="Timeline View - Engineering Memory System",
    page_icon="📅",
    layout="wide",
)

# Initialize session state
UIState.init_session_state()

# Initialize API
api = BackendAPI()


def render_timeline_filters():
    """Render timeline filter controls."""
    st.sidebar.header("🔍 Filters")
    
    # Date range filter
    st.sidebar.subheader("Date Range")
    
    date_preset = st.sidebar.selectbox(
        "Quick Select",
        options=["All Time", "Last 7 Days", "Last 30 Days", "Last 90 Days", "Last Year", "Custom"],
        index=0
    )
    
    if date_preset == "Custom":
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.date_input("From", value=None)
        with col2:
            end_date = st.date_input("To", value=None)
    else:
        # Calculate date range based on preset
        end_date = datetime.now()
        if date_preset == "Last 7 Days":
            start_date = end_date - timedelta(days=7)
        elif date_preset == "Last 30 Days":
            start_date = end_date - timedelta(days=30)
        elif date_preset == "Last 90 Days":
            start_date = end_date - timedelta(days=90)
        elif date_preset == "Last Year":
            start_date = end_date - timedelta(days=365)
        else:
            start_date = None
    
    # Event type filter
    st.sidebar.subheader("Event Types")
    event_types = st.sidebar.multiselect(
        "Select Types",
        options=["PR Merged", "Issue Closed", "Release", "Incident", "Decision", "Architecture Change"],
        default=[]
    )
    
    # Entity filter
    st.sidebar.subheader("Related Entities")
    services = st.sidebar.multiselect(
        "Services",
        options=["Authentication", "Payment", "API", "Database", "Frontend", "Backend"],
        default=[]
    )
    
    contributors = st.sidebar.multiselect(
        "Contributors",
        options=[],  # Would be populated from actual data
        default=[]
    )
    
    return {
        'start_date': start_date.isoformat() if start_date else None,
        'end_date': end_date.isoformat() if end_date else None,
        'event_types': event_types,
        'services': services,
        'contributors': contributors,
    }


def render_timeline_event(event: dict):
    """
    Render a single timeline event.
    
    Args:
        event: Event dictionary
    """
    with st.container():
        col1, col2 = st.columns([1, 4])
        
        with col1:
            # Event timestamp
            timestamp = event.get('timestamp', '')
            if timestamp:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                st.markdown(f"**{dt.strftime('%Y-%m-%d')}**")
                st.caption(dt.strftime('%H:%M:%S'))
            
            # Event type badge
            event_type = event.get('event_type', 'Unknown')
            st.markdown(f"`{event_type}`")
        
        with col2:
            # Event title and summary
            title = event.get('title', 'Untitled Event')
            st.markdown(f"### {title}")
            
            summary = event.get('summary', '')
            if summary:
                st.markdown(summary)
            
            # Metadata
            col_a, col_b, col_c = st.columns(3)
            
            with col_a:
                if 'contributors' in event and event['contributors']:
                    st.caption(f"👤 {', '.join(event['contributors'][:3])}")
            
            with col_b:
                if 'related_services' in event and event['related_services']:
                    st.caption(f"🔧 {', '.join(event['related_services'][:3])}")
            
            with col_c:
                confidence = event.get('confidence', 0)
                st.caption(f"📊 Confidence: {confidence:.0%}")
            
            # Expandable details
            with st.expander("📄 Details"):
                if 'description' in event:
                    st.markdown("**Description:**")
                    st.markdown(event['description'])
                
                if 'source_references' in event:
                    st.markdown("**Sources:**")
                    for ref in event['source_references']:
                        st.markdown(f"- [{ref.get('type', 'Unknown')} #{ref.get('number', '?')}]({ref.get('url', '#')})")
                
                if 'tags' in event and event['tags']:
                    st.markdown("**Tags:**")
                    st.markdown(", ".join(f"`{tag}`" for tag in event['tags']))
        
        st.markdown("---")


def render_timeline_chart(events: list):
    """
    Render timeline visualization chart.
    
    Args:
        events: List of event dictionaries
    """
    if not events:
        return
    
    # Prepare data for chart
    chart_data = []
    for event in events:
        timestamp = event.get('timestamp')
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                chart_data.append({
                    'Date': dt.date(),
                    'Event': event.get('title', 'Untitled'),
                    'Type': event.get('event_type', 'Unknown'),
                })
            except:
                pass
    
    if chart_data:
        df = pd.DataFrame(chart_data)
        
        # Group by date and count
        daily_counts = df.groupby('Date').size().reset_index(name='Count')
        
        st.line_chart(daily_counts.set_index('Date'))


def main():
    """Main timeline view page."""
    
    st.title("📅 Timeline View")
    st.markdown("Explore engineering events chronologically.")
    st.markdown("---")
    
    # Check if data is available
    availability = UIState.check_data_availability()
    
    if not availability.get('extracted'):
        st.warning("⚠️ No timeline data available. Please run extraction first.")
        st.info("👉 Go to **Processing Dashboard** to start extraction")
        return
    
    # Get filters
    filters = render_timeline_filters()
    
    # Fetch timeline events
    with st.spinner("Loading timeline events..."):
        events = api.get_timeline_events(
            start_date=filters['start_date'],
            end_date=filters['end_date'],
            event_types=filters['event_types'] if filters['event_types'] else None,
        )
    
    # Display summary
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Events", len(events))
    
    with col2:
        if events:
            event_types = set(e.get('event_type', 'Unknown') for e in events)
            st.metric("Event Types", len(event_types))
    
    with col3:
        if events:
            date_range = "N/A"
            timestamps = [e.get('timestamp') for e in events if e.get('timestamp')]
            if timestamps:
                dates = [datetime.fromisoformat(ts.replace('Z', '+00:00')).date() for ts in timestamps]
                date_range = f"{min(dates)} to {max(dates)}"
            st.metric("Date Range", date_range)
    
    st.markdown("---")
    
    # Timeline visualization
    if events:
        st.subheader("📊 Event Distribution")
        render_timeline_chart(events)
        
        st.markdown("---")
        
        # View mode selection
        view_mode = st.radio(
            "View Mode",
            options=["Timeline", "Table", "Calendar"],
            horizontal=True
        )
        
        st.markdown("---")
        
        if view_mode == "Timeline":
            # Timeline view
            st.subheader("📋 Timeline Events")
            
            # Pagination
            events_per_page = 10
            total_pages = (len(events) + events_per_page - 1) // events_per_page
            
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
            
            start_idx = (page - 1) * events_per_page
            end_idx = start_idx + events_per_page
            
            # Display events
            for event in events[start_idx:end_idx]:
                render_timeline_event(event)
            
            # Pagination info
            if total_pages > 1:
                st.info(f"Showing {start_idx + 1}-{min(end_idx, len(events))} of {len(events)} events (Page {page}/{total_pages})")
        
        elif view_mode == "Table":
            # Table view
            st.subheader("📊 Event Table")
            
            table_data = []
            for event in events:
                timestamp = event.get('timestamp', '')
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        date_str = dt.strftime('%Y-%m-%d %H:%M')
                    except:
                        date_str = timestamp
                else:
                    date_str = 'N/A'
                
                table_data.append({
                    'Date': date_str,
                    'Type': event.get('event_type', 'Unknown'),
                    'Title': event.get('title', 'Untitled'),
                    'Confidence': f"{event.get('confidence', 0):.0%}",
                })
            
            df = pd.DataFrame(table_data)
            st.dataframe(df, use_container_width=True)
        
        else:  # Calendar view
            st.subheader("📅 Calendar View")
            st.info("Calendar view coming soon!")
    
    else:
        st.info("ℹ️ No events found matching the selected filters")
        st.markdown("Try adjusting the filters or check if timeline extraction has been completed.")


if __name__ == "__main__":
    main()

# Made with Bob
