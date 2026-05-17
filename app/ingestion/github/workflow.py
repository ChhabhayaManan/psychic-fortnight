"""
GitHub ingestion workflow — producer/consumer pipeline.

Architecture:
  1 Discovery producer  → fast page scanning (100 numbers per API call)
                        → writes manifest JSONL + fills asyncio.Queue
  N Fetch workers       → pull from queue, fetch full detail in parallel
                        → store to disk + enqueue for extraction

Workers start immediately; extraction begins while discovery is still running.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from app.ingestion.github.client import GitHubClient
from app.ingestion.github.ingestion import GitHubIngestion
from app.memory.raw_storage import RawDataStorage
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

# Number of parallel fetch workers
FETCH_WORKERS = 8
# Max items buffered in the queue between discovery and fetch
QUEUE_BUFFER = 400
# Log progress every N fetches
LOG_FETCH_EVERY = 10


class GitHubIngestionWorkflow:

    def __init__(
        self,
        owner: str,
        repo: str,
        client: GitHubClient,
        storage: RawDataStorage,
        state_manager: IngestionStateManager,
        processing_queue: ProcessingQueue,
        max_workers: int = FETCH_WORKERS,
        skip_existing: bool = True,
        stop_check: Optional[Callable[[], bool]] = None,
        pr_limit: Optional[int] = None,
        issue_limit: Optional[int] = None,
    ):
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
            owner=owner, repo=repo, client=client, storage=storage
        )
        self.source_id = self.ingestion.get_source_id()
        self.state: Optional[IngestionSourceState] = None

        # Shared counters (updated by multiple workers)
        self._fetched = 0
        self._skipped = 0
        self._failed = 0
        self._counter_lock: Optional[asyncio.Lock] = None

        logger.info(
            "Ingestion workflow initialized",
            owner=owner,
            repo=repo,
            source_id=self.source_id,
            fetch_workers=self.max_workers,
        )

    # ─── Public entry point ───────────────────────────────────────────────────

    async def run(self) -> IngestionSourceState:
        self._counter_lock = asyncio.Lock()
        print(f"\n[INGEST] Starting pipeline for {self.owner}/{self.repo} "
              f"with {self.max_workers} fetch workers")

        # Load or create state
        self.state = self.state_manager.load_state(self.source_id)
        if not self.state:
            self.state = IngestionSourceState(
                source_id=self.source_id,
                repository=f"{self.owner}/{self.repo}",
                discovered_at=datetime.now().isoformat(),
            )
        self.state.metadata["status"] = "validating"
        self.state_manager.save_state(self.state)

        # Validate repo access
        is_valid = await self.ingestion.validate()
        if not is_valid:
            raise ValueError(f"Cannot access repository: {self.owner}/{self.repo}")
        if self._should_stop():
            return self.state

        repo = self.ingestion._repository
        self.state.metadata["status"] = "running"
        self.state_manager.save_state(self.state)

        # Work queue between discovery and fetch workers
        work_queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_BUFFER)

        # Start N fetch workers (they wait immediately for items)
        worker_tasks = [
            asyncio.create_task(self._fetch_worker(work_queue, worker_id=i))
            for i in range(self.max_workers)
        ]

        try:
            # Run discovery producer (fills queue while workers drain it)
            await self._discovery_producer(work_queue, repo)
        finally:
            # Signal all workers to stop (one sentinel per worker)
            for _ in range(self.max_workers):
                await work_queue.put(None)

            # Wait for all workers to finish with a timeout to avoid hanging forever
            # but ensuring we don't close the loop while they are still running
            done, pending = await asyncio.wait(worker_tasks, timeout=30)
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

        # Final state save
        self.state.metadata["status"] = "complete"
        self.state_manager.save_state(self.state)

        print(f"\n[INGEST] Complete — "
              f"fetched={self._fetched}  "
              f"skipped={self._skipped}  "
              f"failed={self._failed}")
        return self.state

    # ─── Discovery producer ───────────────────────────────────────────────────

    async def _discovery_producer(self, queue: asyncio.Queue, repo) -> None:
        """
        Scans PR and issue numbers page by page (100/page, ~1s per page).
        Writes each discovered number to the manifest JSONL file and puts
        items that need fetching into the work queue.
        """
        manifest_path = self._manifest_path()
        manifest_path.parent.mkdir(parents=True, exist_ok=True)

        pr_scanned = 0
        issue_scanned = 0

        with open(manifest_path, "w", encoding="utf-8") as mf:

            # ── PRs ──────────────────────────────────────────────────────────
            pr_limit_rem = self.pr_limit
            async for page_nums in self.client.stream_pr_pages(repo, state="all"):
                if self._should_stop():
                    break

                page_nums = sorted(page_nums)  # oldest first
                if pr_limit_rem is not None:
                    page_nums = page_nums[:pr_limit_rem]
                    pr_limit_rem -= len(page_nums)

                for num in page_nums:
                    mf.write(json.dumps({"type": "pr", "number": num}) + "\n")

                    # Decide if we need to fetch or can skip
                    if self._is_stored("pr", num):
                        path = self._stored_path("pr", num)
                        self._register_existing("pr", num, path)
                        # Still enqueue for extraction
                        self.processing_queue.enqueue(ProcessingHandoff(
                            source_id=self.source_id,
                            item_type="pr",
                            item_number=num,
                            raw_data_path=path,
                        ))
                        async with self._counter_lock:
                            self._skipped += 1
                    else:
                        self._register_queued("pr", num)
                        await queue.put(("pr", num))

                pr_scanned += len(page_nums)
                print(f"[INGEST] Scanned {pr_scanned} PRs  |  queue={queue.qsize()}  "
                      f"fetched={self._fetched}")

                if pr_limit_rem is not None and pr_limit_rem <= 0:
                    break

            mf.flush()

            # ── Issues ───────────────────────────────────────────────────────
            if not self._should_stop():
                issue_limit_rem = self.issue_limit
                async for page_nums in self.client.stream_issue_pages(repo, state="all"):
                    if self._should_stop():
                        break

                    page_nums = sorted(page_nums)
                    if issue_limit_rem is not None:
                        page_nums = page_nums[:issue_limit_rem]
                        issue_limit_rem -= len(page_nums)

                    for num in page_nums:
                        mf.write(json.dumps({"type": "issue", "number": num}) + "\n")

                        if self._is_stored("issue", num):
                            path = self._stored_path("issue", num)
                            self._register_existing("issue", num, path)
                            self.processing_queue.enqueue(ProcessingHandoff(
                                source_id=self.source_id,
                                item_type="issue",
                                item_number=num,
                                raw_data_path=path,
                            ))
                            async with self._counter_lock:
                                self._skipped += 1
                        else:
                            self._register_queued("issue", num)
                            await queue.put(("issue", num))

                    issue_scanned += len(page_nums)
                    print(f"[INGEST] Scanned {issue_scanned} issues  |  queue={queue.qsize()}  "
                          f"fetched={self._fetched}")

                    if issue_limit_rem is not None and issue_limit_rem <= 0:
                        break

        print(f"[INGEST] Discovery done — {pr_scanned} PRs + {issue_scanned} issues scanned  "
              f"(manifest: {manifest_path})")

    # ─── Fetch workers ────────────────────────────────────────────────────────

    async def _fetch_worker(self, queue: asyncio.Queue, worker_id: int) -> None:
        """
        Pulls (item_type, number) from the queue.
        Fetches full detail, stores to disk, enqueues for extraction.
        Stops on sentinel (None).
        """
        while True:
            try:
                item = await queue.get()

                if item is None:          # sentinel — stop
                    queue.task_done()
                    break

                if self._should_stop():
                    queue.task_done()
                    break

                item_type, number = item
                item_id = f"{self.source_id}_{item_type}_{number}"

                try:
                    if item_type == "pr":
                        data = await self.ingestion.fetch_pr(number)
                        path = self.storage.store_pr(self.source_id, number, data)
                    else:
                        data = await self.ingestion.fetch_issue(number)
                        path = self.storage.store_issue(self.source_id, number, data)

                    self.state.update_item_status(
                        item_id, IngestionStatus.STORED, raw_data_path=str(path)
                    )
                    self.processing_queue.enqueue(ProcessingHandoff(
                        source_id=self.source_id,
                        item_type=item_type,
                        item_number=number,
                        raw_data_path=str(path),
                    ))

                    async with self._counter_lock:
                        self._fetched += 1
                        total = self._fetched
                    if total % LOG_FETCH_EVERY == 0:
                        print(f"[FETCH]  {total} items stored  "
                              f"(queue remaining: {queue.qsize()})")

                except Exception as e:
                    logger.error(f"Failed {item_type} #{number}", error=str(e))
                    self.state.update_item_status(
                        item_id, IngestionStatus.FAILED, error=str(e)
                    )
                    async with self._counter_lock:
                        self._failed += 1

                finally:
                    queue.task_done()

                # Periodic state save (every 50 fetches across all workers)
                if self._fetched % 50 == 0:
                    self.state_manager.save_state(self.state)

            except asyncio.CancelledError:
                # Task was cancelled, exit cleanly
                break
            except Exception as e:
                logger.exception("Unexpected error in fetch worker")
                # Wait a bit to avoid tight loop on persistent errors
                await asyncio.sleep(1)

    # ─── State helpers ────────────────────────────────────────────────────────

    def _should_stop(self) -> bool:
        if self.stop_check and self.stop_check():
            if self.state:
                self.state.metadata["status"] = "stopped"
            return True
        return False

    def _is_stored(self, item_type: str, number: int) -> bool:
        """True if the raw file already exists on disk."""
        if not self.skip_existing:
            return False
        return self._stored_path(item_type, number) != "" and \
               Path(self._stored_path(item_type, number)).exists()

    def _stored_path(self, item_type: str, number: int) -> str:
        folder = "prs" if item_type == "pr" else "issues"
        return str(
            self.storage.base_path / folder / f"{number}.json"
        )

    def _register_existing(self, item_type: str, number: int, path: str) -> None:
        item_id = f"{self.source_id}_{item_type}_{number}"
        if not self.state.get_item(item_id):
            self.state.add_item(IngestionItemState(
                item_id=item_id,
                source_id=self.source_id,
                item_type=item_type,
                item_number=number,
                status=IngestionStatus.STORED,
                raw_data_path=path,
            ))

    def _register_queued(self, item_type: str, number: int) -> None:
        item_id = f"{self.source_id}_{item_type}_{number}"
        if not self.state.get_item(item_id):
            self.state.add_item(IngestionItemState(
                item_id=item_id,
                source_id=self.source_id,
                item_type=item_type,
                item_number=number,
                status=IngestionStatus.QUEUED,
            ))

    def _manifest_path(self) -> Path:
        return (
            self.state_manager.base_path / "ingestion" / f"{self.source_id}_manifest.jsonl"
        )

    # ─── Read-only helpers ────────────────────────────────────────────────────

    def get_state(self) -> Optional[IngestionSourceState]:
        return self.state

    def get_progress(self) -> dict:
        if not self.state:
            return {"source_id": self.source_id, "status": "not_started", "progress": 0.0}
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
            "metadata": self.state.metadata,
        }
