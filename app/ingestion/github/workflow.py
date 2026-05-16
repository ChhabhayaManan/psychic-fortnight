"""Full automatic GitHub ingestion workflow."""

import asyncio
from typing import List, Optional

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
        skip_existing: bool = True
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
        """
        self.owner = owner
        self.repo = repo
        self.client = client
        self.storage = storage
        self.state_manager = state_manager
        self.processing_queue = processing_queue
        self.max_workers = max_workers
        self.skip_existing = skip_existing

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
            max_workers=max_workers
        )

    async def run(self) -> IngestionSourceState:
        """
        Run the complete ingestion workflow.

        Returns:
            Final ingestion state
        """
        logger.info("Starting ingestion workflow", source_id=self.source_id)

        # Step 1: Validate repository access
        logger.info("Step 1: Validating repository access")
        is_valid = await self.ingestion.validate()
        if not is_valid:
            raise ValueError(f"Failed to validate repository: {self.owner}/{self.repo}")

        logger.info("Repository validated successfully")

        # Step 2: Discover all PRs and issues
        logger.info("Step 2: Discovering PRs and issues")
        discovery_result = await self.ingestion.discover()

        logger.info(
            "Discovery complete",
            prs=len(discovery_result.pr_numbers),
            issues=len(discovery_result.issue_numbers),
            total=discovery_result.total_count
        )

        # Step 3: Initialize or load state
        logger.info("Step 3: Initializing ingestion state")
        self.state = self._initialize_state(discovery_result)

        # Step 4: Create ingestion queue items
        logger.info("Step 4: Creating ingestion queue")
        items = discovery_result.to_items()
        self._queue_items(items)

        logger.info(
            "Ingestion queue created",
            total_items=len(items),
            queued=self.state.queued_count
        )

        # Step 5: Fetch and store raw records
        logger.info("Step 5: Fetching and storing raw records")
        await self._process_items()

        # Step 6: Save final state
        logger.info("Step 6: Saving final state")
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

    def _initialize_state(self, discovery_result) -> IngestionSourceState:
        """Initialize or load ingestion state."""
        # Try to load existing state
        existing_state = self.state_manager.load_state(self.source_id)

        if existing_state:
            logger.info("Loaded existing ingestion state", source_id=self.source_id)
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
                # Skip if already stored and skip_existing is True
                if self.skip_existing and existing_item.status == IngestionStatus.STORED:
                    logger.debug(
                        "Skipping already stored item",
                        item_id=item.id
                    )
                    continue

            # Add to state as queued
            item_state = IngestionItemState(
                item_id=item.id,
                source_id=item.source_id,
                item_type=item.item_type,
                item_number=item.item_number,
                status=IngestionStatus.QUEUED
            )
            self.state.add_item(item_state)

    async def _process_items(self) -> None:
        """Process all queued items with worker pool."""
        if not self.state:
            return

        queued_items = self.state.get_items_by_status(IngestionStatus.QUEUED)

        if not queued_items:
            logger.info("No items to process")
            return

        logger.info(
            "Processing items with worker pool",
            total_items=len(queued_items),
            workers=self.max_workers
        )

        # Create semaphore for worker pool
        semaphore = asyncio.Semaphore(self.max_workers)

        # Process items concurrently
        tasks = [
            self._process_item(item, semaphore)
            for item in queued_items
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_item(
        self,
        item_state: IngestionItemState,
        semaphore: asyncio.Semaphore
    ) -> None:
        """Process a single item."""
        if not self.state:
            return

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
                        logger.info(
                            "Item already stored, skipping",
                            item_id=item_state.item_id
                        )

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

                        # Still enqueue for processing
                        self._enqueue_for_processing(item_state, str(raw_path))

                        return

                # Fetch raw data
                logger.info(
                    "Fetching item",
                    item_id=item_state.item_id,
                    type=item_state.item_type,
                    number=item_state.item_number
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

                logger.info(
                    "Item stored successfully",
                    item_id=item_state.item_id,
                    path=str(path)
                )

                # Update state
                self.state.update_item_status(
                    item_state.item_id,
                    IngestionStatus.STORED,
                    raw_data_path=str(path)
                )

                # Enqueue for Step 3 processing
                self._enqueue_for_processing(item_state, str(path))

                # Save state periodically
                self.state_manager.save_state(self.state)

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

                # Save state
                self.state_manager.save_state(self.state)

    def _enqueue_for_processing(self, item_state: IngestionItemState, raw_path: str) -> None:
        """Enqueue item for Step 3 processing."""
        handoff = ProcessingHandoff(
            source_id=item_state.source_id,
            item_type=item_state.item_type,
            item_number=item_state.item_number,
            raw_data_path=raw_path
        )

        self.processing_queue.enqueue(handoff)

        logger.debug(
            "Item enqueued for processing",
            item_id=item_state.item_id,
            raw_path=raw_path
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
            "is_complete": self.state.is_complete
        }


# Made with Bob
