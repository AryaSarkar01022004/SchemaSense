"""
Query Explanation and Optimization Engine (Section 5.8).
- AST inspection: extracts tables, joins, filters, and aggregations.
- Generates 2-3 sentence factual plain-language summary from the structured outline.
- Optimization hints: analyzes EXPLAIN output, suggesting missing indexes or rewrites.
"""

import re
from typing import Dict, Any, List


class QueryExplainer:
    @staticmethod
    def extract_ast_outline(sql: str) -> Dict[str, Any]:
        """Extracts structured outline from query without hallucinations."""
        outline = {
            "tables": [],
            "joins": [],
            "filters": [],
            "aggregations": [],
            "grouping": []
        }
        
        # Tables & Joins
        join_matches = re.findall(r"\bJOIN\s+([a-zA-Z0-9_]+)\s+ON\s+([^WHERE|GROUP|ORDER|LIMIT]+)", sql, re.IGNORECASE)
        for tbl, cond in join_matches:
            outline["joins"].append(f"{tbl.strip()} on {cond.strip()}")

        from_match = re.search(r"\bFROM\s+([a-zA-Z0-9_]+)", sql, re.IGNORECASE)
        if from_match:
            outline["tables"].append(from_match.group(1))

        # Filters
        where_match = re.search(r"\bWHERE\s+([^GROUP|ORDER|LIMIT]+)", sql, re.IGNORECASE)
        if where_match:
            outline["filters"].append(where_match.group(1).strip())

        # Aggregations
        for agg in ("COUNT", "SUM", "AVG", "MIN", "MAX"):
            matches = re.findall(rf"\b({agg}\s*\([^)]+\))", sql, re.IGNORECASE)
            outline["aggregations"].extend(matches)

        # Grouping
        group_match = re.search(r"\bGROUP\s+BY\s+([^ORDER|LIMIT]+)", sql, re.IGNORECASE)
        if group_match:
            outline["grouping"].append(group_match.group(1).strip())

        return outline

    @staticmethod
    def explain_query(sql: str) -> str:
        """Produces a concise 2-3 sentence summary from the structured AST outline."""
        outline = QueryExplainer.extract_ast_outline(sql)
        tables = ", ".join(outline["tables"]) or "the database"
        
        sentences = []
        if outline["aggregations"] and outline["grouping"]:
            aggs = ", ".join(outline["aggregations"])
            groups = ", ".join(outline["grouping"])
            sentences.append(f"This query computes {aggs} from {tables}, grouped by {groups}.")
        elif outline["aggregations"]:
            aggs = ", ".join(outline["aggregations"])
            sentences.append(f"This query calculates {aggs} across {tables}.")
        else:
            sentences.append(f"This query selects specific records from {tables}.")

        if outline["joins"]:
            joins_str = "; ".join(outline["joins"])
            sentences.append(f"It joins related tables: {joins_str}.")

        if outline["filters"]:
            filters_str = "; ".join(outline["filters"])
            sentences.append(f"Results are filtered by: {filters_str}.")

        return " ".join(sentences)

    @staticmethod
    def generate_optimization_hints(sql: str, explain_data: Dict[str, Any]) -> List[str]:
        """Proposes up to 3 non-destructive optimization suggestions based on the query plan."""
        hints = []
        
        # Check full table scans
        if explain_data.get("has_full_scan"):
            hints.append("Potential sequential scan detected: consider adding an index on filter or join keys.")

        # Check subqueries that could be joins
        if re.search(r"\bIN\s*\(\s*SELECT\b", sql, re.IGNORECASE):
            hints.append("Query uses an 'IN (SELECT ...)' subquery: rewriting as an INNER JOIN can significantly improve execution speed.")

        # Check for unindexed sorting
        if "ORDER BY" in sql.upper() and "LIMIT" in sql.upper():
            hints.append("Sorting with LIMIT: creating a composite index matching the ORDER BY clause avoids an in-memory sort.")

        return hints[:3]


query_explainer = QueryExplainer()

