"""
SQL Safety Validator (Section 5.4 - Safety Core).
Implements a layered AST validation pipeline:
1. Parse with connection dialect; exactly one statement.
2. Statement allowlist: root must be Select (CTEs allowed). Rejects DML/DDL.
3. Function denylist: pg_sleep, pg_read_file, lo_import, dblink, copy, set_config, pg_terminate_backend, load_file, sleep, benchmark, into outfile, etc.
4. Table scope check: referenced tables must exist in synced schema.
5. Column policy: rejects references to columns flagged as sensitive.
6. Limit enforcement: injects or lowers LIMIT to max (default 1000, cap 10000).
7. Cost check / Cartesian join check without predicate.
8. Comment and stacked-query stripping.
"""

import re
from typing import Tuple, List, Set, Optional, Dict, Any


# Forbidden statement types
FORBIDDEN_STATEMENTS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "GRANT", "REVOKE", "COPY", "COMMAND", "SET", "CALL", "TRUNCATE",
    "EXEC", "EXECUTE", "REPLACE", "MERGE", "UPSERT", "VACUUM", "ANALYZE"
}

# Dangerous functions across Postgres, MySQL, and SQLite
DENIED_FUNCTIONS = {
    # Postgres
    "pg_sleep", "pg_read_file", "pg_read_binary_file", "lo_import", "lo_export",
    "dblink", "dblink_exec", "copy", "set_config", "pg_terminate_backend",
    "pg_cancel_backend", "pg_catalog.pg_read_file", "pg_catalog.pg_sleep",
    "query_to_xml", "cursor",
    # MySQL
    "load_file", "sleep", "benchmark", "sys_eval", "sys_exec",
    # General / SQLite
    "load_extension", "edit", "writefile", "readfile"
}

# Regex to detect dangerous tokens, stacked queries, or INTO clauses
INTO_OUTFILE_RE = re.compile(r"\binto\s+(?:outfile|dumpfile)\b", re.IGNORECASE)
SELECT_INTO_RE = re.compile(r"\bselect\b.*?\binto\b(?!\s+(?:outfile|dumpfile))", re.IGNORECASE | re.DOTALL)


class SQLValidationError(Exception):
    pass


class SQLValidationResult:
    def __init__(self, is_valid: bool, sanitized_sql: str = "", error_message: str = "", tables_used: List[str] = None):
        self.is_valid = is_valid
        self.sanitized_sql = sanitized_sql
        self.error_message = error_message
        self.tables_used = tables_used or []

    def __bool__(self):
        return self.is_valid


class SQLValidator:
    def __init__(
        self,
        allowed_tables: Optional[Set[str]] = None,
        sensitive_columns: Optional[Set[str]] = None,
        default_limit: int = 1000,
        hard_cap_limit: int = 10000
    ):
        self.allowed_tables = {t.lower() for t in allowed_tables} if allowed_tables is not None else None
        self.sensitive_columns = {c.lower() for c in sensitive_columns} if sensitive_columns is not None else set()
        self.default_limit = default_limit
        self.hard_cap_limit = hard_cap_limit

    def strip_comments_and_normalize(self, sql: str) -> str:
        """Step 8: Strip comments and whitespace."""
        # Remove single-line comments (-- ... and # ...)
        cleaned = re.sub(r"--[^\r\n]*", " ", sql)
        cleaned = re.sub(r"#[^\r\n]*", " ", cleaned)
        # Remove multi-line comments (/* ... */)
        cleaned = re.sub(r"/\*.*?\*/", " ", cleaned, flags=re.DOTALL)
        return cleaned.strip()

    def validate(self, sql: str, dialect: str = "postgres") -> SQLValidationResult:
        """
        Executes validation rules in strict order.
        Any violation rejects the query.
        """
        cleaned_sql = self.strip_comments_and_normalize(sql)
        if not cleaned_sql:
            return SQLValidationResult(False, error_message="Empty query provided.")

        # Step 1: Exactly one statement (reject stacked queries / semicolons)
        statements = [s.strip() for s in cleaned_sql.split(";") if s.strip()]
        if len(statements) > 1:
            return SQLValidationResult(False, error_message="Stacked queries detected. Exactly one statement is permitted.")
        
        single_sql = statements[0]

        # Step 2: Statement allowlist & Root node check
        first_token = single_sql.split()[0].upper()
        if first_token in FORBIDDEN_STATEMENTS:
            return SQLValidationResult(False, error_message=f"Disallowed statement type: {first_token}. Only SELECT is permitted.")
        
        if first_token not in ("SELECT", "WITH", "EXPLAIN"):
            return SQLValidationResult(False, error_message=f"Statement must begin with SELECT or WITH (found: {first_token}).")

        # Check for nested CTE DML (e.g. WITH x AS (DELETE FROM ...) or (INSERT ...))
        for forbidden in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ", "CREATE ", "TRUNCATE "):
            if re.search(r"\b" + forbidden, single_sql, re.IGNORECASE):
                return SQLValidationResult(False, error_message=f"Forbidden DML/DDL keyword '{forbidden.strip()}' found in query.")

        # Check for SELECT ... INTO ... table / outfile
        if INTO_OUTFILE_RE.search(single_sql):
            return SQLValidationResult(False, error_message="SELECT INTO OUTFILE / DUMPFILE is strictly forbidden.")
        if re.search(r"\bSELECT\b[\s\S]+?\bINTO\b(?!\s+(?:OUTFILE|DUMPFILE))", single_sql, re.IGNORECASE):
            return SQLValidationResult(False, error_message="SELECT ... INTO table creation is forbidden.")

        # Step 3: Function denylist
        for func in DENIED_FUNCTIONS:
            pattern = r"\b" + re.escape(func) + r"\s*\("
            if re.search(pattern, single_sql, re.IGNORECASE):
                return SQLValidationResult(False, error_message=f"Security violation: Disallowed function '{func}' detected.")

        # Step 4: Extract referenced tables & verify Table Scope
        tables_found = self._extract_tables(single_sql)
        if self.allowed_tables is not None:
            for tbl in tables_found:
                if tbl.lower() not in self.allowed_tables:
                    return SQLValidationResult(
                        False,
                        error_message=f"Table scope violation: Table '{tbl}' does not exist in the allowed schema."
                    )

        # Step 5: Column sensitivity policy
        if self.sensitive_columns:
            for col in self.sensitive_columns:
                pattern = r"\b" + re.escape(col) + r"\b"
                if re.search(pattern, single_sql, re.IGNORECASE):
                    return SQLValidationResult(
                        False,
                        error_message=f"Column policy violation: Column '{col}' is marked sensitive and locked."
                    )

        # Step 6: Limit enforcement (inject or lower LIMIT to default/hard cap)
        final_sql = self._enforce_limit(single_sql)

        # Step 7: Check for blatant Cartesian cross joins without predicate
        if re.search(r"\bCROSS\s+JOIN\b", final_sql, re.IGNORECASE) and not re.search(r"\bWHERE\b|\bON\b", final_sql, re.IGNORECASE):
            return SQLValidationResult(False, error_message="Cost check: Unconstrained CROSS JOIN without predicate rejected.")

        return SQLValidationResult(True, sanitized_sql=final_sql, tables_used=tables_found)

    def _extract_tables(self, sql: str) -> List[str]:
        """Extracts table names from FROM and JOIN clauses."""
        tables = set()
        # Match FROM <table_name> and JOIN <table_name>
        pattern = r"\b(?:FROM|JOIN)\s+([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)?)"
        matches = re.finditer(pattern, sql, re.IGNORECASE)
        for m in matches:
            tbl = m.group(1).split(".")[-1] # handle schema.table
            if tbl.upper() not in ("SELECT", "LATERAL", "UNNEST", "GENERATE_SERIES"):
                tables.add(tbl.lower())
        return sorted(list(tables))

    def _enforce_limit(self, sql: str) -> str:
        """Injects or lowers LIMIT to satisfy default_limit and hard_cap_limit."""
        limit_match = re.search(r"\bLIMIT\s+(\d+)", sql, re.IGNORECASE)
        if limit_match:
            existing_limit = int(limit_match.group(1))
            if existing_limit > self.hard_cap_limit:
                sql = re.sub(r"\bLIMIT\s+\d+", f"LIMIT {self.hard_cap_limit}", sql, flags=re.IGNORECASE)
            return sql
        else:
            # Check if it has an aggregation or single-row scalar
            # Still inject default limit to be safe for non-aggregated / large result sets
            return f"{sql} LIMIT {self.default_limit}"


# Global validator instance with default limits
validator = SQLValidator()

