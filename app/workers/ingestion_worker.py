"""Automatic background pipeline runner."""

from typing import Any, Dict, Optional

from app.ingestion.github.workflow import GitHubIngestionWorkflow
from app.utils.logging import get_logger
from app.workers.extraction_worker import ExtractionWorker
from app.workers.indexing_worker import IndexingWorker

logger = get_logger(__name__)


class AutomaticPipelineRunner:
    """Run ingestion, extraction, and indexing as one resumable backend pipeline."""

    def __init__(
        self,
        ingestion_workflow: Optional[GitHubIngestionWorkflow] = None,
        extraction_worker: Optional[ExtractionWorker] = None,
        indexing_worker: Optional[IndexingWorker] = None,
    ):
        self.ingestion_workflow = ingestion_workflow
        self.extraction_worker = extraction_worker
        self.indexing_worker = indexing_worker

    async def run(self) -> Dict[str, Any]:
        """Run all configured pipeline stages in order."""
        results: Dict[str, Any] = {
            "ingestion": None,
            "extraction": None,
            "indexing": None,
        }

        if self.ingestion_workflow is not None:
            logger.info("Running ingestion stage")
            ingestion_state = await self.ingestion_workflow.run()
            results["ingestion"] = ingestion_state.to_dict()

        if self.extraction_worker is not None:
            logger.info("Running extraction stage")
            results["extraction"] = await self.extraction_worker.process_all()

        if self.indexing_worker is not None:
            logger.info("Running indexing stage")
            results["indexing"] = await self.indexing_worker.index_all_artifacts()

        return results

