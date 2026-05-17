"""
Main entry point for the Agentic Engineering Memory System.

This is the primary entry point that launches the Streamlit UI and
initializes the autonomous processing system.
"""

import sys

from app.config import get_settings
from app.utils import get_logger, setup_logging


def main():
    """
    Main entry point for the application.

    Initializes configuration, logging, and launches the Streamlit UI.
    """
    # Load settings
    settings = get_settings()

    # Setup logging
    setup_logging(
        log_level=settings.log_level,
        log_format=settings.log_format,
        log_dir=settings.logs_dir
    )

    logger = get_logger(__name__)
    logger.info(
        "Starting Agentic Engineering Memory System",
        version="0.1.0",
        project_root=str(settings.project_root)
    )

    # Launch Streamlit UI
    try:
        import streamlit.web.cli as stcli

        ui_path = settings.project_root / "app" / "ui" / "app.py"

        logger.info("Launching Streamlit UI", ui_path=str(ui_path))

        sys.argv = [
            "streamlit",
            "run",
            str(ui_path),
            "--server.port=8501",
            "--server.address=localhost",
            "--browser.gatherUsageStats=false"
        ]

        sys.exit(stcli.main())

    except Exception as e:
        logger.exception("Failed to launch application", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()

# Made with Bob
