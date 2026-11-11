"""
SchemaSense API Server Launcher.
"""

import sys
import os

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import run_server
from app.config import settings
from app.db.repository import repository
from seed_demo_data import seed_demo_database


def ensure_demo_seeded():
    """Seed the sample e-commerce SQLite database on first boot if no connections exist."""
    try:
        if not repository.list_connections():
            seed_demo_database(db_path=settings.DEMO_DB_PATH)
    except Exception as exc:
        print(f"Warning: demo seed skipped ({exc})")


if __name__ == "__main__":
    ensure_demo_seeded()
    port = int(os.environ.get("PORT", settings.PORT))
    run_server(host=settings.HOST, port=port)

