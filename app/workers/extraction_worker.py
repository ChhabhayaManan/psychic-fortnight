"""Extraction worker for processing raw data into artifacts."""

import asyncio
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from app.extraction.base_extractor import BaseExtractor
from app.extraction.decisions.extractor import DecisionExtractor
from app.extraction.incidents.extractor import IncidentExtractor
from app.extraction.architecture.extractor import ArchitectureExtractor
from app.extraction.timeline.extractor import TimelineExtractor
from app.extraction.ownership.extractor import OwnershipExtractor
from app.extraction.unresolved.extractor import UnresolvedExtractor
from app.memory.json_store import JsonStore
from app.models.ingestion_state import ProcessingHandoff, ProcessingQueue
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ExtractionWorker:
    """
    Extraction worker.

    Processes raw GitHub data through LLM extraction agents to produce
    typed memory artifacts (decisions, incidents, timeline, architecture,
    ownership, unresolved questions).
    """

    def __init__(
        self,
        json_store: JsonStore,
        processing_queue: ProcessingQueue,
        extractors: Optional[List[BaseExtractor]] = None,
        max_workers: int = 3,
        max_attempts: int = 3,
        stop_check: Optional[Callable[[], bool]] = None
    ):
        """
        Initialize extraction worker.

        Args:
            json_store: JsonStore for storing extracted artifacts
            processing_queue: ProcessingQueue for raw data
            extractors: List of extractors to use (defaults to all LLM extractors)
            max_workers: Maximum concurrent workers
            max_attempts: Max retry attempts per item
            stop_check: Optional callback to check if extraction should stop
        """
        self.json_store = json_store
        self.processing_queue = processing_queue
        self.max_workers = max_workers
        self.max_attempts = max_attempts
        self.stop_check = stop_check

        # Initialize extractors
        if extractors is None:
            self.extractors = self._get_default_extractors()
        else:
            self.extractors = extractors

        logger.info(
            "Extraction worker initialized",
            extractors=len(self.extractors),
            max_workers=max_workers
        )

    def _get_default_extractors(self) -> List[BaseExtractor]:
        """Get default set of extractors (all LLM-powered)."""
        return [
            DecisionExtractor(min_confidence=0.6),
            IncidentExtractor(min_confidence=0.6),
            TimelineExtractor(min_confidence=0.5),
            ArchitectureExtractor(min_confidence=0.6),
            OwnershipExtractor(min_confidence=0.6),
            UnresolvedExtractor(min_confidence=0.6),
        ]

    async def process_queue(self, batch_size: int = 10) -> Dict[str, Any]:
        """
        Process items from the queue.

        Args:
            batch_size: Number of items to process in this batch

        Returns:
            Processing statistics
        """
        # Get items from queue
        items = self.processing_queue.peek(batch_size)

        if not items:
            return {
                "processed": 0,
                "succeeded": 0,
                "failed": 0,
                "artifacts_created": 0
            }

        logger.info(f"Processing batch -- {len(items)} items", count=len(items))

        # Process items concurrently
        semaphore = asyncio.Semaphore(self.max_workers)
        tasks = [
            self._process_item(item, semaphore)
            for item in items
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect statistics
        succeeded = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
        failed = sum(1 for r in results if isinstance(r, Exception) or
                    (isinstance(r, dict) and not r.get("success")))
        artifacts_created = sum(r.get("artifacts_created", 0) for r in results
                               if isinstance(r, dict))

        # Move completed items out of the active queue and keep failures retryable.
        for item, result in zip(items, results):
            if isinstance(result, dict) and result.get("success"):
                self.processing_queue.record_success(item)
            else:
                error = str(result)
                if isinstance(result, dict):
                    error = result.get("error", "Unknown extraction failure")
                self.processing_queue.record_failure(
                    item,
                    error,
                    max_attempts=self.max_attempts
                )

        stats = {
            "processed": len(items),
            "succeeded": succeeded,
            "failed": failed,
            "artifacts_created": artifacts_created,
            "remaining_queue": self.processing_queue.size(),
            "dead_letters": self.processing_queue.dead_letter_size()
        }

        logger.info("Batch extraction complete", **stats)

        return stats

    async def _process_item(
        self,
        handoff: ProcessingHandoff,
        semaphore: asyncio.Semaphore
    ) -> Dict[str, Any]:
        """
        Process a single item.

        Args:
            handoff: Processing handoff record
            semaphore: Semaphore for concurrency control

        Returns:
            Processing result
        """
        async with semaphore:
            try:
                logger.info(
                    f"Extracting {handoff.item_type.upper()} #{handoff.item_number}",
                    source_id=handoff.source_id
                )

                # Mark as running in queue so peek() skips it
                self._update_queue_status(handoff, "running")
                
                # Load raw data
                raw_data = self._load_raw_data(handoff.raw_data_path)
                if not raw_data:
                    return {
                        "success": False,
                        "error": "Failed to load raw data",
                        "artifacts_created": 0
                    }

                # Run all extractors
                artifacts_created = 0
                for extractor in self.extractors:
                    try:
                        artifacts = await extractor.extract(raw_data)

                        # Store extracted artifacts
                        for artifact in artifacts:
                            artifact_type = extractor.get_artifact_type()
                            self.json_store.store_artifact(artifact_type, artifact)
                            artifacts_created += 1

                            logger.debug(
                                "Artifact stored",
                                artifact_type=artifact_type,
                                artifact_id=artifact.id
                            )

                    except Exception as e:
                        logger.error(
                            f"{extractor.__class__.__name__} failed",
                            error=str(e)
                        )
                        # Continue with other extractors

                return {
                    "success": True,
                    "artifacts_created": artifacts_created
                }

            except Exception as e:
                logger.error(
                    "Failed to process item",
                    source_id=handoff.source_id,
                    item_type=handoff.item_type,
                    item_number=handoff.item_number,
                    error=str(e)
                )
                return {
                    "success": False,
                    "error": str(e),
                    "artifacts_created": 0
                }

    def _load_raw_data(self, raw_data_path: str) -> Optional[Dict[str, Any]]:
        """
        Load raw data from file.

        Args:
            raw_data_path: Path to raw data file

        Returns:
            Raw data dictionary or None if failed
        """
        try:
            path = Path(raw_data_path)
            if not path.exists():
                logger.error(f"Raw data file not found: {raw_data_path}")
                return None

            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)

        except Exception as e:
            logger.error(f"Failed to load raw data: {e}")
            return None

    def _update_queue_status(self, handoff: ProcessingHandoff, status: str) -> None:
        """Update item status in the queue file."""
        with self.processing_queue._lock:
            queue = self.processing_queue._load_queue()
            key = self.processing_queue._handoff_key(handoff.to_dict())
            for item in queue:
                if self.processing_queue._handoff_key(item) == key:
                    item["status"] = status
                    break
            self.processing_queue._save_queue(queue)

    async def process_all(self) -> Dict[str, Any]:
        """
        Process all items in the queue.

        Returns:
            Total processing statistics
        """
        total_stats = {
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "artifacts_created": 0
        }

        queue_size = self.processing_queue.size()
        print(f"\n[EXTRACT] Queue has {queue_size} item(s) to process")

        while self.processing_queue.size() > 0:
            if self.stop_check and self.stop_check():
                logger.info("Stop requested, halting extraction")
                print("[EXTRACT] 🛑 Stop requested")
                break
                
            batch_stats = await self.process_queue(batch_size=10)

            # Aggregate statistics
            for key in total_stats:
                total_stats[key] += batch_stats.get(key, 0)

        print(f"[EXTRACT] Done — processed={total_stats['processed']}  "
              f"artifacts={total_stats['artifacts_created']}  "
              f"failed={total_stats['failed']}")
        logger.info("All items processed", **total_stats)

        return total_stats


# Made with Bob
