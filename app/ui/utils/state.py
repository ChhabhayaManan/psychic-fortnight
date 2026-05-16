"""
State management utilities for Streamlit UI.

Handles session state initialization, configuration persistence,
and shared state across pages.
"""

import streamlit as st
from pathlib import Path
from typing import Any, Dict, Optional
import json
from datetime import datetime


class UIState:
    """Manages UI session state and configuration."""
    
    @staticmethod
    def init_session_state():
        """Initialize session state variables if not already set."""
        defaults = {
            # Configuration
            'github_token': '',
            'repo_owner': '',
            'repo_name': '',
            'llm_api_key': '',
            'config_saved': False,
            
            # Processing state
            'ingestion_running': False,
            'extraction_running': False,
            'last_refresh': None,
            
            # Chat state
            'chat_history': [],
            'current_query': '',
            
            # Filters
            'timeline_filters': {
                'start_date': None,
                'end_date': None,
                'event_types': [],
            },
            'decision_filters': {
                'min_confidence': 0.0,
                'tags': [],
                'services': [],
            },
            'graph_filters': {
                'node_types': [],
                'max_depth': 2,
            },
        }
        
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    @staticmethod
    def save_config(config: Dict[str, Any]) -> bool:
        """
        Save configuration to .env file.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            env_path = Path('.env')
            
            # Read existing .env if it exists
            existing_config = {}
            if env_path.exists():
                with open(env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            existing_config[key.strip()] = value.strip()
            
            # Update with new config
            existing_config.update({
                'GITHUB_TOKEN': config.get('github_token', ''),
                'REPO_OWNER': config.get('repo_owner', ''),
                'REPO_NAME': config.get('repo_name', ''),
                'LLM_API_KEY': config.get('llm_api_key', ''),
            })
            
            # Write back to .env
            with open(env_path, 'w') as f:
                f.write("# Engineering Memory System Configuration\n")
                f.write(f"# Last updated: {datetime.now().isoformat()}\n\n")
                for key, value in existing_config.items():
                    if value:  # Only write non-empty values
                        f.write(f"{key}={value}\n")
            
            # Update session state
            st.session_state.config_saved = True
            return True
            
        except Exception as e:
            st.error(f"Failed to save configuration: {e}")
            return False
    
    @staticmethod
    def load_config() -> Dict[str, Any]:
        """
        Load configuration from .env file.
        
        Returns:
            Configuration dictionary
        """
        config = {
            'github_token': '',
            'repo_owner': '',
            'repo_name': '',
            'llm_api_key': '',
        }
        
        try:
            env_path = Path('.env')
            if env_path.exists():
                with open(env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip()
                            
                            if key == 'GITHUB_TOKEN':
                                config['github_token'] = value
                            elif key == 'REPO_OWNER':
                                config['repo_owner'] = value
                            elif key == 'REPO_NAME':
                                config['repo_name'] = value
                            elif key == 'LLM_API_KEY':
                                config['llm_api_key'] = value
        except Exception as e:
            st.warning(f"Could not load configuration: {e}")
        
        return config
    
    @staticmethod
    def get_data_paths() -> Dict[str, Path]:
        """
        Get standard data directory paths.
        
        Returns:
            Dictionary of path names to Path objects
        """
        base = Path('data')
        return {
            'raw': base / 'raw' / 'github',
            'extracted': base / 'extracted',
            'embeddings': base / 'embeddings' / 'chroma',
            'graph': base / 'graph',
            'snapshots': base / 'snapshots',
            'state': base / 'state',
        }
    
    @staticmethod
    def check_data_availability() -> Dict[str, bool]:
        """
        Check which data directories have content.
        
        Returns:
            Dictionary of data type to availability status
        """
        paths = UIState.get_data_paths()
        availability = {}
        
        for name, path in paths.items():
            availability[name] = path.exists() and any(path.iterdir()) if path.exists() else False
        
        return availability
    
    @staticmethod
    def format_timestamp(ts: Optional[str]) -> str:
        """
        Format ISO timestamp for display.
        
        Args:
            ts: ISO format timestamp string
            
        Returns:
            Formatted timestamp string
        """
        if not ts:
            return "N/A"
        
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return ts
    
    @staticmethod
    def mask_token(token: str, visible_chars: int = 4) -> str:
        """
        Mask sensitive token for display.
        
        Args:
            token: Token string to mask
            visible_chars: Number of characters to show at start
            
        Returns:
            Masked token string
        """
        if not token or len(token) <= visible_chars:
            return "****"
        
        return token[:visible_chars] + "*" * (len(token) - visible_chars)

# Made with Bob
