"""
Self-Healing Repair Loop (Section 5.6).
When SQL validation or execution fails (syntax error, unknown column, type mismatch):
- Sends the model: original question, schema context, failed SQL, and sanitized error message.
- Allows at most 2 retries.
- Logs each attempt.
- If still failing, returns friendly error explanation + last SQL for manual editing in the UI.
"""

from typing import Dict, Any, Tuple
from app.services.llm_client import llm_client
from app.config import settings


class RepairLoop:
    def __init__(self, max_retries: int = None):
        self.max_retries = max_retries or settings.MAX_REPAIR_RETRIES

    def repair_sql(
        self,
        question: str,
        schema_context: str,
        failed_sql: str,
        error_message: str,
        attempt: int,
        dialect: str = "postgres"
    ) -> Dict[str, Any]:
        """
        Generates a repaired SQL query addressing the specific error encountered.
        """
        system_prompt = f"""You are fixing a broken SQL query for {dialect.upper()}.
MANDATORY RULES:
- Output ONLY valid JSON matching the contract: {{"sql": "...", "tables_used": [...], "assumptions": [...], "needs_clarification": false, "clarifying_question": null}}
- Strictly fix the specific error described.
- Maintain read-only SELECT rules.
"""
        repair_user_prompt = f"""### SCHEMA CONTEXT:
{schema_context}

### ORIGINAL QUESTION:
{question}

### FAILED SQL (Attempt {attempt} of {self.max_retries}):
{failed_sql}

### SANITIZED ERROR MESSAGE:
{error_message}

Please fix the SQL query to resolve this error. Return the corrected JSON response."""

        repaired_response = llm_client.generate_sql_response(
            system_prompt,
            repair_user_prompt,
            question,
            schema_context
        )
        return repaired_response


repair_loop = RepairLoop()

