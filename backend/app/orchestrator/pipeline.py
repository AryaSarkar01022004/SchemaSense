"""
Query Orchestrator Pipeline (Section 5.3 & 5.11).
Executes the full 9-stage pipeline and streams stage events over SSE:
1. Normalize + resolve follow-up (conversation context)
2. Schema retrieval (top-k tables, expand FK neighbors)
3. Prompt build
4. LLM generation (structured JSON: sql, assumptions, confidence)
5. Validation (parse, policy, dry-run EXPLAIN)
6. Repair loop (max 2 retries with error feedback)
7. Cache lookup, then execute with limits
8. Viz recommendation + explanation
9. Persist message, emit final event
"""

import json
import time
import asyncio
from typing import AsyncGenerator, Dict, Any, Optional
from app.db.models import Connection, Message, generate_uuid, now_utc
from app.db.repository import repository
from app.db.target_db import TargetDatabaseManager
from app.safety.validator import SQLValidator
from app.services.schema_retriever import SchemaRetriever
from app.services.prompt_builder import PromptBuilder
from app.services.llm_client import llm_client
from app.services.repair_loop import repair_loop
from app.services.viz_recommender import viz_recommender
from app.services.explanation import query_explainer
from app.services.cache import cache_service


def format_sse(event: str, data: Dict[str, Any]) -> str:
    """Formats payload as standard Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


class QueryOrchestrator:
    @staticmethod
    async def process_question_stream(
        conversation_id: str,
        question: str,
        connection: Connection
    ) -> AsyncGenerator[str, None]:
        """
        Runs the 9-stage pipeline and yields SSE events in real time.
        """
        start_time = time.time()
        msg_id = generate_uuid()
        
        # Initialize message record
        msg = Message(
            id=msg_id,
            conversation_id=conversation_id,
            role="assistant",
            question=question,
            status="running"
        )
        repository.create_message(msg)

        try:
            # Stage 1: Normalize & Resolve Follow-up
            yield format_sse("status", {"stage": "resolving_context", "message": "Analyzing question and conversation context..."})
            await asyncio.sleep(0.05)
            
            history = repository.get_messages(conversation_id, limit=6)
            # Exclude current running message
            past_history = [m for m in history if m.id != msg_id]
            
            resolved_question = question
            if past_history:
                follow_up_prompt = PromptBuilder.build_follow_up_prompt(question, past_history)
                resolved_question = llm_client.resolve_follow_up(follow_up_prompt, question)

            # Stage 2: Schema Retrieval
            yield format_sse("status", {"stage": "retrieving_schema", "message": "Searching database schema and relations..."})
            await asyncio.sleep(0.05)
            
            all_tables = repository.get_schema(connection.id)
            if not all_tables:
                # If schema hasn't been synced yet, run quick introspection now
                all_tables = TargetDatabaseManager.introspect_schema(connection)
                if all_tables:
                    repository.save_schema(connection.id, all_tables)

            selected_tables, compact_schema = SchemaRetriever.retrieve_schema(resolved_question, all_tables)
            allowed_table_names = {t.table_name.lower() for t in all_tables}
            sensitive_column_names = {
                c.column_name.lower() for t in all_tables for c in t.columns if c.is_sensitive
            }

            # Stage 3: Prompt Build
            yield format_sse("status", {"stage": "building_prompt", "message": "Compiling schema context and few-shot examples..."})
            await asyncio.sleep(0.05)
            
            few_shots = repository.get_past_feedback_examples(connection.id, limit=3)
            system_prompt = PromptBuilder.build_system_prompt(dialect=connection.dialect)
            user_prompt = PromptBuilder.build_user_prompt(resolved_question, compact_schema, few_shots)

            # Stage 4: LLM Generation
            yield format_sse("status", {"stage": "generating_sql", "message": "Generating safe SQL translation..."})
            await asyncio.sleep(0.05)
            
            llm_result = llm_client.generate_sql_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                question=resolved_question,
                schema_context=compact_schema
            )

            # Handle clarification question
            if llm_result.get("needs_clarification"):
                clarifying_q = llm_result.get("clarifying_question") or "Could you please clarify your request?"
                msg.explanation = clarifying_q
                msg.status = "completed"
                repository.update_message(msg.id, status="completed", explanation=clarifying_q)
                yield format_sse("explanation", {"explanation": clarifying_q, "needs_clarification": True})
                yield format_sse("done", {"message_id": msg.id})
                return

            candidate_sql = llm_result.get("sql", "").strip()
            assumptions = llm_result.get("assumptions", [])
            tokens_in = int(llm_result.get("_tokens_in", 0) or 0)
            tokens_out = int(llm_result.get("_tokens_out", 0) or 0)

            # Stage 5: Validation (Safety Core)
            yield format_sse("status", {"stage": "validating_safety", "message": "Applying AST safety validation and policy checks..."})
            await asyncio.sleep(0.05)

            validator = SQLValidator(
                allowed_tables=allowed_table_names,
                sensitive_columns=sensitive_column_names,
                default_limit=1000,
                hard_cap_limit=10000
            )
            val_res = validator.validate(candidate_sql, dialect=connection.dialect)

            # Stage 6: Repair Loop for validation errors (max 2 retries)
            retries_used = 0
            validated_sql = val_res.sanitized_sql
            while not val_res and retries_used < 2:
                retries_used += 1
                yield format_sse("status", {
                    "stage": "repair_loop",
                    "message": f"Validation issue detected, repairing query (Attempt {retries_used}/2)..."
                })
                repaired_resp = repair_loop.repair_sql(
                    question=resolved_question,
                    schema_context=compact_schema,
                    failed_sql=candidate_sql,
                    error_message=val_res.error_message,
                    attempt=retries_used,
                    dialect=connection.dialect
                )
                tokens_in += int(repaired_resp.get("_tokens_in", 0) or 0)
                tokens_out += int(repaired_resp.get("_tokens_out", 0) or 0)
                candidate_sql = repaired_resp.get("sql", "").strip()
                val_res = validator.validate(candidate_sql, dialect=connection.dialect)
                if val_res:
                    validated_sql = val_res.sanitized_sql
                    break

            if not val_res:
                error_msg = f"SQL Safety Rejection: {val_res.error_message}"
                repository.update_message(msg.id, status="error", error=error_msg, generated_sql=candidate_sql)
                yield format_sse("error", {"error": error_msg, "last_sql": candidate_sql})
                yield format_sse("done", {"message_id": msg.id})
                return

            # Emit generated SQL event to UI
            yield format_sse("sql", {
                "sql": validated_sql,
                "assumptions": assumptions,
                "tables_used": val_res.tables_used
            })

            # Stage 7: Execution & Cache Lookup (with runtime error repair retry)
            yield format_sse("status", {"stage": "executing_query", "message": "Executing query inside read-only transaction..."})
            await asyncio.sleep(0.05)

            exec_res_dict = None
            while True:
                cached_result = cache_service.get_query_cache(connection.id, validated_sql)
                if cached_result:
                    exec_res_dict = cached_result
                    break
                try:
                    raw_exec = TargetDatabaseManager.execute_query(connection, validated_sql, max_rows=1000, timeout_ms=10000)
                    exec_res_dict = raw_exec.to_dict()
                    cache_service.set_query_cache(connection.id, validated_sql, exec_res_dict)
                    break
                except Exception as exec_err:
                    if retries_used >= 2:
                        repository.update_message(msg.id, status="error", error=f"SQL Execution Error: {exec_err}", generated_sql=candidate_sql, validated_sql=validated_sql)
                        yield format_sse("error", {"error": f"SQL Execution Error: {exec_err}", "last_sql": validated_sql})
                        yield format_sse("done", {"message_id": msg.id})
                        return

                    retries_used += 1
                    yield format_sse("status", {
                        "stage": "repair_loop",
                        "message": f"Execution error ({str(exec_err)[:60]}), repairing SQL (Attempt {retries_used}/2)..."
                    })
                    repaired_resp = repair_loop.repair_sql(
                        question=resolved_question,
                        schema_context=compact_schema,
                        failed_sql=validated_sql,
                        error_message=str(exec_err),
                        attempt=retries_used,
                        dialect=connection.dialect
                    )
                    tokens_in += int(repaired_resp.get("_tokens_in", 0) or 0)
                    tokens_out += int(repaired_resp.get("_tokens_out", 0) or 0)
                    candidate_sql = repaired_resp.get("sql", "").strip()
                    val_res = validator.validate(candidate_sql, dialect=connection.dialect)
                    if not val_res:
                        error_msg = f"Repaired SQL rejected: {val_res.error_message}"
                        repository.update_message(msg.id, status="error", error=error_msg, generated_sql=candidate_sql)
                        yield format_sse("error", {"error": error_msg, "last_sql": candidate_sql})
                        yield format_sse("done", {"message_id": msg.id})
                        return
                    validated_sql = val_res.sanitized_sql
                    yield format_sse("sql", {
                        "sql": validated_sql,
                        "assumptions": assumptions,
                        "tables_used": val_res.tables_used
                    })

            # Stream first page of rows to UI
            yield format_sse("rows", {
                "columns": exec_res_dict["columns"],
                "rows": exec_res_dict["rows"],
                "row_count": exec_res_dict["row_count"],
                "exec_ms": exec_res_dict["exec_ms"],
                "truncated": exec_res_dict["truncated"]
            })

            # Stage 8: Viz Recommendation & Explanation
            yield format_sse("status", {"stage": "synthesizing_insights", "message": "Generating visualization and query explanation..."})
            await asyncio.sleep(0.05)
            
            chart_spec = viz_recommender.profile_and_recommend(
                columns=exec_res_dict["columns"],
                rows=exec_res_dict["rows"],
                question=resolved_question
            )
            yield format_sse("chart", {"spec": chart_spec})

            explanation_text = query_explainer.explain_query(validated_sql)
            yield format_sse("explanation", {"explanation": explanation_text})

            # Stage 9: Persist Message & Emit Done
            total_elapsed_ms = int((time.time() - start_time) * 1000)
            repository.update_message(
                msg.id,
                status="completed",
                generated_sql=candidate_sql,
                validated_sql=validated_sql,
                row_count=exec_res_dict["row_count"],
                exec_ms=total_elapsed_ms,
                chart_spec=chart_spec,
                explanation=explanation_text,
                assumptions=assumptions,
                llm_tokens_in=tokens_in,
                llm_tokens_out=tokens_out
            )

            yield format_sse("done", {
                "message_id": msg.id,
                "status": "completed",
                "exec_ms": total_elapsed_ms
            })

        except Exception as e:
            err_str = f"Execution error: {str(e)}"
            repository.update_message(msg.id, status="error", error=err_str)
            yield format_sse("error", {"error": err_str})
            yield format_sse("done", {"message_id": msg.id})


orchestrator = QueryOrchestrator()

