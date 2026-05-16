"""
API integration utilities for Streamlit UI.

Provides interfaces to backend services including ingestion,
extraction, indexing, and querying.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.models.ingestion_state import IngestionStateManager, ProcessingQueue
from app.memory.json_store import JsonStore
from app.memory.snapshots import SnapshotStore
from app.memory.graph_store import GraphStore


class BackendAPI:
    """Interface to backend services."""
    
    def __init__(self, base_path: Path = Path('.')):
        """
        Initialize backend API.
        
        Args:
            base_path: Base directory path for data
        """
        self.base_path = base_path
        self.data_path = base_path / 'data'
        
        # Initialize stores
        self.json_store = JsonStore(self.data_path / 'extracted')
        self.snapshot_store = SnapshotStore(self.data_path / 'snapshots')
        
        # Initialize state manager
        self.state_manager = IngestionStateManager(self.data_path / 'state')
    
    def get_ingestion_status(self, source_id: str) -> Optional[Dict[str, Any]]:
        """
        Get ingestion status for a source.
        
        Args:
            source_id: Source identifier (e.g., 'owner_repo')
            
        Returns:
            Status dictionary or None if not found
        """
        try:
            state = self.state_manager.load_source_state(source_id)
            if state:
                return {
                    'source_id': state.source_id,
                    'status': state.status,
                    'discovered_count': state.discovered_count,
                    'queued_count': state.queued_count,
                    'stored_count': state.stored_count,
                    'skipped_count': state.skipped_count,
                    'failed_count': state.failed_count,
                    'started_at': state.started_at,
                    'completed_at': state.completed_at,
                    'last_updated': state.last_updated,
                }
            return None
        except Exception as e:
            print(f"Error getting ingestion status: {e}")
            return None
    
    def get_processing_queue_status(self) -> Dict[str, Any]:
        """
        Get processing queue status.
        
        Returns:
            Queue status dictionary
        """
        try:
            queue = ProcessingQueue(self.data_path / 'state')
            items = queue.list_pending()
            
            return {
                'pending_count': len(items),
                'items': items[:10],  # First 10 items
            }
        except Exception as e:
            print(f"Error getting queue status: {e}")
            return {'pending_count': 0, 'items': []}
    
    def get_extraction_stats(self) -> Dict[str, int]:
        """
        Get extraction statistics by artifact type.
        
        Returns:
            Dictionary of artifact type to count
        """
        stats = {}
        artifact_types = ['decisions', 'incidents', 'timeline', 'architecture', 
                         'ownership', 'unresolved', 'relationships']
        
        for artifact_type in artifact_types:
            try:
                artifacts = self.json_store.list_artifacts(artifact_type)
                stats[artifact_type] = len(artifacts)
            except Exception:
                stats[artifact_type] = 0
        
        return stats
    
    def get_project_snapshot(self) -> Optional[Dict[str, Any]]:
        """
        Get current project snapshot.
        
        Returns:
            Snapshot dictionary or None if not available
        """
        try:
            return self.snapshot_store.get_latest_snapshot()
        except Exception as e:
            print(f"Error getting snapshot: {e}")
            return None
    
    def get_decisions(self, 
                     min_confidence: float = 0.0,
                     tags: Optional[List[str]] = None,
                     services: Optional[List[str]] = None,
                     limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get filtered decisions.
        
        Args:
            min_confidence: Minimum confidence score
            tags: Filter by tags
            services: Filter by related services
            limit: Maximum number of results
            
        Returns:
            List of decision dictionaries
        """
        try:
            all_decisions = self.json_store.list_artifacts('decisions')
            filtered = []
            
            for decision_id in all_decisions[:limit]:
                decision = self.json_store.get_artifact('decisions', decision_id)
                if not decision:
                    continue
                
                # Apply filters
                if decision.get('confidence', 0) < min_confidence:
                    continue
                
                if tags:
                    decision_tags = decision.get('tags', [])
                    if not any(tag in decision_tags for tag in tags):
                        continue
                
                if services:
                    decision_services = decision.get('related_services', [])
                    if not any(svc in decision_services for svc in services):
                        continue
                
                filtered.append(decision)
            
            return filtered
        except Exception as e:
            print(f"Error getting decisions: {e}")
            return []
    
    def get_timeline_events(self,
                           start_date: Optional[str] = None,
                           end_date: Optional[str] = None,
                           event_types: Optional[List[str]] = None,
                           limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get filtered timeline events.
        
        Args:
            start_date: Start date filter (ISO format)
            end_date: End date filter (ISO format)
            event_types: Filter by event types
            limit: Maximum number of results
            
        Returns:
            List of timeline event dictionaries
        """
        try:
            all_events = self.json_store.list_artifacts('timeline')
            filtered = []
            
            for event_id in all_events[:limit]:
                event = self.json_store.get_artifact('timeline', event_id)
                if not event:
                    continue
                
                # Apply date filters
                event_date = event.get('timestamp')
                if start_date and event_date and event_date < start_date:
                    continue
                if end_date and event_date and event_date > end_date:
                    continue
                
                # Apply type filter
                if event_types:
                    if event.get('event_type') not in event_types:
                        continue
                
                filtered.append(event)
            
            # Sort by timestamp
            filtered.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return filtered
        except Exception as e:
            print(f"Error getting timeline events: {e}")
            return []
    
    def get_graph_data(self) -> Optional[Dict[str, Any]]:
        """
        Get knowledge graph data.
        
        Returns:
            Graph data dictionary or None if not available
        """
        try:
            graph_path = self.data_path / 'graph' / 'knowledge_graph.json'
            if graph_path.exists():
                with open(graph_path, 'r') as f:
                    return json.load(f)
            return None
        except Exception as e:
            print(f"Error getting graph data: {e}")
            return None
    
    def get_artifact_details(self, artifact_type: str, artifact_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a specific artifact.
        
        Args:
            artifact_type: Type of artifact
            artifact_id: Artifact identifier
            
        Returns:
            Artifact dictionary or None if not found
        """
        try:
            return self.json_store.get_artifact(artifact_type, artifact_id)
        except Exception as e:
            print(f"Error getting artifact details: {e}")
            return None
    
    def validate_github_connection(self, token: str, owner: str, repo: str) -> Tuple[bool, str]:
        """
        Validate GitHub connection.
        
        Args:
            token: GitHub token
            owner: Repository owner
            repo: Repository name
            
        Returns:
            Tuple of (success, message)
        """
        try:
            from github import Github
            
            g = Github(token)
            repository = g.get_repo(f"{owner}/{repo}")
            
            # Try to access basic info
            _ = repository.name
            _ = repository.description
            
            return True, f"Successfully connected to {owner}/{repo}"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
    
    def start_ingestion(self, owner: str, repo: str, token: str) -> Tuple[bool, str]:
        """
        Start ingestion process for a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            token: GitHub token
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # This would trigger the actual ingestion workflow
            # For now, return a placeholder
            return True, "Ingestion started (implementation pending)"
        except Exception as e:
            return False, f"Failed to start ingestion: {str(e)}"
    
    def query_memory(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Query the engineering memory system.
        
        Args:
            query: User query string
            context: Optional context for the query
            
        Returns:
            Query response dictionary
        """
        # This would integrate with Step 4 (LangGraph orchestration)
        # For now, return a placeholder response
        return {
            'answer': 'Query processing not yet implemented. This will integrate with Step 4 orchestration.',
            'sources': [],
            'confidence': 0.0,
            'context': {},
        }

# Made with Bob
