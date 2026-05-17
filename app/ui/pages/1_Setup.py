"""
Setup and Configuration Page

Allows users to configure GitHub credentials, repository details,
and other system settings.
"""

import streamlit as st
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.ui.utils.state import UIState
from app.ui.utils.api import BackendAPI


# Page configuration
st.set_page_config(
    page_title="Setup - Engineering Memory System",
    page_icon="⚙️",
    layout="wide",
)

# Initialize session state
UIState.init_session_state()

# Initialize API
api = BackendAPI()


def main():
    """Main setup page."""
    
    st.title("⚙️ Setup and Configuration")
    st.markdown("Configure your GitHub connection and system settings.")
    st.markdown("---")
    
    # Load existing configuration
    config = UIState.load_config()
    
    # GitHub Configuration Section
    st.header("🔗 GitHub Configuration")
    
    with st.form("github_config"):
        st.markdown("### Repository Details")
        
        col1, col2 = st.columns(2)
        
        with col1:
            repo_owner = st.text_input(
                "Repository Owner",
                value=config.get('repo_owner', ''),
                placeholder="e.g., microsoft",
                help="The GitHub username or organization that owns the repository"
            )
        
        with col2:
            repo_name = st.text_input(
                "Repository Name",
                value=config.get('repo_name', ''),
                placeholder="e.g., vscode",
                help="The name of the repository"
            )
        
        st.markdown("### Authentication")
        
        github_token = st.text_input(
            "GitHub Personal Access Token",
            value=config.get('github_token', ''),
            type="password",
            placeholder="ghp_xxxxxxxxxxxxxxxxxxxx",
            help="Generate a token at https://github.com/settings/tokens with 'repo' scope"
        )
        
        verify_ssl = st.checkbox(
            "Verify SSL Certificates",
            value=config.get('verify_ssl', True),
            help="Uncheck this if you are behind a corporate proxy that uses self-signed certificates"
        )
        
        if github_token:
            st.info(f"Token: {UIState.mask_token(github_token)}")
        
        st.markdown("---")
        
        col1, col2 = st.columns([1, 3])
        
        with col1:
            validate_button = st.form_submit_button(
                "🔍 Validate Connection",
                use_container_width=True
            )
        
        with col2:
            save_button = st.form_submit_button(
                "💾 Save Configuration",
                type="primary",
                use_container_width=True
            )
    
    # Handle validation
    if validate_button:
        if not all([github_token, repo_owner, repo_name]):
            st.error("❌ Please fill in all fields before validating")
        else:
            with st.spinner("Validating GitHub connection..."):
                success, message = api.validate_github_connection(
                    github_token, repo_owner, repo_name
                )
                
                if success:
                    st.success(f"✅ {message}")
                else:
                    st.error(f"❌ {message}")
    
    # Handle save
    if save_button:
        if not all([github_token, repo_owner, repo_name]):
            st.error("❌ Please fill in all fields before saving")
        else:
            config_data = {
                'github_token': github_token,
                'repo_owner': repo_owner,
                'repo_name': repo_name,
                'verify_ssl': verify_ssl,
                'llm_api_key': config.get('llm_api_key', ''),
            }
            
            if UIState.save_config(config_data):
                from app.config.settings import reload_settings
                reload_settings()
                st.success("✅ Configuration saved successfully!")
                st.info("You can now proceed to the Processing Dashboard to start ingestion.")
                
                # Update session state
                st.session_state.github_token = github_token
                st.session_state.repo_owner = repo_owner
                st.session_state.repo_name = repo_name
                st.session_state.config_saved = True
            else:
                st.error("❌ Failed to save configuration")
    
    # LLM Configuration Section
    st.markdown("---")
    st.header("🤖 LLM Configuration (Optional)")
    
    with st.form("llm_config"):
        st.markdown("""
        Configure your LLM API for query processing and extraction.
        This is optional for basic ingestion but required for the Query Interface.
        """)
        
        llm_provider = st.selectbox(
            "LLM Provider",
            options=["Watsonx", "Gemini", "Groq", "OpenAI", "Azure OpenAI", "Local Model"],
            index=["Watsonx", "Gemini", "Groq", "OpenAI", "Azure OpenAI", "Local Model"].index(config.get('llm_provider', 'Watsonx')) if config.get('llm_provider', 'Watsonx') in ["Watsonx", "Gemini", "Groq", "OpenAI", "Azure OpenAI", "Local Model"] else 0,
            help="Select your LLM provider"
        )
        
        llm_api_key = st.text_input(
            "API Key",
            value=config.get('llm_api_key', ''),
            type="password",
            placeholder="Enter your API key",
            help="API key for the selected LLM provider"
        )
        
        if llm_api_key:
            st.info(f"API Key: {UIState.mask_token(llm_api_key)}")
        
        save_llm_button = st.form_submit_button(
            "💾 Save LLM Configuration",
            use_container_width=True
        )
    
    if save_llm_button:
        config_data = {
            'github_token': config.get('github_token', ''),
            'repo_owner': config.get('repo_owner', ''),
            'repo_name': config.get('repo_name', ''),
            'llm_api_key': llm_api_key,
            'llm_provider': llm_provider,
        }
        
        if UIState.save_config(config_data):
            from app.config.settings import reload_settings
            reload_settings()
            st.success("✅ LLM configuration saved successfully!")
            st.session_state.llm_api_key = llm_api_key
            st.session_state.llm_provider = llm_provider
        else:
            st.error("❌ Failed to save LLM configuration")
    
    # Data Directories Section
    st.markdown("---")
    st.header("📁 Data Directories")
    
    paths = UIState.get_data_paths()
    availability = UIState.check_data_availability()
    
    st.markdown("Current data directory structure:")
    
    for name, path in paths.items():
        status = "✅ Available" if availability.get(name) else "❌ Empty"
        st.text(f"{status} - {name}: {path}")
    
    # Advanced Settings
    st.markdown("---")
    st.header("🔧 Advanced Settings")
    
    with st.expander("Discovery Limits (Testing)"):
        st.markdown("""
        Limit the number of items to discover for testing purposes or very large repositories.
        Set to 0 or leave empty for no limit.
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            pr_limit = st.number_input(
                "Max PRs",
                min_value=0,
                max_value=10000,
                value=config.get('pr_limit', 50),
                help="Maximum number of PRs to discover"
            )
        
        with col2:
            issue_limit = st.number_input(
                "Max Issues",
                min_value=0,
                max_value=10000,
                value=config.get('issue_limit', 50),
                help="Maximum number of issues to discover (excluding PRs)"
            )
        
        if st.button("💾 Save Limits"):
            config_data = UIState.load_config()
            config_data['pr_limit'] = pr_limit
            config_data['issue_limit'] = issue_limit
            if UIState.save_config(config_data):
                st.success("✅ Limits saved!")
            else:
                st.error("❌ Failed to save limits")

    with st.expander("Rate Limiting"):
        st.markdown("""
        Configure rate limiting for GitHub API calls to avoid hitting rate limits.
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            rate_limit_requests = st.number_input(
                "Requests per Period",
                min_value=1,
                max_value=1000,
                value=config.get('rate_limit_requests', 100),
                help="Maximum number of requests allowed per period"
            )
        
        with col2:
            rate_limit_period = st.number_input(
                "Period (seconds)",
                min_value=1,
                max_value=3600,
                value=config.get('rate_limit_period', 60),
                help="Time period for rate limiting in seconds"
            )
        
        if st.button("💾 Save Rate Limits"):
            config_data = UIState.load_config()
            config_data['rate_limit_requests'] = rate_limit_requests
            config_data['rate_limit_period'] = rate_limit_period
            if UIState.save_config(config_data):
                st.success("✅ Rate limits saved!")
            else:
                st.error("❌ Failed to save rate limits")
    
    with st.expander("Worker Configuration"):
        st.markdown("""
        Configure the number of concurrent workers for ingestion and extraction.
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            ingestion_workers = st.number_input(
                "Ingestion Workers",
                min_value=1,
                max_value=20,
                value=config.get('ingestion_workers', 5),
                help="Number of concurrent workers for GitHub ingestion"
            )
        
        with col2:
            extraction_workers = st.number_input(
                "Extraction Workers",
                min_value=1,
                max_value=20,
                value=config.get('extraction_workers', 3),
                help="Number of concurrent workers for artifact extraction"
            )
            
        if st.button("💾 Save Worker Config"):
            config_data = UIState.load_config()
            config_data['ingestion_workers'] = ingestion_workers
            config_data['extraction_workers'] = extraction_workers
            if UIState.save_config(config_data):
                st.success("✅ Worker configuration saved!")
            else:
                st.error("❌ Failed to save worker configuration")
    
    # Configuration Summary
    st.markdown("---")
    st.header("📋 Configuration Summary")
    
    if st.session_state.config_saved:
        st.success("✅ System is configured and ready to use")
        
        summary_data = {
            "GitHub Repository": f"{st.session_state.repo_owner}/{st.session_state.repo_name}",
            "GitHub Token": UIState.mask_token(st.session_state.github_token),
            "LLM Configured": "Yes" if st.session_state.llm_api_key else "No",
        }
        
        for key, value in summary_data.items():
            st.text(f"{key}: {value}")
        
        st.markdown("---")
        st.info("👉 Next step: Go to **Processing Dashboard** to start ingestion")
    else:
        st.warning("⚠️ Configuration not yet saved")
        st.info("👉 Fill in the required fields and click 'Save Configuration'")


if __name__ == "__main__":
    main()

# Made with Bob
