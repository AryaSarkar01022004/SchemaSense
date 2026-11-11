"""
Evaluation Harness (Section 6 & 7).
Measures:
1. Execution Accuracy: Result set of generated SQL == Result set of Gold SQL.
2. Validation Pass Rate: Generated SQL passes safety validator.
3. Median Latency: Time from question to chart & results (< 5s target).
"""

import time
import statistics
from typing import Dict, Any, List, Tuple
from app.db.models import Connection
from app.db.repository import repository
from app.db.target_db import TargetDatabaseManager
from app.safety.validator import SQLValidator
from app.services.schema_retriever import SchemaRetriever
from app.services.prompt_builder import PromptBuilder
from app.services.llm_client import llm_client
from app.eval.dataset import EVAL_DATASET


def normalize_rows_for_comparison(rows: List[Dict[str, Any]], has_order_by: bool) -> List[Tuple]:
    """
    Normalizes rows into tuples of values for order-insensitive or order-sensitive comparison.
    """
    normalized = []
    for r in rows:
        row_vals = tuple(round(v, 2) if isinstance(v, float) else str(v) for v in r.values())
        normalized.append(row_vals)
    if not has_order_by:
        normalized.sort()
    return normalized


class EvaluationHarness:
    def __init__(self, connection: Connection):
        self.connection = connection

    def run_suite(self, dataset: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        cases = dataset or EVAL_DATASET
        total = len(cases)
        correct_count = 0
        validation_passed = 0
        latencies = []
        details = []

        all_tables = repository.get_schema(self.connection.id)
        allowed_tables = {t.table_name.lower() for t in all_tables}
        validator = SQLValidator(allowed_tables=allowed_tables)

        print("\n=======================================================")
        print(f"SchemaSense Evaluation Suite ({total} test cases)")
        print("=======================================================")

        for case in cases:
            case_id = case["id"]
            question = case["question"]
            gold_sql = case["gold_sql"]
            category = case.get("category", "general")

            start_t = time.time()

            # 1. Pipeline execution
            _, compact_schema = SchemaRetriever.retrieve_schema(question, all_tables)
            system_prompt = PromptBuilder.build_system_prompt(self.connection.dialect)
            user_prompt = PromptBuilder.build_user_prompt(question, compact_schema)
            llm_resp = llm_client.generate_sql_response(system_prompt, user_prompt, question, compact_schema)
            gen_sql = llm_resp.get("sql", "").strip()

            # 2. Validation
            val_res = validator.validate(gen_sql, dialect=self.connection.dialect)
            is_valid = bool(val_res)
            if is_valid:
                validation_passed += 1

            # 3. Execution & Equivalence Check
            is_match = False
            error_str = None
            try:
                gold_exec = TargetDatabaseManager.execute_query(self.connection, gold_sql)
                gen_exec = TargetDatabaseManager.execute_query(self.connection, val_res.sanitized_sql if is_valid else gen_sql)

                has_order = "ORDER BY" in gold_sql.upper()
                norm_gold = normalize_rows_for_comparison(gold_exec.rows, has_order)
                norm_gen = normalize_rows_for_comparison(gen_exec.rows, has_order)

                is_match = (norm_gold == norm_gen)
                if is_match:
                    correct_count += 1
            except Exception as e:
                error_str = str(e)

            elapsed_ms = int((time.time() - start_t) * 1000)
            latencies.append(elapsed_ms)

            status_icon = " " if is_match else "❌"
            print(f"{status_icon} [{case_id}] {question[:45]:<45} | Match: {is_match} | Latency: {elapsed_ms}ms")
            if not is_match and error_str:
                print(f"    Error: {error_str}")

            details.append({
                "id": case_id,
                "category": category,
                "question": question,
                "gold_sql": gold_sql,
                "generated_sql": gen_sql,
                "is_valid": is_valid,
                "is_match": is_match,
                "latency_ms": elapsed_ms,
                "error": error_str
            })

        accuracy = (correct_count / total) * 100.0
        val_rate = (validation_passed / total) * 100.0
        median_lat = statistics.median(latencies) if latencies else 0.0

        print("-------------------------------------------------------")
        print(f"Execution Accuracy:    {accuracy:.1f}% (Target: >= 85.0%)")
        print(f"Validation Pass Rate:  {val_rate:.1f}%")
        print(f"Median Latency:        {median_lat:.1f}ms (Target: < 5000ms)")
        print("-------------------------------------------------------")

        passed_target = (accuracy >= 85.0) and (median_lat < 5000)
        return {
            "total": total,
            "correct_count": correct_count,
            "accuracy": accuracy,
            "validation_pass_rate": val_rate,
            "median_latency_ms": median_lat,
            "passed_target": passed_target,
            "details": details
        }

