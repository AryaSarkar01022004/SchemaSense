"""
Evaluation Harness Runner.
"""

import sys
import os

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.db.repository import repository
from app.eval.harness import EvaluationHarness
from seed_demo_data import seed_demo_database


def main():
    if os.getenv("EVAL_LIVE_LLM", "0") != "1":
        settings.LLM_PROVIDER = "mock"

    conns = repository.list_connections()
    demo_conn = next((c for c in conns if c.name == "Demo E-Commerce Store"), None)
    if not demo_conn:
        conn_id = seed_demo_database()
        demo_conn = repository.get_connection(conn_id)

    harness = EvaluationHarness(demo_conn)
    results = harness.run_suite()

    if results["passed_target"]:
        print(" SUCCESS: Evaluation harness exceeded the 85% accuracy target!")
        sys.exit(0)
    else:
        print("⚠️ WARNING: Accuracy fell below 85% threshold.")
        sys.exit(1)


if __name__ == "__main__":
    main()

