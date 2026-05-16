"""Processing configuration and constants."""

from enum import Enum
from typing import Any, Dict, Optional

from .settings import get_settings


class ProcessingMode(str, Enum):
    """Processing modes for autonomous operation."""
    FULL_SCAN = "full_scan"  # Process all data from source
    INCREMENTAL = "incremental"  # Process only new data
    BACKFILL = "backfill"  # Fill gaps in existing data
    MONITORING = "monitoring"  # Continuous monitoring mode


class ExtractionType(str, Enum):
    """Types of extraction operations."""
    DECISION = "decision"
    INCIDENT = "incident"
    TIMELINE = "timeline"
    RELATIONSHIP = "relationship"
    OWNERSHIP = "ownership"


class ProcessingConfig:
    """
    Processing configuration and constants.

    Centralizes processing-related configuration including batch sizes,
    timeouts, retry policies, and extraction settings.
    """

    def __init__(self):
        """Initialize processing configuration."""
        self.settings = get_settings()

    # Batch Processing
    @property
    def batch_size(self) -> int:
        """Number of items to process in a single batch."""
        return int(self.settings.batch_size)

    @property
    def max_workers(self) -> int:
        """Maximum number of concurrent workers."""
        return int(self.settings.max_workers)

    @property
    def checkpoint_interval(self) -> int:
        """Number of items between checkpoints."""
        return int(self.settings.checkpoint_interval)

    # Rate Limiting
    @property
    def rate_limit_requests(self) -> int:
        """Maximum requests per period."""
        return int(self.settings.rate_limit_requests)

    @property
    def rate_limit_period(self) -> int:
        """Rate limit period in seconds."""
        return int(self.settings.rate_limit_period)

    # Retry Configuration
    @property
    def max_retries(self) -> int:
        """Maximum number of retry attempts."""
        return 3

    @property
    def retry_delay(self) -> int:
        """Initial retry delay in seconds."""
        return 5

    @property
    def retry_backoff(self) -> float:
        """Exponential backoff multiplier."""
        return 2.0

    # Timeouts
    @property
    def api_timeout(self) -> int:
        """API request timeout in seconds."""
        return 30

    @property
    def extraction_timeout(self) -> int:
        """Extraction operation timeout in seconds."""
        return 120

    @property
    def processing_timeout(self) -> int:
        """Overall processing timeout in seconds."""
        return 300

    # Confidence Thresholds
    @property
    def min_decision_confidence(self) -> float:
        """Minimum confidence for decision extraction."""
        return float(self.settings.min_decision_confidence)

    @property
    def min_incident_confidence(self) -> float:
        """Minimum confidence for incident extraction."""
        return float(self.settings.min_incident_confidence)

    @property
    def min_relationship_confidence(self) -> float:
        """Minimum confidence for relationship extraction."""
        return float(self.settings.min_relationship_confidence)

    # Extraction Settings
    @property
    def extraction_settings(self) -> Dict[str, Any]:
        """Get extraction-specific settings."""
        return {
            "decision": {
                "min_confidence": self.min_decision_confidence,
                "require_reasoning": True,
                "min_description_length": 50,
                "extract_related_services": True
            },
            "incident": {
                "min_confidence": self.min_incident_confidence,
                "require_root_cause": True,
                "require_resolution": False,  # May not be resolved yet
                "extract_affected_services": True
            },
            "timeline": {
                "min_confidence": 0.5,
                "group_related_events": True,
                "max_events_per_day": 50
            },
            "relationship": {
                "min_confidence": self.min_relationship_confidence,
                "bidirectional": True,
                "infer_implicit": True
            }
        }

    # Discovery Settings
    @property
    def discovery_settings(self) -> Dict[str, Any]:
        """Get discovery agent settings."""
        return {
            "scan_interval": 300,  # 5 minutes
            "max_items_per_scan": 100,
            "prioritize_recent": True,
            "include_closed": True,
            "lookback_days": 365
        }

    # Monitoring Settings
    @property
    def monitoring_settings(self) -> Dict[str, Any]:
        """Get monitoring settings."""
        return {
            "enabled": self.settings.enable_monitoring,
            "interval": self.settings.monitoring_interval,
            "track_metrics": True,
            "alert_on_errors": True,
            "max_error_rate": 0.1  # 10%
        }

    # Queue Settings
    @property
    def queue_settings(self) -> Dict[str, Any]:
        """Get queue management settings."""
        return {
            "max_queue_size": 1000,
            "priority_levels": 3,
            "requeue_on_failure": True,
            "max_requeue_attempts": 3
        }


# Global processing config instance
_processing_config: Optional[ProcessingConfig] = None


def get_processing_config() -> ProcessingConfig:
    """
    Get global processing config instance.

    Returns:
        Global ProcessingConfig instance
    """
    global _processing_config
    if _processing_config is None:
        _processing_config = ProcessingConfig()
    return _processing_config

# Made with Bob
