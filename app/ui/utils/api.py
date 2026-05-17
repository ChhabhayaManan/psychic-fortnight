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
from app.memory.graph_store import GraphStore
from app.config import get_settings


class BackendAPI:
    """Interface to backend services."""
    
    def __init__(self, base_path: Path = Path('.')):
        """
        Initialize backend API.
        
        Args:
            base_path: Base directory path for data
        """
        self.base_path = base_path
        self.settings = get_settings()
        self.current_source_id = None
        self.project_paths = None
        
        # Legacy defaults
        self.data_path = base_path / 'data'
        self.json_store = JsonStore(self.data_path / 'extracted')
        self.state_manager = IngestionStateManager(self.data_path / 'state')

    def set_project(self, source_id: str):
        """
        Set the current active project.
        
        Args:
            source_id: Project identifier
        """
        self.current_source_id = source_id
        self.project_paths = self.settings.get_project_paths(source_id)
        
        # Re-initialize stores with project-specific paths
        self.json_store = JsonStore(self.project_paths['extracted'])
        self.state_manager = IngestionStateManager(self.project_paths['state'])
    
    def get_ingestion_status(self, source_id: str) -> Optional[Dict[str, Any]]:
        """
        Get ingestion status for a source.
        
        Args:
            source_id: Source identifier (e.g., 'owner_repo')
            
        Returns:
            Status dictionary or None if not found
        """
        # Ensure we are using the correct project paths
        if self.current_source_id != source_id:
            self.set_project(source_id)
            
        try:
            state = self.state_manager.load_state(source_id)
            if state:
                status = "Completed" if state.is_complete else "In Progress"
                if state.total_count == 0:
                    status = "Not Started"
                return {
                    'source_id': state.source_id,
                    'status': status,
                    'discovered_count': state.total_count,
                    'queued_count': state.queued_count,
                    'stored_count': state.stored_count,
                    'skipped_count': state.skipped_count,
                    'failed_count': state.failed_count,
                    'started_at': state.discovered_at,
                    'completed_at': state.discovered_at if state.is_complete else None,
                    'last_updated': state.discovered_at,
                }
            return None
        except Exception as e:
            print(f"Error getting ingestion status: {e}")
            return None
    
    def get_processing_queue_status(self, source_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get processing queue status.
        
        Args:
            source_id: Optional source identifier
            
        Returns:
            Queue status dictionary
        """
        if source_id and self.current_source_id != source_id:
            self.set_project(source_id)
            
        try:
            path = self.project_paths['state'] if self.project_paths else self.data_path / 'state'
            queue = ProcessingQueue(path)
            items = queue.peek(10)
            
            return {
                'pending_count': queue.size(),
                'items': [item.to_dict() for item in items],
            }
        except Exception as e:
            print(f"Error getting queue status: {e}")
            return {'pending_count': 0, 'items': []}
    
    def get_extraction_stats(self, source_id: Optional[str] = None) -> Dict[str, int]:
        """
        Get extraction statistics by artifact type.
        
        Args:
            source_id: Optional source identifier
            
        Returns:
            Dictionary of artifact type to count
        """
        if source_id and self.current_source_id != source_id:
            self.set_project(source_id)
            
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
    
    
    def get_decisions(self, 
                     min_confidence: float = 0.0,
                     tags: Optional[List[str]] = None,
                     services: Optional[List[str]] = None,
                     limit: int = 100,
                     source_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get filtered decisions.
        
        Args:
            min_confidence: Minimum confidence score
            tags: Filter by tags
            services: Filter by related services
            limit: Maximum number of results
            source_id: Optional source identifier
            
        Returns:
            List of decision dictionaries
        """
        if source_id and self.current_source_id != source_id:
            self.set_project(source_id)
            
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
                           limit: int = 100,
                           source_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get filtered timeline events.
        
        Args:
            start_date: Start date filter (ISO format)
            end_date: End date filter (ISO format)
            event_types: Filter by event types
            limit: Maximum number of results
            source_id: Optional source identifier
            
        Returns:
            List of timeline event dictionaries
        """
        if source_id and self.current_source_id != source_id:
            self.set_project(source_id)
            
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
    
    def get_graph_data(self, source_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get knowledge graph data.
        
        Args:
            source_id: Optional source identifier
            
        Returns:
            Graph data dictionary or None if not available
        """
        if source_id and self.current_source_id != source_id:
            self.set_project(source_id)
            
        try:
            path = self.project_paths['graph'] if self.project_paths else self.data_path / 'graph'
            graph_path = path / 'knowledge_graph.json'
            if graph_path.exists():
                with open(graph_path, 'r') as f:
                    return json.load(f)
            return None
        except Exception as e:
            print(f"Error getting graph data: {e}")
            return None
    
    def get_artifact_details(self, artifact_type: str, artifact_id: str, source_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a specific artifact.
        
        Args:
            artifact_type: Type of artifact
            artifact_id: Artifact identifier
            source_id: Optional source identifier
            
        Returns:
            Artifact dictionary or None if not found
        """
        if source_id and self.current_source_id != source_id:
            self.set_project(source_id)
            
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
            from app.ui.utils.state import UIState
            
            config = UIState.load_config()
            verify_ssl = config.get('verify_ssl', True)
            
            g = Github(token, verify=verify_ssl)
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
            import threading
            import asyncio
            from app.ingestion.github.client import GitHubClient
            from app.memory.raw_storage import RawDataStorage
            from app.models.ingestion_state import ProcessingQueue
            from app.ingestion.github.workflow import GitHubIngestionWorkflow
            from app.utils.rate_limiter import RateLimiter
            from app.ui.utils.state import UIState
            
            source_id = f"{owner}_{repo}"
            self.set_project(source_id)
            
            config = UIState.load_config()
            verify_ssl = config.get('verify_ssl', True)
            pr_limit = config.get('pr_limit')
            issue_limit = config.get('issue_limit')
            ingestion_workers = config.get('ingestion_workers', 3)
            rate_limit_requests = config.get('rate_limit_requests', 100)
            rate_limit_period = config.get('rate_limit_period', 60)
            
            # Convert 0 to None for no limit
            if pr_limit == 0: pr_limit = None
            if issue_limit == 0: issue_limit = None
            
            def run_workflow_in_background():
                import traceback
                from app.utils.logging import get_logger
                logger = get_logger(__name__)
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    logger.info(f"Starting ingestion workflow for {owner}/{repo}")
                    rate_limiter = RateLimiter(max_requests=rate_limit_requests, period=rate_limit_period)
                    client = GitHubClient(token=token, rate_limiter=rate_limiter, verify_ssl=verify_ssl)
                    storage = RawDataStorage(self.project_paths['raw'])
                    processing_queue = ProcessingQueue(self.project_paths['state'])
                    
                    workflow = GitHubIngestionWorkflow(
                        owner=owner,
                        repo=repo,
                        client=client,
                        storage=storage,
                        state_manager=self.state_manager,
                        processing_queue=processing_queue,
                        max_workers=ingestion_workers,
                        pr_limit=pr_limit,
                        issue_limit=issue_limit
                    )
                    
                    logger.info("Workflow initialized, starting execution")
                    final_state = loop.run_until_complete(workflow.run())
                    logger.info(f"Workflow completed successfully. Stored: {final_state.stored_count}, Failed: {final_state.failed_count}")
                except Exception as e:
                    logger.error(f"Workflow failed: {e}")
                    logger.error(traceback.format_exc())
                    # Save error to metadata
                    try:
                        from app.models.ingestion_state import IngestionSourceState
                        from datetime import datetime
                        error_state = IngestionSourceState(
                            source_id=source_id,
                            repository=f"{owner}/{repo}",
                            discovered_at=datetime.now().isoformat(),
                            metadata={"error": str(e), "failed_at": datetime.now().isoformat(), "status": "error"}
                        )
                        self.state_manager.save_state(error_state)
                    except Exception as save_error:
                        logger.error(f"Failed to save error state: {save_error}")
                finally:
                    try:
                        if 'client' in locals():
                            client.close()
                    except Exception as close_error:
                        logger.error(f"Failed to close client: {close_error}")
                    loop.close()
                    
            thread = threading.Thread(target=run_workflow_in_background)
            thread.daemon = True
            thread.start()
            
            return True, f"Ingestion started for {owner}/{repo}"
        except Exception as e:
            return False, f"Failed to start ingestion: {str(e)}"
    
    def start_extraction(self, source_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        Start extraction process for queued items.
        
        Args:
            source_id: Optional source identifier
            
        Returns:
            Tuple of (success, message)
        """
        try:
            import threading
            import asyncio
            from app.workers.extraction_worker import ExtractionWorker
            from app.models.ingestion_state import ProcessingQueue
            
            if source_id:
                self.set_project(source_id)
                
            def run_extraction_in_background():
                import traceback
                from app.utils.logging import get_logger
                logger = get_logger(__name__)
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    logger.info("Starting extraction worker")
                    path = self.project_paths['state'] if self.project_paths else self.data_path / 'state'
                    processing_queue = ProcessingQueue(path)
                    
                    worker = ExtractionWorker(
                        json_store=self.json_store,
                        processing_queue=processing_queue,
                        max_workers=3
                    )
                    
                    logger.info("Extraction worker initialized, starting processing")
                    stats = loop.run_until_complete(worker.process_all())
                    logger.info(f"Extraction completed. Processed: {stats['processed']}, Succeeded: {stats['succeeded']}, Failed: {stats['failed']}")
                except Exception as e:
                    logger.error(f"Extraction failed: {e}")
                    logger.error(traceback.format_exc())
                finally:
                    loop.close()
            
            thread = threading.Thread(target=run_extraction_in_background)
            thread.daemon = True
            thread.start()
            
            return True, "Extraction started - processing queued items"
        except Exception as e:
            return False, f"Failed to start extraction: {str(e)}"
    
    def query_memory(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Query the engineering memory system using the Step 4 orchestration pipeline.

        Args:
            query: User query string
            context: Optional context for the query

        Returns:
            Query response dictionary
        """
        try:
            from app.orchestration.answer import answer_query
            from app.orchestration.state import QueryRequest
            from app.memory.vector_store import VectorStore

            paths = self.project_paths
            if not paths:
                return {
                    'answer': 'No project configured. Please set up a repository first.',
                    'sources': [], 'confidence': 0.0, 'context': {},
                }

            # Build stores from project paths
            json_store = JsonStore(paths['extracted'])

            try:
                vector_store = VectorStore(paths['chroma'])
            except Exception:
                vector_store = None

            try:
                from app.memory.graph_store import GraphStore
                graph_store = GraphStore(paths['graph'])
            except Exception:
                graph_store = None

            request = QueryRequest(query=query)
            response = answer_query(
                request=request,
                json_store=json_store,
                vector_store=vector_store,
                graph_store=graph_store,
            )

            return {
                'answer': response.answer or 'No answer generated.',
                'sources': response.sources or [],
                'confidence': response.confidence or 0.0,
                'context': {
                    'query_type': response.query_type,
                    'evidence_count': len(response.evidence or []),
                    'limitations': response.limitations or [],
                },
            }

        except Exception as e:
            return {
                'answer': f'Query failed: {str(e)}',
                'sources': [],
                'confidence': 0.0,
                'context': {'error': str(e)},
            }

# Made with Bob
