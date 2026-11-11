"""
Prompt Builder (Section 5.3 - Stages 1 & 3).
- Stage 1: Resolves follow-up questions to standalone questions using prior conversation context.
- Stage 3: Constructs the system prompt and user prompt enforcing:
  * Strict dialect compliance (Postgres / MySQL / SQLite)
  * Read-only SELECT enforcement
  * Explicit column lists (forbids SELECT *)
  * Enforcing LIMIT for non-aggregated results
  * ISO date handling relative to provided current timestamp
  * Schema context and few-shot examples from thumbs-up queries
"""

from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from app.db.models import Message


class PromptBuilder:
    @staticmethod
    def build_system_prompt(dialect: str = "postgres") -> str:
        current_date_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        return f"""You are SchemaSense, an expert database AI engineer.
Your task is to translate natural language questions into safe, accurate SQL queries for {dialect.upper()}.

MANDATORY RULES:
1. DIALECT: Output valid {dialect.upper()} SQL.
2. READ-ONLY: Output ONLY 'SELECT' or 'WITH ... SELECT' queries. NEVER produce INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, GRANT, or other DML/DDL.
3. EXPLICIT COLUMNS: Always list explicit column names (e.g. SELECT orders.id, orders.total_amount). NEVER USE 'SELECT *'.
4. LIMIT: For any query returning raw rows or non-aggregated lists, ALWAYS specify a reasonable LIMIT (default 100, max 1000).
5. DATE HANDLING: Today's reference date is {current_date_iso}. Interpret relative terms ('last month', 'this year', 'yesterday') relative to this date using standard SQL date functions.
6. ASSUMPTIONS: Note any ambiguity or interpretation choices in the 'assumptions' array.
7. CLARIFICATION: If the question is truly impossible to answer or requires missing parameters, set 'needs_clarification' to true and ask a concise 'clarifying_question'.

OUTPUT CONTRACT:
You must respond with valid JSON matching this exact structure:
{{
  "sql": "SELECT ...",
  "tables_used": ["table_a", "table_b"],
  "assumptions": ["Interpreted 'last month' as previous calendar month"],
  "needs_clarification": false,
  "clarifying_question": null
}}
"""

    @staticmethod
    def build_user_prompt(
        question: str,
        compact_schema: str,
        few_shot_examples: Optional[List[Dict[str, str]]] = None
    ) -> str:
        parts = []
        
        parts.append("### DATABASE SCHEMA CONTEXT:")
        parts.append(compact_schema)
        parts.append("")
        
        if few_shot_examples:
            parts.append("### RELEVANT PAST VERIFIED EXAMPLES:")
            for ex in few_shot_examples[:3]:
                parts.append(f"Question: {ex['question']}")
                parts.append(f"SQL: {ex['sql']}")
                parts.append("")
                
        parts.append("### USER QUESTION:")
        parts.append(question)
        parts.append("")
        parts.append("Generate the JSON response matching the output contract now.")
        
        return "\n".join(parts)

    @staticmethod
    def build_follow_up_prompt(current_question: str, history: List[Message]) -> str:
        """
        Stage 1: Prompts LLM to resolve a follow-up question (e.g., 'now by region')
        into a standalone question given the last 3 questions and their SQL.
        """
        recent = [m for m in history if m.question][-3:]
        if not recent:
            return current_question

        context_lines = []
        for i, m in enumerate(recent, 1):
            context_lines.append(f"Q{i}: {m.question}")
            if m.validated_sql or m.generated_sql:
                context_lines.append(f"SQL{i}: {m.validated_sql or m.generated_sql}")

        return f"""Given the following recent conversation history:
{chr(10).join(context_lines)}

The user asks a follow-up question:
"{current_question}"

Rewrite this follow-up as a complete, standalone question that incorporates all necessary context from prior turns. Return ONLY the standalone question as a single plain-text line."""

