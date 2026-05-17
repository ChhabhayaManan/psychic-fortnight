"""
State management utilities for Streamlit UI.

Handles session state initialization, configuration persistence,
and shared state across pages.
"""

import streamlit as st
from pathlib import Path
from typing import Any, Dict, Optional, Set
import json
from datetime import datetime
import threading

class PipelineControl:
    """Shared control state for background threads."""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(PipelineControl, cls).__new__(cls)
                cls._instance.stop_requested = False
                cls._instance.active_tasks: Set[str] = set()
                cls._instance.current_stage = 'idle'
                cls._instance.error_message = ''
            return cls._instance
            
    def request_stop(self):
        with self._lock:
            self.stop_requested = True
            
    def reset_stop(self):
        with self._lock:
            self.stop_requested = False
            
    def should_stop(self) -> bool:
        with self._lock:
            return self.stop_requested

    def get_stage(self) -> str:
        with self._lock:
            return self.current_stage
            
    def set_stage(self, stage: str):
        with self._lock:
            self.current_stage = stage
            
    def get_error(self) -> str:
        with self._lock:
            return self.error_message
            
    def set_error(self, message: str):
        with self._lock:
            self.error_message = message
            self.current_stage = 'error'

    def register_task(self, task_name: str):
        with self._lock:
            self.active_tasks.add(task_name)
            
    def unregister_task(self, task_name: str):
        with self._lock:
            self.active_tasks.discard(task_name)
            
    def is_task_active(self, task_name: str) -> bool:
        with self._lock:
            return task_name in self.active_tasks


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
            updates = {
                'GITHUB_TOKEN': config.get('github_token', ''),
                'REPO_OWNER': config.get('repo_owner', ''),
                'REPO_NAME': config.get('repo_name', ''),
                'LLM_API_KEY': config.get('llm_api_key', ''),
            }
            if 'llm_provider' in config:
                provider = config['llm_provider']
                updates['LLM_PROVIDER'] = provider
                api_key = config.get('llm_api_key', '')
                if provider == "Gemini":
                    updates['GEMINI_API_KEY'] = api_key
                elif provider == "Groq":
                    updates['GROQ_API_KEY'] = api_key
                elif provider == "Watsonx":
                    updates['WATSONX_API_KEY'] = api_key

            existing_config.update(updates)
            
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
                            elif key == 'LLM_PROVIDER':
                                config['llm_provider'] = value
        except Exception as e:
            st.warning(f"Could not load configuration: {e}")
        
        return config
    
    @staticmethod
    def get_data_paths(source_id: Optional[str] = None) -> Dict[str, Path]:
        """
        Get project-specific data directory paths.
        
        Args:
            source_id: Optional project identifier
            
        Returns:
            Dictionary of path names to Path objects
        """
        if source_id:
            from app.config import get_settings
            paths = get_settings().get_project_paths(source_id)
            # Map keys to match expected UI structure if necessary
            return {
                'raw': paths['raw'],
                'extracted': paths['extracted'],
                'embeddings': paths['chroma'],
                'graph': paths['graph'],
                'state': paths['state'],
            }
            
        base = Path('data')
        return {
            'raw': base / 'raw' / 'github',
            'extracted': base / 'extracted',
            'embeddings': base / 'embeddings' / 'chroma',
            'graph': base / 'graph',
            'state': base / 'state',
        }
    
    @staticmethod
    def check_data_availability(source_id: Optional[str] = None) -> Dict[str, bool]:
        """
        Check which data directories have content.
        
        Args:
            source_id: Optional project identifier
            
        Returns:
            Dictionary of data type to availability status
        """
        paths = UIState.get_data_paths(source_id)
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
