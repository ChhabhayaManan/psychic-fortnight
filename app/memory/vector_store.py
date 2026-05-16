"""Vector storage using ChromaDB."""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None

from app.models import (
    ArchitectureChange,
    Decision,
    Incident,
    OwnershipMemory,
    TimelineEvent,
    UnresolvedQuestion,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


class VectorStore:
    """
    Vector storage using ChromaDB.

    Stores artifact embeddings with metadata for semantic search.
    """

    def __init__(
        self,
        persist_directory: Path,
        collection_name: str = "engineering_memory"
    ):
        """
        Initialize vector store.

        Args:
            persist_directory: Directory for ChromaDB persistence
            collection_name: Name of the collection
        """
        if not CHROMADB_AVAILABLE:
            raise ImportError(
                "chromadb is not installed. Install with: pip install chromadb"
            )

        self.persist_directory = persist_directory
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Engineering memory artifacts"}
        )

        logger.info(
            "Vector store initialized",
            persist_directory=str(persist_directory),
            collection=collection_name
        )

    def upsert_artifact(
        self,
        artifact_type: str,
        artifact: Union[Decision, Incident, TimelineEvent, ArchitectureChange,
                       OwnershipMemory, UnresolvedQuestion]
    ) -> None:
        """
        Upsert artifact to vector store.

        Args:
            artifact_type: Type of artifact
            artifact: Artifact instance
        """
        try:
            # Generate embedding text
            embedding_text = self._get_embedding_text(artifact)

            # Build metadata
            metadata = self._build_metadata(artifact_type, artifact)

            # Upsert to collection
            self.collection.upsert(
                ids=[artifact.id],
                documents=[embedding_text],
                metadatas=[metadata]
            )

            logger.info(
                "Artifact upserted to vector store",
                artifact_type=artifact_type,
                artifact_id=artifact.id
            )

        except Exception as e:
            logger.error(
                "Failed to upsert artifact",
                artifact_type=artifact_type,
                artifact_id=artifact.id,
                error=str(e)
            )
            raise

    def delete_artifact(self, artifact_type: str, artifact_id: str) -> None:
        """
        Delete artifact from vector store.

        Args:
            artifact_type: Type of artifact
            artifact_id: Artifact ID
        """
        try:
            self.collection.delete(ids=[artifact_id])

            logger.info(
                "Artifact deleted from vector store",
                artifact_type=artifact_type,
                artifact_id=artifact_id
            )

        except Exception as e:
            logger.error(
                "Failed to delete artifact",
                artifact_type=artifact_type,
                artifact_id=artifact_id,
                error=str(e)
            )

    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get collection statistics.

        Returns:
            Statistics dictionary
        """
        try:
            count = self.collection.count()

            return {
                "collection_name": self.collection_name,
                "total_vectors": count,
                "persist_directory": str(self.persist_directory)
            }

        except Exception as e:
            logger.error("Failed to get collection stats", error=str(e))
            return {
                "collection_name": self.collection_name,
                "total_vectors": 0,
                "error": str(e)
            }

    def search(
        self,
        query: str,
        n_results: int = 10,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar artifacts.

        Args:
            query: Search query
            n_results: Number of results to return
            filter_metadata: Optional metadata filter

        Returns:
            List of search results
        """
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=filter_metadata
            )

            # Format results
            formatted_results = []
            if results and results['ids']:
                for i, artifact_id in enumerate(results['ids'][0]):
                    formatted_results.append({
                        "id": artifact_id,
                        "distance": results['distances'][0][i] if 'distances' in results else None,
                        "metadata": results['metadatas'][0][i] if 'metadatas' in results else {},
                        "document": results['documents'][0][i] if 'documents' in results else ""
                    })

            return formatted_results

        except Exception as e:
            logger.error("Search failed", error=str(e))
            return []

    def _get_embedding_text(
        self,
        artifact: Union[Decision, Incident, TimelineEvent, ArchitectureChange,
                       OwnershipMemory, UnresolvedQuestion]
    ) -> str:
        """
        Get embedding text from artifact.

        Args:
            artifact: Artifact instance

        Returns:
            Embedding text
        """
        if hasattr(artifact, 'to_embedding_text'):
            return artifact.to_embedding_text()

        # Fallback: use title and summary
        text_parts = []
        if hasattr(artifact, 'title'):
            text_parts.append(artifact.title)
        if hasattr(artifact, 'summary'):
            text_parts.append(artifact.summary)

        return "\n\n".join(text_parts)

    def _build_metadata(
        self,
        artifact_type: str,
        artifact: Union[Decision, Incident, TimelineEvent, ArchitectureChange,
                       OwnershipMemory, UnresolvedQuestion]
    ) -> Dict[str, Any]:
        """
        Build metadata for vector storage.

        Args:
            artifact_type: Type of artifact
            artifact: Artifact instance

        Returns:
            Metadata dictionary
        """
        metadata = {
            "artifact_type": artifact_type,
            "artifact_id": artifact.id,
            "title": getattr(artifact, "title", ""),
        }

        # Add confidence if available
        if hasattr(artifact, "confidence"):
            metadata["confidence"] = float(artifact.confidence)

        # Add source information
        if hasattr(artifact, "source_refs") and artifact.source_refs:
            metadata["source_count"] = len(artifact.source_refs)
            metadata["primary_source_url"] = artifact.source_refs[0].url
            metadata["source_id"] = artifact.source_refs[0].source_id

            # Add raw data path if available
            if artifact.source_refs[0].raw_data_path:
                metadata["raw_data_path"] = artifact.source_refs[0].raw_data_path

        # Add timestamp
        if hasattr(artifact, "timestamp"):
            timestamp = artifact.timestamp
            if isinstance(timestamp, datetime):
                metadata["timestamp"] = timestamp.isoformat()
            else:
                metadata["timestamp"] = str(timestamp)

        # Add type-specific metadata
        if hasattr(artifact, "severity"):
            metadata["severity"] = artifact.severity

        if hasattr(artifact, "status"):
            metadata["status"] = artifact.status

        if hasattr(artifact, "event_type"):
            metadata["event_type"] = artifact.event_type

        if hasattr(artifact, "change_type"):
            metadata["change_type"] = artifact.change_type

        if hasattr(artifact, "entity_type"):
            metadata["entity_type"] = artifact.entity_type

        return metadata

    def reset(self) -> None:
        """Reset the collection (delete all vectors)."""
        try:
            self.client.delete_collection(name=self.collection_name)
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "Engineering memory artifacts"}
            )
            logger.warning("Vector store collection reset")
        except Exception as e:
            logger.error("Failed to reset collection", error=str(e))


# Made with Bob
