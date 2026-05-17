"""
Streamlit Cloud entry point for Engineering Memory Knowledge.
This file delegates to app.py which contains the full single-page UI.

Select this file (streamlit_app.py) when deploying on Streamlit Cloud.
"""

import runpy
from pathlib import Path

# Run app.py from the same directory as this file
runpy.run_path(str(Path(__file__).parent / "app.py"), run_name="__main__")
