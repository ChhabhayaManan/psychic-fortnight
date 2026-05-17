"""Knowledge graph storage using NetworkX."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    nx = None

from app.models import (
    ArchitectureChange,
    Decision,
    Incident,
    OwnershipMemory,
    Relationship,
    TimelineEvent,
    UnresolvedQuestion,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


class GraphStore:
    """
    Knowledge graph storage using NetworkX.

    Stores artifacts, entities, and relationships as a directed graph.
    """

    def __init__(self, graph_data_dir: Path):
        """
        Initialize graph store.

        Args:
            graph_data_dir: Directory for graph data storage
        """
        if not NETWORKX_AVAILABLE:
            raise ImportError(
                "networkx is not installed. Install with: pip install networkx"
            )

        self.graph_data_dir = graph_data_dir
        self.graph_data_dir.mkdir(parents=True, exist_ok=True)
        self.graph_path = self.graph_data_dir / "knowledge_graph.json"

        # Initialize or load graph
        self.graph = nx.DiGraph()
        self.load()

        logger.info("Graph store initialized", graph_path=str(self.graph_path))

    def upsert_artifact_node(
        self,
        artifact_type: str,
        artifact: Union[Decision, Incident, TimelineEvent, ArchitectureChange,
                       OwnershipMemory, UnresolvedQuestion]
    ) -> None:
        """
        Add or update artifact node in graph.

        Args:
            artifact_type: Type of artifact
            artifact: Artifact instance
        """
        node_id = artifact.id

        # Build node attributes
        attributes = {
            "node_type": "artifact",
            "artifact_type": artifact_type,
            "title": getattr(artifact, "title", ""),
            "created_at": datetime.now().isoformat()
        }

        # Add confidence if available
        if hasattr(artifact, "confidence"):
            attributes["confidence"] = float(artifact.confidence)

        # Add timestamp
        if hasattr(artifact, "timestamp"):
            timestamp = artifact.timestamp
            if isinstance(timestamp, datetime):
                attributes["timestamp"] = timestamp.isoformat()
            else:
                attributes["timestamp"] = str(timestamp)

        # Add or update node
        if self.graph.has_node(node_id):
            self.graph.nodes[node_id].update(attributes)
            logger.debug(f"Updated artifact node: {node_id}")
        else:
            self.graph.add_node(node_id, **attributes)
            logger.debug(f"Added artifact node: {node_id}")

        # Add edges to related entities
        self._add_artifact_edges(artifact_type, artifact)

        # Add provenance edges to sources
        if hasattr(artifact, "source_refs"):
            for source_ref in artifact.source_refs:
                source_node_id = f"source_{source_ref.source_type}_{source_ref.source_id}"
                self.upsert_entity_node(
                    "source",
                    source_node_id,
                    {
                        "source_type": source_ref.source_type,
                        "source_id": source_ref.source_id,
                        "url": source_ref.url,
                        "contributor": source_ref.contributor
                    }
                )
                self.graph.add_edge(
                    node_id,
                    source_node_id,
                    relation_type="sourced_from"
                )

    def upsert_entity_node(
        self,
        entity_type: str,
        entity_id: str,
        metadata: Dict[str, Any]
    ) -> None:
        """
        Add or update entity node in graph.

        Args:
            entity_type: Type of entity (service, contributor, source, etc.)
            entity_id: Entity identifier
            metadata: Entity metadata
        """
        attributes = {
            "node_type": "entity",
            "entity_type": entity_type,
            **metadata
        }

        if self.graph.has_node(entity_id):
            self.graph.nodes[entity_id].update(attributes)
            logger.debug(f"Updated entity node: {entity_id}")
        else:
            self.graph.add_node(entity_id, **attributes)
            logger.debug(f"Added entity node: {entity_id}")

    def upsert_relationship(self, relationship: Relationship) -> None:
        """
        Add or update relationship edge in graph.

        Args:
            relationship: Relationship instance
        """
        if not self.graph.has_node(relationship.source):
            self.upsert_entity_node(
                "unknown",
                relationship.source,
                {"name": relationship.source, "created_from_relationship": True}
            )

        if not self.graph.has_node(relationship.target):
            self.upsert_entity_node(
                "unknown",
                relationship.target,
                {"name": relationship.target, "created_from_relationship": True}
            )

        # Add or update edge
        self.graph.add_edge(
            relationship.source,
            relationship.target,
            relation_type=relationship.relation_type,
            confidence=float(relationship.confidence),
            description=relationship.description,
            relationship_id=relationship.id
        )

        logger.debug(
            f"Added relationship: {relationship.source} -> {relationship.target}"
        )

    def _add_artifact_edges(
        self,
        artifact_type: str,
        artifact: Union[Decision, Incident, TimelineEvent, ArchitectureChange,
                       OwnershipMemory, UnresolvedQuestion]
    ) -> None:
        """
        Add edges from artifact to related entities.

        Args:
            artifact_type: Type of artifact
            artifact: Artifact instance
        """
        artifact_id = artifact.id

        # Add edges to services
        if hasattr(artifact, "related_services"):
            for service in artifact.related_services:
                service_id = f"service_{service}"
                self.upsert_entity_node("service", service_id, {"name": service})
                self.graph.add_edge(
                    artifact_id,
                    service_id,
                    relation_type="affects"
                )

        if hasattr(artifact, "affected_services"):
            for service in artifact.affected_services:
                service_id = f"service_{service}"
                self.upsert_entity_node("service", service_id, {"name": service})
                self.graph.add_edge(
                    artifact_id,
                    service_id,
                    relation_type="affects"
                )

        # Add edges to contributors
        if hasattr(artifact, "contributors"):
            for contributor in artifact.contributors:
                contributor_id = f"contributor_{contributor}"
                self.upsert_entity_node(
                    "contributor",
                    contributor_id,
                    {"username": contributor}
                )
                self.graph.add_edge(
                    artifact_id,
                    contributor_id,
                    relation_type="contributed_by"
                )

        # Add edges to owners (for ownership artifacts)
        if hasattr(artifact, "owners"):
            for owner in artifact.owners:
                owner_id = f"contributor_{owner}"
                self.upsert_entity_node(
                    "contributor",
                    owner_id,
                    {"username": owner}
                )
                self.graph.add_edge(
                    artifact_id,
                    owner_id,
                    relation_type="owned_by"
                )

        # Add edges to related decisions/incidents
        if hasattr(artifact, "related_decisions"):
            for decision_id in artifact.related_decisions:
                if self.graph.has_node(decision_id):
                    self.graph.add_edge(
                        artifact_id,
                        decision_id,
                        relation_type="related_to"
                    )

        if hasattr(artifact, "related_incidents"):
            for incident_id in artifact.related_incidents:
                if self.graph.has_node(incident_id):
                    self.graph.add_edge(
                        artifact_id,
                        incident_id,
                        relation_type="related_to"
                    )

    def save(self) -> None:
        """Save graph to disk."""
        try:
            # Convert graph to JSON-serializable format
            data = nx.node_link_data(self.graph)

            # Save to file
            with open(self.graph_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(
                "Graph saved",
                nodes=self.graph.number_of_nodes(),
                edges=self.graph.number_of_edges(),
                path=str(self.graph_path)
            )

        except Exception as e:
            logger.error("Failed to save graph", error=str(e))
            raise

    def load(self) -> None:
        """Load graph from disk."""
        if not self.graph_path.exists():
            logger.info("No existing graph found, starting with empty graph")
            return

        try:
            with open(self.graph_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.graph = nx.node_link_graph(data, directed=True)

            logger.info(
                "Graph loaded",
                nodes=self.graph.number_of_nodes(),
                edges=self.graph.number_of_edges()
            )

        except Exception as e:
            logger.error("Failed to load graph", error=str(e))
            self.graph = nx.DiGraph()

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get graph statistics.

        Returns:
            Statistics dictionary
        """
        # Count nodes by type
        node_types = {}
        for node, attrs in self.graph.nodes(data=True):
            node_type = attrs.get("node_type", "unknown")
            node_types[node_type] = node_types.get(node_type, 0) + 1

        # Count edges by relation type
        edge_types = {}
        for _, _, attrs in self.graph.edges(data=True):
            relation_type = attrs.get("relation_type", "unknown")
            edge_types[relation_type] = edge_types.get(relation_type, 0) + 1

        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "nodes_by_type": node_types,
            "edges_by_relation": edge_types,
            "is_directed": self.graph.is_directed()
        }

    def get_neighbors(
        self,
        node_id: str,
        relation_type: Optional[str] = None
    ) -> List[str]:
        """
        Get neighbors of a node.

        Args:
            node_id: Node identifier
            relation_type: Optional relation type filter

        Returns:
            List of neighbor node IDs
        """
        if not self.graph.has_node(node_id):
            return []

        neighbors = []
        for neighbor in self.graph.neighbors(node_id):
            if relation_type:
                edge_data = self.graph.get_edge_data(node_id, neighbor)
                if edge_data and edge_data.get("relation_type") == relation_type:
                    neighbors.append(neighbor)
            else:
                neighbors.append(neighbor)

        return neighbors

    def reset(self) -> None:
        """Reset the graph (delete all nodes and edges)."""
        self.graph = nx.DiGraph()
        logger.warning("Graph reset")


# Made with Bob
