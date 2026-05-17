"""Configuration settings loader."""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Loads configuration from .env file and environment variables.
    Environment variables take precedence over .env file values.
    """

    # Project paths
    project_root: Path = Path(__file__).parent.parent.parent
    data_dir: Path = project_root / "data"
    projects_dir: Path = data_dir / "projects"
    raw_data_dir: Path = data_dir / "raw"
    extracted_data_dir: Path = data_dir / "extracted"
    graph_data_dir: Path = data_dir / "graph"
    embeddings_dir: Path = data_dir / "embeddings"
    state_dir: Path = data_dir / "state"
    logs_dir: Path = project_root / "logs"

    # API Keys
    watsonx_api_key: Optional[str] = None
    watsonx_project_id: Optional[str] = None
    github_token: Optional[str] = None
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None

    # LLM Configuration
    watsonx_url: str = "https://us-south.ml.cloud.ibm.com"
    llm_model: str = "meta-llama/llama-3-1-70b-instruct"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2048
    gemini_model: str = "gemini-1.5-pro"
    groq_model: str = "llama3-70b-8192"
    llm_provider: str = "Watsonx"

    # Processing Configuration
    max_workers: int = 5
    batch_size: int = 10
    rate_limit_requests: int = 100
    rate_limit_period: int = 60  # seconds
    checkpoint_interval: int = 50  # items

    # Confidence Thresholds
    min_decision_confidence: float = 0.7
    min_incident_confidence: float = 0.6
    min_relationship_confidence: float = 0.5

    # Vector Database
    chroma_persist_directory: Optional[Path] = None
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Monitoring
    enable_monitoring: bool = True
    monitoring_interval: int = 30  # seconds

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    def __init__(self, **kwargs):
        """Initialize settings and create directories."""
        super().__init__(**kwargs)

        # Set chroma directory if not specified
        chroma_directory = self.chroma_persist_directory or self.embeddings_dir / "chroma"
        self.chroma_persist_directory = chroma_directory

        # Create required directories
        self._create_directories()

    def get_project_paths(self, source_id: str) -> dict[str, Path]:
        """
        Get all data paths for a specific project.
        
        Args:
            source_id: Project identifier (e.g., 'owner_repo')
            
        Returns:
            Dictionary mapping path types to Path objects
        """
        base = self.projects_dir / source_id
        paths = {
            "base": base,
            "raw": base / "raw",
            "extracted": base / "extracted",
            "graph": base / "graph",
            "embeddings": base / "embeddings",
            "chroma": base / "embeddings" / "chroma",
            "state": base / "state",
        }
        
        # Ensure project directories exist
        for path in paths.values():
            path.mkdir(parents=True, exist_ok=True)
            
        return paths

    def _create_directories(self) -> None:
        """Create required directories if they don't exist."""
        chroma_directory = self.chroma_persist_directory or self.embeddings_dir / "chroma"
        directories = [
            self.data_dir,
            self.projects_dir,
            self.raw_data_dir,
            self.extracted_data_dir,
            self.graph_data_dir,
            self.embeddings_dir,
            self.state_dir,
            self.logs_dir,
            chroma_directory
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    @property
    def github_raw_dir(self) -> Path:
        """Get GitHub raw data directory."""
        return self.raw_data_dir / "github"

    @property
    def decisions_dir(self) -> Path:
        """Get decisions extracted data directory."""
        return self.extracted_data_dir / "decisions"

    @property
    def incidents_dir(self) -> Path:
        """Get incidents extracted data directory."""
        return self.extracted_data_dir / "incidents"

    @property
    def timeline_dir(self) -> Path:
        """Get timeline extracted data directory."""
        return self.extracted_data_dir / "timeline"


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get global settings instance.

    Creates settings instance on first call and returns cached instance
    on subsequent calls.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """
    Reload settings from environment.

    Useful for testing or when environment variables change.
    """
    global _settings
    _settings = Settings()
    return _settings

# Made with Bob
