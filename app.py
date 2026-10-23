
"""Root entry point for the implementation in truebite/."""

import runpy
import sys
from pathlib import Path

application_directory = Path(__file__).parent / "truebite"
sys.path.insert(0, str(application_directory))
runpy.run_path(str(application_directory / "app.py"), run_name="__main__")
