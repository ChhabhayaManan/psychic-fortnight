"""
Main Streamlit entry point for the Engineering Memory System.
Used for deployment and local execution.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import and run the Home page
from app.ui.Home import main

if __name__ == "__main__":
    main()
