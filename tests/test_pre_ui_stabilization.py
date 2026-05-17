import asyncio
import importlib
import json
from datetime import datetime

import pytest


def test_settings_load_without_llm_environment(monkeypatch):
    monkeypatch.delenv("WATSONX_API_KEY", raising=False)
    monkeypatch.delenv("WATSONX_PROJECT_ID", raising=False)
    settings_module = importlib.import_module("app.config.settings")
    settings_module._settings = None

    # Force skip .env file loading for test isolation
    settings = settings_module.Settings(_env_file=None)
    settings_module._settings = settings

    assert settings.watsonx_api_key is None
    assert settings.watsonx_project_id is None


def test_llm_readiness_reports_missing_credentials(monkeypatch):
    monkeypatch.delenv("WATSONX_API_KEY", raising=False)
    monkeypatch.delenv("WATSONX_PROJECT_ID", raising=False)
    settings_module = importlib.import_module("app.config.settings")
    settings_module._settings = settings_module.Settings(_env_file=None)
    llm_module = importlib.import_module("app.config.llm_config")
    llm_module._llm_config = None

    llm_config = llm_module.get_llm_config()

    assert llm_config.validate_llm_ready() is False
    with pytest.raises(RuntimeError, match="Watsonx credentials"):
        llm_config.get_summarization_llm()


def test_raw_storage_metadata_includes_raw_data_path(tmp_path):
    from app.memory.raw_storage import RawDataStorage

    storage = RawDataStorage(tmp_path / "raw")
    path = storage.store_pr(
        "acme_project",
        12,
        {
            "source": {"type": "github", "repository": "acme/project", "pr_number": 12},
            "metadata": {"title": "Adopt gRPC"},
        },
    )

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["_storage_metadata"]["raw_data_path"] == str(path)


def test_processing_queue_dedupes_retries_and_dead_letters(tmp_path):
    from app.models.ingestion_state import ProcessingHandoff, ProcessingQueue

    queue = ProcessingQueue(tmp_path / "state")
    handoff = ProcessingHandoff(
        source_id="acme_project",
        item_type="pr",
        item_number=1,
        raw_data_path="data/raw/github/acme_project/prs/1.json",
    )

    queue.enqueue(handoff)
    queue.enqueue(handoff)
    assert queue.size() == 1

    queued = queue.peek(1)[0]
    queue.record_failure(queued, "missing file", max_attempts=2)
    retry_item = queue.peek(1)[0]
    assert retry_item.attempt_count == 1
    assert retry_item.last_error == "missing file"
    assert retry_item.dead_letter is False
    assert queue.size() == 1

    queue.record_failure(retry_item, "still missing", max_attempts=2)
    assert queue.size() == 0
    assert queue.dead_letter_size() == 1
    assert queue.peek_dead_letters(1)[0].dead_letter is True


def test_extraction_worker_preserves_failed_items_for_retry(tmp_path):
    from app.memory.json_store import JsonStore
    from app.models.ingestion_state import ProcessingHandoff, ProcessingQueue
    from app.workers.extraction_worker import ExtractionWorker

    queue = ProcessingQueue(tmp_path / "state")
    queue.enqueue(
        ProcessingHandoff(
            source_id="acme_project",
            item_type="pr",
            item_number=3,
            raw_data_path=str(tmp_path / "missing.json"),
        )
    )
    worker = ExtractionWorker(JsonStore(tmp_path / "extracted"), queue, max_attempts=2)

    stats = asyncio.run(worker.process_queue(batch_size=1))

    assert stats["failed"] == 1
    assert queue.size() == 1
    assert queue.peek(1)[0].attempt_count == 1


def test_indexing_worker_reports_vector_failures(tmp_path):
    from app.memory.json_store import JsonStore
    from app.models import Decision, SourceReference, SourceType
    from app.workers.indexing_worker import IndexingWorker

    class FailingVectorStore:
        def upsert_artifact(self, artifact_type, artifact):
            raise RuntimeError("vector offline")

    source = SourceReference(
        source_type=SourceType.PR,
        source_id="5",
        url="https://github.com/acme/project/pull/5",
        contributor="alice",
        timestamp=datetime(2024, 1, 1),
    )
    store = JsonStore(tmp_path / "extracted")
    decision = Decision(
        id="dec_1",
        title="Adopt gRPC",
        summary="The team adopted gRPC for internal calls.",
        reasoning="REST payload drift was causing runtime issues.",
        confidence=0.9,
        source_refs=[source],
    )
    store.store_artifact("decisions", decision)

    stats = asyncio.run(
        IndexingWorker(store, vector_store=FailingVectorStore()).index_artifact_type("decisions")
    )

    assert stats["count"] == 1
    assert stats["vector_indexed"] == 0
    assert stats["vector_failed"] == 1
    assert stats["failures"][0]["artifact_id"] == "dec_1"


def test_default_extraction_worker_exposes_all_artifact_lanes(tmp_path):
    from app.memory.json_store import JsonStore
    from app.models.ingestion_state import ProcessingQueue
    from app.workers.extraction_worker import ExtractionWorker

    worker = ExtractionWorker(
        JsonStore(tmp_path / "extracted"),
        ProcessingQueue(tmp_path / "state"),
    )

    assert {extractor.get_artifact_type() for extractor in worker.extractors} == {
        "decision",
        "incident",
        "timeline",
        "architecture",
        "ownership",
        "unresolved",
        "relationship",
    }


def test_ingestion_workflow_requeues_failed_items_on_resume(tmp_path):
    from app.ingestion.github.workflow import GitHubIngestionWorkflow
    from app.memory.raw_storage import RawDataStorage
    from app.models.ingestion import IngestionItem
    from app.models.ingestion_state import (
        IngestionItemState,
        IngestionSourceState,
        IngestionStateManager,
        IngestionStatus,
        ProcessingQueue,
    )

    state_manager = IngestionStateManager(tmp_path / "state")
    processing_queue = ProcessingQueue(tmp_path / "state")
    state = IngestionSourceState(
        source_id="acme_project",
        repository="acme/project",
        discovered_at=datetime(2024, 1, 1).isoformat(),
        pr_count=1,
        total_count=1,
    )
    state.add_item(
        IngestionItemState(
            item_id="acme_project_pr_1",
            source_id="acme_project",
            item_type="pr",
            item_number=1,
            status=IngestionStatus.FAILED,
            error="network dropped",
        )
    )

    workflow = GitHubIngestionWorkflow(
        owner="acme",
        repo="project",
        client=object(),
        storage=RawDataStorage(tmp_path / "raw"),
        state_manager=state_manager,
        processing_queue=processing_queue,
    )
    workflow.state = state

    # Simulate requeueing a failed item
    item_id = "acme_project_pr_1"
    workflow._register_queued("pr", 1)

    assert workflow.state.get_item(item_id).status == IngestionStatus.QUEUED
    assert workflow.state.get_item(item_id).error is None
