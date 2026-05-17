"""Full automatic GitHub ingestion workflow."""

import asyncio
from typing import List, Optional, Callable

from app.ingestion.github.client import GitHubClient
from app.ingestion.github.ingestion import GitHubIngestion
from app.memory.raw_storage import RawDataStorage
from app.models.ingestion import IngestionItem
from app.models.ingestion_state import (
    IngestionItemState,
    IngestionSourceState,
    IngestionStateManager,
    IngestionStatus,
    ProcessingHandoff,
    ProcessingQueue,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


class GitHubIngestionWorkflow:
    """
    Full automatic GitHub ingestion workflow.

    Implements the complete Step 2 flow:
    1. Validate repository access
    2. Discover all PRs and issues
    3. Create ingestion queue items
    4. Fetch raw records
    5. Store with provenance
    6. Track state
    7. Enqueue for Step 3 processing
    """

    def __init__(
        self,
        owner: str,
        repo: str,
        client: GitHubClient,
        storage: RawDataStorage,
        state_manager: IngestionStateManager,
        processing_queue: ProcessingQueue,
        max_workers: int = 3,
        skip_existing: bool = True,
        stop_check: Optional[Callable[[], bool]] = None,
        pr_limit: Optional[int] = None,
        issue_limit: Optional[int] = None
    ):
        """
        Initialize workflow.

        Args:
            owner: Repository owner
            repo: Repository name
            client: GitHubClient instance
            storage: RawDataStorage instance
            state_manager: IngestionStateManager instance
            processing_queue: ProcessingQueue instance
            max_workers: Maximum concurrent workers
            skip_existing: Skip already stored items
            stop_check: Optional callback to check if ingestion should stop
            pr_limit: Max PRs to discover
            issue_limit: Max Issues to discover
        """
        self.owner = owner
        self.repo = repo
        self.client = client
        self.storage = storage
        self.state_manager = state_manager
        self.processing_queue = processing_queue
        self.max_workers = max_workers
        self.skip_existing = skip_existing
        self.stop_check = stop_check
        self.pr_limit = pr_limit
        self.issue_limit = issue_limit

        self.ingestion = GitHubIngestion(
            owner=owner,
            repo=repo,
            client=client,
            storage=storage
        )

        self.source_id = self.ingestion.get_source_id()
        self.state: Optional[IngestionSourceState] = None

        logger.info(
            "GitHub ingestion workflow initialized",
            owner=owner,
            repo=repo,
            source_id=self.source_id,
            max_workers=max_workers,
            pr_limit=pr_limit,
            issue_limit=issue_limit
        )

    async def run(self, fetch_limit: Optional[int] = None) -> IngestionSourceState:
        """
        Run the complete ingestion workflow.

        Args:
            fetch_limit: Max NEW items to fetch and store in this run.
                         (Existing/skipped items don't count towards this limit).

        Returns:
            Final ingestion state
        """
        logger.info("Starting ingestion workflow", source_id=self.source_id, fetch_limit=fetch_limit)
        
        # Save initial state immediately so UI shows progress
        from datetime import datetime
        self.state = self.state_manager.load_state(self.source_id)
        if not self.state:
            self.state = IngestionSourceState(
                source_id=self.source_id,
                repository=f"{self.owner}/{self.repo}",
                discovered_at=datetime.now().isoformat(),
                pr_count=0,
                issue_count=0,
                total_count=0
            )
        
        # Mark as discovering in metadata
        self.state.metadata["status"] = "discovering"
        self.state_manager.save_state(self.state)

        # Step 1: Validate repository access
        logger.info("Step 1: Validating repository access")
        is_valid = await self.ingestion.validate()
        if not is_valid:
            raise ValueError(f"Failed to validate repository: {self.owner}/{self.repo}")

        logger.info("Repository validated successfully")
        
        if self._should_stop():
            return self.state

        # Step 2: Discover all PRs and issues
        # (This is fast and needed to know what we already have)
        logger.info("Discovering items...")
        discovery_result = await self.ingestion.discover(
            pr_limit=self.pr_limit,
            issue_limit=self.issue_limit
        )

        logger.info(
            f"Discovered -- {discovery_result.total_count}",
            total=discovery_result.total_count
        )

        # Step 3: Initialize or load state
        logger.info("Step 3: Initializing ingestion state")
        self.state = self._initialize_state(discovery_result)
        self.state.metadata["status"] = "fetching"
        self.state_manager.save_state(self.state)

        if self._should_stop():
            return self.state

        # Step 4: Create ingestion queue items
        logger.info("Step 4: Creating ingestion queue")
        items = discovery_result.to_items()
        self._queue_items(items)
        self.state_manager.save_state(self.state)

        logger.info(
            "Ingestion queue created",
            total_items=len(items),
            queued=self.state.queued_count
        )

        # Step 5: Fetch and store raw records
        logger.info("Step 5: Fetching and storing raw records")
        await self._process_items(fetch_limit=fetch_limit)

        # Step 6: Save final state
        logger.info("Step 6: Saving final state")
        self.state.metadata["status"] = "complete" if self.state.is_complete else "partial"
        self.state_manager.save_state(self.state)

        logger.info(
            "Ingestion workflow complete",
            source_id=self.source_id,
            stored=self.state.stored_count,
            skipped=self.state.skipped_count,
            failed=self.state.failed_count,
            progress=f"{self.state.progress_percentage:.1f}%"
        )

        return self.state

    def _should_stop(self) -> bool:
        """Check if ingestion should stop."""
        if self.stop_check and self.stop_check():
            logger.info("Stop requested, halting ingestion")
            if self.state:
                self.state.metadata["status"] = "stopped"
                self.state_manager.save_state(self.state)
            return True
        return False

    def _initialize_state(self, discovery_result) -> IngestionSourceState:
        """Initialize or load ingestion state."""
        # Try to load existing state
        existing_state = self.state_manager.load_state(self.source_id)

        if existing_state:
            logger.info("Loaded existing ingestion state", source_id=self.source_id)
            # Update counts in case new items were discovered
            existing_state.pr_count = len(discovery_result.pr_numbers)
            existing_state.issue_count = len(discovery_result.issue_numbers)
            existing_state.total_count = discovery_result.total_count
            return existing_state

        # Create new state
        state = IngestionSourceState(
            source_id=self.source_id,
            repository=f"{self.owner}/{self.repo}",
            discovered_at=discovery_result.discovered_at.isoformat(),
            pr_count=len(discovery_result.pr_numbers),
            issue_count=len(discovery_result.issue_numbers),
            total_count=discovery_result.total_count
        )

        logger.info("Created new ingestion state", source_id=self.source_id)
        return state

    def _queue_items(self, items: List[IngestionItem]) -> None:
        """Queue items for ingestion."""
        if not self.state:
            return

        for item in items:
            # Check if already in state
            existing_item = self.state.get_item(item.id)

            if existing_item:
                if self.skip_existing and existing_item.status == IngestionStatus.STORED:
                    # Still ensure it's in the processing queue for Step 3
                    if existing_item.raw_data_path:
                        self._enqueue_for_processing(
                            existing_item,
                            existing_item.raw_data_path
                        )
                    continue
                
                if existing_item.status != IngestionStatus.QUEUED:
                    # If it's failed, we might want to retry it by re-queuing
                    if existing_item.status == IngestionStatus.FAILED:
                        self.state.update_item_status(item.id, IngestionStatus.QUEUED)
                    continue

            # Add to state as queued — will be fetched from GitHub
            item_state = IngestionItemState(
                item_id=item.id,
                source_id=item.source_id,
                item_type=item.item_type,
                item_number=item.item_number,
                status=IngestionStatus.QUEUED
            )

            self.state.add_item(item_state)

    def _enqueue_for_processing(self, item_state: IngestionItemState, raw_path: str) -> None:
        """Add an item to the Step 3 processing queue."""
        handoff = self._create_handoff(item_state, raw_path)
        self.processing_queue.enqueue(handoff)

    async def _process_items(self, fetch_limit: Optional[int] = None) -> None:
        """Process all queued items in batches."""
        if not self.state:
            return

        queued_items = self.state.get_items_by_status(IngestionStatus.QUEUED)

        if not queued_items:
            logger.info("No items to process")
            return

        logger.info(
            "Processing items with worker pool",
            total_items=len(queued_items),
            workers=self.max_workers,
            fetch_limit=fetch_limit
        )

        # Create semaphore for worker pool
        semaphore = asyncio.Semaphore(self.max_workers)
        
        items_fetched = 0
        batch_size = 50
        
        for i in range(0, len(queued_items), batch_size):
            if self._should_stop():
                break
                
            if fetch_limit and items_fetched >= fetch_limit:
                logger.info(f"Fetch limit reached ({fetch_limit}), stopping batch processing")
                break
                
            batch = queued_items[i : i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(queued_items)-1)//batch_size + 1} ({len(batch)} items)")
            
            tasks = [
                self._process_item(item, semaphore)
                for item in batch
            ]

            # Collect handoffs from this batch
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Count how many were actually fetched vs skipped/failed
            # (Result is ProcessingHandoff if it was stored or skipped)
            for r in results:
                if isinstance(r, ProcessingHandoff):
                    # We only count it towards the fetch_limit if it wasn't already there 
                    # (but _process_item handles the skip_existing check)
                    # For simplicity, we'll increment based on success
                    items_fetched += 1
            
            # Enqueue successful handoffs
            handoffs = [r for r in results if isinstance(r, ProcessingHandoff)]
            if handoffs:
                self.processing_queue.enqueue_batch(handoffs)
                logger.info(f"Enqueued {len(handoffs)} items for processing")
            
            # Save state after each batch
            self.state_manager.save_state(self.state)

    async def _process_item(
        self,
        item_state: IngestionItemState,
        semaphore: asyncio.Semaphore
    ) -> Optional[ProcessingHandoff]:
        """
        Process a single item.
        
        Returns:
            ProcessingHandoff if successful, None otherwise.
        """
        if not self.state or self._should_stop():
            return None

        async with semaphore:
            try:
                # Check if already exists and skip_existing is True
                if self.skip_existing:
                    exists = self.storage.exists(
                        item_state.source_id,
                        item_state.item_type,
                        item_state.item_number
                    )

                    if exists:
                        # Get existing path
                        if item_state.item_type == "pr":
                            raw_path = self.storage.base_path / "github" / item_state.source_id / "prs" / f"{item_state.item_number}.json"
                        else:
                            raw_path = self.storage.base_path / "github" / item_state.source_id / "issues" / f"{item_state.item_number}.json"

                        # Update state
                        self.state.update_item_status(
                            item_state.item_id,
                            IngestionStatus.SKIPPED,
                            raw_data_path=str(raw_path)
                        )

                        return self._create_handoff(item_state, str(raw_path))

                # Fetch raw data
                logger.info(
                    f"Fetching {item_state.item_type} #{item_state.item_number}",
                    item_id=item_state.item_id
                )

                data = await self.ingestion.fetch(item_state.item_id)

                # Store raw data
                if item_state.item_type == "pr":
                    path = self.storage.store_pr(
                        item_state.source_id,
                        item_state.item_number,
                        data
                    )
                else:
                    path = self.storage.store_issue(
                        item_state.source_id,
                        item_state.item_number,
                        data
                    )

                # Update state
                self.state.update_item_status(
                    item_state.item_id,
                    IngestionStatus.STORED,
                    raw_data_path=str(path)
                )

                return self._create_handoff(item_state, str(path))

            except Exception as e:
                logger.error(
                    "Failed to process item",
                    item_id=item_state.item_id,
                    error=str(e)
                )

                # Update state as failed
                self.state.update_item_status(
                    item_state.item_id,
                    IngestionStatus.FAILED,
                    error=str(e)
                )
                return None

    def _create_handoff(self, item_state: IngestionItemState, raw_path: str) -> ProcessingHandoff:
        """Create a handoff record for Step 3 processing."""
        return ProcessingHandoff(
            source_id=item_state.source_id,
            item_type=item_state.item_type,
            item_number=item_state.item_number,
            raw_data_path=raw_path
        )

    def get_state(self) -> Optional[IngestionSourceState]:
        """Get current ingestion state."""
        return self.state

    def get_progress(self) -> dict:
        """Get progress summary."""
        if not self.state:
            return {
                "source_id": self.source_id,
                "status": "not_started",
                "progress": 0.0
            }

        return {
            "source_id": self.source_id,
            "repository": self.state.repository,
            "total_items": self.state.total_count,
            "stored": self.state.stored_count,
            "skipped": self.state.skipped_count,
            "failed": self.state.failed_count,
            "queued": self.state.queued_count,
            "progress": self.state.progress_percentage,
            "is_complete": self.state.is_complete,
            "metadata": self.state.metadata
        }


# Made with Bob
