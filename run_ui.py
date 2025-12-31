#!/usr/bin/env python
"""
Launcher script for Housewife AI web UI.
Starts the Streamlit application.
"""

import subprocess
import sys

if __name__ == "__main__":
    subprocess.run([sys.executable, "-m", "streamlit", "run", "cookplanner/ui/app.py"])
