"""
SchemaSense API Server Launcher.
"""

import sys
import os

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import run_server
from app.config import settings

if __name__ == "__main__":
    port = int(os.environ.get("PORT", settings.PORT))
    run_server(host=settings.HOST, port=port)

