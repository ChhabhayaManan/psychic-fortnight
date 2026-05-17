"""Indexing worker for updating vector and graph stores."""

from typing import Any, Dict, Optional

from app.memory.graph_store import GraphStore
from app.memory.json_store import JsonStore
from app.memory.vector_store import VectorStore
from app.utils.logging import get_logger

logger = get_logger(__name__)


class IndexingWorker:
    """
    Indexing worker.

    Updates vector store, graph store after
    artifacts are extracted and stored.
    """

    def __init__(
        self,
        json_store: JsonStore,
        vector_store: Optional[VectorStore] = None,
        graph_store: Optional[GraphStore] = None,
        stop_check: Optional[Callable[[], bool]] = None
    ):
        """
        Initialize indexing worker.

        Args:
            json_store: JsonStore for reading artifacts
            vector_store: VectorStore for embeddings (optional)
            graph_store: GraphStore for relationships (optional)
            stop_check: Optional callback to check if indexing should stop
        """
        self.json_store = json_store
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.stop_check = stop_check

        logger.info(
            "Indexing worker initialized",
            has_vector_store=vector_store is not None,
            has_graph_store=graph_store is not None,
        )

    async def index_all_artifacts(self) -> Dict[str, Any]:
        """
        Index all artifacts from JSON store.

        Returns:
            Indexing statistics
        """
        logger.info("Starting full indexing")

        stats = {
            "total_artifacts": 0,
            "vector_indexed": 0,
            "graph_indexed": 0,
            "vector_failed": 0,
            "graph_failed": 0,
            "failures": [],
        }

        # Get all artifact types
        artifact_types = [
            "decisions",
            "incidents",
            "timeline",
            "architecture",
            "ownership",
            "unresolved",
            "relationships"
        ]

        # Index each type
        for artifact_type in artifact_types:
            type_stats = await self.index_artifact_type(artifact_type)
            stats["total_artifacts"] += type_stats.get("count", 0)
            stats["vector_indexed"] += type_stats.get("vector_indexed", 0)
            stats["graph_indexed"] += type_stats.get("graph_indexed", 0)
            stats["vector_failed"] += type_stats.get("vector_failed", 0)
            stats["graph_failed"] += type_stats.get("graph_failed", 0)
            stats["failures"].extend(type_stats.get("failures", []))

        logger.info("Full indexing complete", **stats)

        return stats

    async def index_artifact_type(self, artifact_type: str) -> Dict[str, Any]:
        """
        Index all artifacts of a given type.

        Args:
            artifact_type: Type of artifact to index

        Returns:
            Indexing statistics for this type
        """
        stats = {
            "count": 0,
            "vector_indexed": 0,
            "graph_indexed": 0,
            "vector_failed": 0,
            "graph_failed": 0,
            "failures": []
        }

        try:
            # Get all artifact IDs
            artifact_ids = self.json_store.list_artifacts(artifact_type)
            stats["count"] = len(artifact_ids)

            if not artifact_ids:
                return stats

            logger.info(f"Indexing {artifact_type} -- {len(artifact_ids)} items", count=len(artifact_ids))

            # Index each artifact
            for artifact_id in artifact_ids:
                if self.stop_check and self.stop_check():
                    logger.info("Stop requested, halting indexing")
                    break
                    
                try:
                    # Load artifact
                    artifact = self.json_store.get_artifact(artifact_type, artifact_id)
                    if not artifact:
                        continue

                    # Index to vector store
                    if self.vector_store:
                        try:
                            self.vector_store.upsert_artifact(artifact_type, artifact)
                            stats["vector_indexed"] += 1
                        except Exception as e:
                            stats["vector_failed"] += 1
                            stats["failures"].append({
                                "artifact_type": artifact_type,
                                "artifact_id": artifact_id,
                                "stage": "vector",
                                "error": str(e)
                            })
                            logger.error(
                                "Vector indexing failed",
                                artifact_id=artifact_id,
                                error=str(e)
                            )

                    # Index to graph store
                    if self.graph_store:
                        try:
                            if artifact_type == "relationships":
                                self.graph_store.upsert_relationship(artifact)
                            else:
                                self.graph_store.upsert_artifact_node(artifact_type, artifact)
                            stats["graph_indexed"] += 1
                        except Exception as e:
                            stats["graph_failed"] += 1
                            stats["failures"].append({
                                "artifact_type": artifact_type,
                                "artifact_id": artifact_id,
                                "stage": "graph",
                                "error": str(e)
                            })
                            logger.error(
                                "Graph indexing failed",
                                artifact_id=artifact_id,
                                error=str(e)
                            )

                except Exception as e:
                    logger.error(
                        "Indexing failed",
                        artifact_id=artifact_id,
                        error=str(e)
                    )

            # Save graph if updated
            if self.graph_store and stats["graph_indexed"] > 0:
                self.graph_store.save()

            logger.info(
                f"Indexed {artifact_type} complete",
                count=stats["count"],
                vector_indexed=stats["vector_indexed"],
                graph_indexed=stats["graph_indexed"]
            )

        except Exception as e:
            logger.error(f"Failed to index {artifact_type}", error=str(e))

        return stats

    async def index_artifact(
        self,
        artifact_type: str,
        artifact_id: str
    ) -> bool:
        """
        Index a single artifact.

        Args:
            artifact_type: Type of artifact
            artifact_id: Artifact ID

        Returns:
            True if successful, False otherwise
        """
        try:
            # Load artifact
            artifact = self.json_store.get_artifact(artifact_type, artifact_id)
            if not artifact:
                logger.warning(
                    "Artifact not found",
                    artifact_type=artifact_type,
                    artifact_id=artifact_id
                )
                return False

            # Index to vector store
            if self.vector_store:
                self.vector_store.upsert_artifact(artifact_type, artifact)

            # Index to graph store
            if self.graph_store:
                if artifact_type == "relationships":
                    self.graph_store.upsert_relationship(artifact)
                else:
                    self.graph_store.upsert_artifact_node(artifact_type, artifact)
                self.graph_store.save()

            logger.info(
                "Artifact indexed",
                artifact_type=artifact_type,
                artifact_id=artifact_id
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to index artifact",
                artifact_type=artifact_type,
                artifact_id=artifact_id,
                error=str(e)
            )
            return False

