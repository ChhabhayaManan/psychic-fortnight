"""
Query Interface Page

Chat-based interface for querying the engineering memory system.
Supports multi-turn conversations with source-grounded answers.
"""

import streamlit as st
from pathlib import Path
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.ui.utils.state import UIState
from app.ui.utils.api import BackendAPI


# Page configuration
st.set_page_config(
    page_title="Query Interface - Engineering Memory System",
    page_icon="💬",
    layout="wide",
)

# Initialize session state
UIState.init_session_state()

# Initialize API
api = BackendAPI()


def render_chat_message(role: str, content: str, metadata: dict = None):
    """
    Render a chat message with appropriate styling.
    
    Args:
        role: 'user' or 'assistant'
        content: Message content
        metadata: Optional metadata (sources, confidence, etc.)
    """
    if role == "user":
        with st.chat_message("user"):
            st.markdown(content)
    else:
        with st.chat_message("assistant"):
            st.markdown(content)
            
            # Show metadata if available
            if metadata:
                with st.expander("📊 Response Details"):
                    if 'confidence' in metadata:
                        st.metric("Confidence", f"{metadata['confidence']:.2%}")
                    
                    if 'sources' in metadata and metadata['sources']:
                        st.markdown("**Sources:**")
                        for source in metadata['sources']:
                            st.markdown(f"- {source}")
                    
                    if 'context' in metadata and metadata['context']:
                        st.markdown("**Context:**")
                        st.json(metadata['context'])


def render_example_queries():
    """Render example query suggestions."""
    st.markdown("### 💡 Example Queries")
    
    examples = [
        "What were the major architectural decisions in the last 6 months?",
        "Show me all incidents related to the authentication service",
        "Who are the main contributors to the payment module?",
        "What unresolved questions exist about the API design?",
        "Summarize the timeline of the database migration project",
        "What decisions were made about error handling?",
    ]
    
    cols = st.columns(2)
    
    for i, example in enumerate(examples):
        with cols[i % 2]:
            if st.button(example, key=f"example_{i}", use_container_width=True):
                st.session_state.current_query = example
                st.rerun()


def render_query_filters():
    """Render query filter options."""
    with st.expander("🔍 Query Filters"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.multiselect(
                "Artifact Types",
                options=["Decisions", "Incidents", "Timeline", "Architecture", "Ownership"],
                key="query_artifact_types"
            )
            
            st.date_input(
                "Date Range",
                value=None,
                key="query_date_range"
            )
        
        with col2:
            st.multiselect(
                "Services",
                options=["Authentication", "Payment", "API", "Database", "Frontend"],
                key="query_services"
            )
            
            st.slider(
                "Minimum Confidence",
                min_value=0.0,
                max_value=1.0,
                value=0.5,
                step=0.1,
                key="query_min_confidence"
            )


def process_query(query: str) -> dict:
    """
    Process a user query and return response.
    
    Args:
        query: User query string
        
    Returns:
        Response dictionary with answer, sources, confidence, etc.
    """
    # Build context from filters
    context = {
        'artifact_types': st.session_state.get('query_artifact_types', []),
        'services': st.session_state.get('query_services', []),
        'min_confidence': st.session_state.get('query_min_confidence', 0.5),
        'date_range': st.session_state.get('query_date_range'),
    }
    
    # Call backend API
    response = api.query_memory(query, context)
    
    return response


def main():
    """Main query interface page."""
    
    st.title("💬 Query Interface")
    st.markdown("Ask questions about your engineering history and get source-grounded answers.")
    st.markdown("---")
    
    # Check if system is ready
    availability = UIState.check_data_availability()
    
    if not availability.get('extracted'):
        st.warning("⚠️ No extracted data available. Please run ingestion and extraction first.")
        st.info("👉 Go to **Processing Dashboard** to start the pipeline")
        return
    
    # Query filters
    render_query_filters()
    
    st.markdown("---")
    
    # Chat history display
    st.markdown("### 💬 Conversation")
    
    # Display chat history
    for message in st.session_state.chat_history:
        render_chat_message(
            message['role'],
            message['content'],
            message.get('metadata')
        )
    
    # Example queries (show only if no chat history)
    if not st.session_state.chat_history:
        render_example_queries()
        st.markdown("---")
    
    # Query input
    query = st.chat_input("Ask a question about your engineering history...")
    
    # Handle pre-filled query from examples
    if st.session_state.current_query and not query:
        query = st.session_state.current_query
        st.session_state.current_query = ''
    
    if query:
        # Add user message to history
        st.session_state.chat_history.append({
            'role': 'user',
            'content': query,
            'timestamp': datetime.now().isoformat()
        })
        
        # Display user message
        render_chat_message('user', query)
        
        # Process query
        with st.spinner("🤔 Thinking..."):
            response = process_query(query)
        
        # Add assistant response to history
        st.session_state.chat_history.append({
            'role': 'assistant',
            'content': response['answer'],
            'metadata': {
                'sources': response.get('sources', []),
                'confidence': response.get('confidence', 0.0),
                'context': response.get('context', {}),
            },
            'timestamp': datetime.now().isoformat()
        })
        
        # Display assistant response
        render_chat_message(
            'assistant',
            response['answer'],
            {
                'sources': response.get('sources', []),
                'confidence': response.get('confidence', 0.0),
                'context': response.get('context', {}),
            }
        )
        
        # Rerun to update display
        st.rerun()
    
    # Chat controls
    st.markdown("---")
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        if st.button("🗑️ Clear Conversation", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()
    
    with col2:
        if st.button("💾 Save Chat", use_container_width=True):
            # Save chat history to file
            chat_file = Path('data/chats') / f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            chat_file.parent.mkdir(parents=True, exist_ok=True)
            
            import json
            with open(chat_file, 'w') as f:
                json.dump(st.session_state.chat_history, f, indent=2)
            
            st.success(f"✅ Chat saved to {chat_file}")
    
    with col3:
        if st.button("📤 Export", use_container_width=True):
            # Export chat as markdown
            markdown = "# Engineering Memory Chat\n\n"
            markdown += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            markdown += "---\n\n"
            
            for msg in st.session_state.chat_history:
                role = "**User**" if msg['role'] == 'user' else "**Assistant**"
                markdown += f"{role}: {msg['content']}\n\n"
            
            st.download_button(
                "Download Markdown",
                markdown,
                file_name=f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                mime="text/markdown"
            )
    
    # Statistics
    if st.session_state.chat_history:
        st.markdown("---")
        st.markdown("### 📊 Session Statistics")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            user_messages = len([m for m in st.session_state.chat_history if m['role'] == 'user'])
            st.metric("Questions Asked", user_messages)
        
        with col2:
            assistant_messages = len([m for m in st.session_state.chat_history if m['role'] == 'assistant'])
            st.metric("Responses", assistant_messages)
        
        with col3:
            if st.session_state.chat_history:
                first_msg = st.session_state.chat_history[0]
                duration = datetime.now() - datetime.fromisoformat(first_msg['timestamp'])
                st.metric("Session Duration", f"{duration.seconds // 60} min")


if __name__ == "__main__":
    main()

# Made with Bob
