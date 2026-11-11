"""
LLM Client Provider Abstraction (Section 5.3 - Stage 4).
Supports:
- LM Studio Local Server (OpenAI-compatible API at http://127.0.0.1:1234/v1)
- OpenAI (GPT-4o, GPT-4o-mini with json_object / tool calling)
- Google Gemini (Gemini 1.5/2.0 Pro/Flash)
- Built-in Mock / Deterministic Semantic Engine for offline test suites,
  eval runs, and zero-key local operation.
"""

import json
import re
import time
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple
from app.config import settings


def normalize_openai_base_url(base_url: str) -> str:
    url = (base_url or "http://127.0.0.1:1234/v1").strip().rstrip("/")
    if not url.endswith("/v1"):
        url = f"{url}/v1"
    return url


def extract_json_payload(raw_text: str) -> Dict[str, Any]:
    """
    Robustly extracts a JSON object from LLM output.
    Handles <think>...</think> reasoning blocks, markdown code fences,
    and stray prose around JSON.
    """
    cleaned = raw_text.strip()
    # Strip reasoning blocks emitted by local reasoning models (e.g. DeepSeek-R1, Qwen3)
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", cleaned, flags=re.IGNORECASE).strip()

    # Strip markdown code fences if present
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned, re.IGNORECASE)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    # Try direct JSON parse
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Extract substring between first { and last }
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = cleaned[start:end + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # Fallback: if model returned raw SQL inside a ```sql``` block instead of JSON
    sql_match = re.search(r"```sql\s*([\s\S]*?)```", raw_text, re.IGNORECASE)
    if sql_match:
        return {
            "sql": sql_match.group(1).strip(),
            "tables_used": [],
            "assumptions": ["Extracted SQL from raw model response"],
            "needs_clarification": False,
            "clarifying_question": None,
        }

    # Final fallback: if output starts with SELECT or WITH
    if re.match(r"^\s*(?:SELECT|WITH)\b", cleaned, re.IGNORECASE):
        return {
            "sql": cleaned,
            "tables_used": [],
            "assumptions": ["Extracted SQL directly from model output"],
            "needs_clarification": False,
            "clarifying_question": None,
        }

    raise ValueError(f"Could not parse structured JSON from model output: {raw_text[:200]}")


class LLMClient:
    @property
    def provider(self) -> str:
        return (settings.LLM_PROVIDER or "mock").lower()

    def list_lmstudio_models(self, base_url: Optional[str] = None) -> Dict[str, Any]:
        """Queries LM Studio's /v1/models endpoint for loaded local models."""
        url_root = normalize_openai_base_url(base_url or settings.LMSTUDIO_BASE_URL)
        models_url = f"{url_root}/models"
        headers = {
            "Authorization": f"Bearer {settings.LMSTUDIO_API_KEY or 'lm-studio'}",
            "Accept": "application/json",
        }
        req = urllib.request.Request(models_url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                raw_models = data.get("data", [])
                model_ids = [m.get("id") for m in raw_models if m.get("id")]
                return {
                    "connected": True,
                    "base_url": url_root,
                    "models": model_ids,
                }
        except Exception as e:
            return {
                "connected": False,
                "base_url": url_root,
                "models": [],
                "error": str(e),
            }

    def _resolve_lmstudio_model(self, base_url: str) -> str:
        """Uses configured LLM_MODEL or auto-detects the first loaded chat model in LM Studio."""
        if settings.LLM_MODEL and settings.LLM_MODEL.strip():
            return settings.LLM_MODEL.strip()
        info = self.list_lmstudio_models(base_url)
        models = info.get("models", [])
        if not models:
            raise RuntimeError(
                f"No loaded models found in LM Studio at {base_url}. "
                "Please load a model and start the Local Server in LM Studio."
            )
        # Prefer non-embedding models if multiple are loaded
        chat_models = [m for m in models if "embed" not in m.lower()]
        return chat_models[0] if chat_models else models[0]

    def generate_sql_response(
        self,
        system_prompt: str,
        user_prompt: str,
        question: str,
        schema_context: str
    ) -> Dict[str, Any]:
        """
        Generates structured JSON following the Stage 4 contract.
        """
        provider = self.provider

        if provider == "lmstudio":
            base_url = normalize_openai_base_url(settings.LMSTUDIO_BASE_URL)
            model = self._resolve_lmstudio_model(base_url)
            try:
                return self._call_openai_compatible(
                    base_url=base_url,
                    api_key=settings.LMSTUDIO_API_KEY or "lm-studio",
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    is_json=True,
                    timeout=settings.LLM_TIMEOUT_SECONDS,
                )
            except urllib.error.URLError as e:
                raise RuntimeError(
                    f"Cannot reach LM Studio at {base_url} ({e.reason}). "
                    "Verify LM Studio Local Server is running."
                ) from e

        if provider == "openai" and settings.OPENAI_API_KEY:
            try:
                return self._call_openai_compatible(
                    base_url="https://api.openai.com/v1",
                    api_key=settings.OPENAI_API_KEY,
                    model=settings.LLM_MODEL or "gpt-4o-mini",
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    is_json=True,
                    timeout=30,
                )
            except Exception as e:
                print(f"OpenAI API call failed: {e}. Falling back to internal engine.")

        elif provider == "gemini" and settings.GEMINI_API_KEY:
            try:
                return self._call_gemini(system_prompt, user_prompt)
            except Exception as e:
                raise RuntimeError(f"Gemini API error: {e}") from e

        # Default fallback: deterministic semantic engine
        return self._generate_deterministic(question, schema_context)

    def resolve_follow_up(self, follow_up_prompt: str, original_question: str) -> str:
        """Resolves follow-up query into standalone query."""
        provider = self.provider
        try:
            if provider == "lmstudio":
                base_url = normalize_openai_base_url(settings.LMSTUDIO_BASE_URL)
                model = self._resolve_lmstudio_model(base_url)
                res = self._call_openai_compatible(
                    base_url=base_url,
                    api_key=settings.LMSTUDIO_API_KEY or "lm-studio",
                    model=model,
                    system_prompt="You rewrite conversational follow-up questions into standalone database questions. Return ONLY the rewritten question.",
                    user_prompt=follow_up_prompt,
                    is_json=False,
                    timeout=settings.LLM_TIMEOUT_SECONDS,
                )
                cleaned = re.sub(r"<think>[\s\S]*?</think>", "", str(res), flags=re.IGNORECASE).strip().strip('"')
                if cleaned:
                    return cleaned
            elif provider == "gemini" and settings.GEMINI_API_KEY:
                res = self._call_gemini(
                    "You rewrite conversational follow-up questions into standalone database questions. Return ONLY the rewritten question.",
                    follow_up_prompt,
                    is_json=False,
                )
                cleaned = str(res).strip().strip('"')
                if cleaned:
                    return cleaned
            elif provider == "openai" and settings.OPENAI_API_KEY:
                res = self._call_openai_compatible(
                    base_url="https://api.openai.com/v1",
                    api_key=settings.OPENAI_API_KEY,
                    model=settings.LLM_MODEL or "gpt-4o-mini",
                    system_prompt="You rewrite follow-up questions.",
                    user_prompt=follow_up_prompt,
                    is_json=False,
                    timeout=15,
                )
                return str(res).strip().strip('"')
        except Exception:
            pass

        # Simple heuristic fallback for follow-up resolution
        lower_q = original_question.lower()
        if "by " in lower_q or "now " in lower_q or "filter" in lower_q:
            return f"Show previous query {original_question.replace('now ', '')}"
        return original_question

    def list_gemini_models(self, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Queries Gemini's /v1beta/models endpoint for available generateContent models."""
        key = (api_key or settings.GEMINI_API_KEY or "").strip()
        if not key:
            return {"connected": False, "models": [], "error": "Gemini API key is missing."}
        url = "https://generativelanguage.googleapis.com/v1beta/models"
        req = urllib.request.Request(url, headers={"x-goog-api-key": key}, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = []
                for m in data.get("models", []):
                    if "generateContent" in m.get("supportedGenerationMethods", []):
                        name = m.get("name", "").replace("models/", "")
                        if name and "tts" not in name and "image" not in name and "robotics" not in name:
                            models.append(name)
                return {"connected": True, "models": models}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            return {"connected": False, "models": [], "error": f"HTTP {e.code}: {err_body}"}
        except Exception as e:
            return {"connected": False, "models": [], "error": str(e)}

    def test_connection(self) -> Dict[str, Any]:
        """Performs a lightweight chat completion check against the active LLM provider."""
        provider = self.provider
        if provider == "mock":
            return {"ok": True, "provider": "mock", "model": "deterministic-offline", "message": "Built-in offline semantic engine is ready."}

        if provider == "lmstudio":
            base_url = normalize_openai_base_url(settings.LMSTUDIO_BASE_URL)
            info = self.list_lmstudio_models(base_url)
            if not info["connected"]:
                return {"ok": False, "provider": "lmstudio", "error": f"Failed to reach LM Studio at {base_url}: {info.get('error')}"}
            model = self._resolve_lmstudio_model(base_url)
            res = self._call_openai_compatible(
                base_url=base_url,
                api_key=settings.LMSTUDIO_API_KEY or "lm-studio",
                model=model,
                system_prompt="Reply with valid JSON: {\"status\": \"ok\"}",
                user_prompt="ping",
                is_json=False,
                timeout=30,
            )
            return {"ok": True, "provider": "lmstudio", "model": model, "base_url": base_url, "sample_reply": str(res)[:120]}

        if provider == "openai":
            if not settings.OPENAI_API_KEY:
                return {"ok": False, "provider": "openai", "error": "OPENAI_API_KEY is missing."}
            model = settings.LLM_MODEL or "gpt-4o-mini"
            res = self._call_openai_compatible(
                base_url="https://api.openai.com/v1",
                api_key=settings.OPENAI_API_KEY,
                model=model,
                system_prompt="Reply with OK.",
                user_prompt="ping",
                is_json=False,
                timeout=15,
            )
            return {"ok": True, "provider": "openai", "model": model, "sample_reply": str(res)[:120]}

        if provider == "gemini":
            if not settings.GEMINI_API_KEY:
                return {"ok": False, "provider": "gemini", "error": "GEMINI_API_KEY is missing."}
            model = (settings.LLM_MODEL or "gemini-flash-lite-latest").replace("models/", "")
            res = self._call_gemini("Reply with valid JSON: {\"status\": \"ok\"}", "ping", is_json=True)
            return {"ok": True, "provider": "gemini", "model": model, "sample_reply": str(res)[:120]}

        return {"ok": False, "provider": provider, "error": f"Unsupported provider: {provider}"}

    def assistant_chat(
        self,
        messages: List[Dict[str, str]],
        schema_context: str = "",
        connection_name: str = "",
        active_sql: str = "",
        active_columns: Optional[List[str]] = None,
        sample_rows: Optional[List[Dict[str, Any]]] = None,
        insights_summary: str = "",
    ) -> Dict[str, Any]:
        """
        Conversational Analysis Assistant Co-pilot.
        Helps the user plan analyses, explore metrics, interpret results,
        debug SQL, and recommends clickable questions to run in the Explorer.
        """
        system_prompt = """You are SchemaSense's AI Data Analysis Assistant.
Your role is to guide the user through their data analysis workflow in plain, concise language:
- Suggest valuable KPIs, breakdowns, comparisons, and visualizations based on the active dataset schema.
- Help interpret SQL queries, results, outliers, or trends.
- Suggest SQL improvements or debugging steps if asked.
- Recommend 2-4 concrete, ready-to-run natural language questions in 'suggested_questions' that the user can click to execute directly in the SQL Explorer.

OUTPUT CONTRACT:
Respond ONLY with valid JSON matching:
{
  "reply": "Your helpful, clear Markdown-formatted analysis guidance (concise, bulleted where helpful).",
  "suggested_questions": ["Question 1", "Question 2"]
}"""

        context_sections = []
        if connection_name:
            context_sections.append(f"ACTIVE DATA SOURCE: {connection_name}")
        if schema_context:
            context_sections.append(f"SCHEMA:\n{schema_context}")
        if active_sql:
            context_sections.append(f"LATEST SQL QUERY:\n{active_sql}")
        if active_columns:
            context_sections.append(f"LATEST RESULT COLUMNS: {', '.join(active_columns)}")
        if sample_rows:
            context_sections.append(f"LATEST SAMPLE ROWS (first {len(sample_rows)}):\n{json.dumps(sample_rows[:5], default=str)}")
        if insights_summary:
            context_sections.append(f"DETECTED ANOMALY INSIGHTS:\n{insights_summary}")

        history_lines = []
        for m in messages[-8:]:
            role = m.get("role", "user").upper()
            content = m.get("content", "").strip()
            if content:
                history_lines.append(f"{role}: {content}")

        user_prompt = (
            "### WORKSPACE CONTEXT\n"
            + ("\n\n".join(context_sections) if context_sections else "No active table selected yet.")
            + "\n\n### CONVERSATION HISTORY\n"
            + "\n".join(history_lines)
            + "\n\nRespond with the JSON contract now."
        )

        provider = self.provider
        try:
            if provider == "gemini" and settings.GEMINI_API_KEY:
                res = self._call_gemini(system_prompt, user_prompt, is_json=True)
                return {
                    "reply": res.get("reply") or str(res),
                    "suggested_questions": res.get("suggested_questions") or [],
                    "provider": "gemini",
                    "model": (settings.LLM_MODEL or "gemini-flash-lite-latest").replace("models/", ""),
                }
            if provider == "lmstudio":
                base_url = normalize_openai_base_url(settings.LMSTUDIO_BASE_URL)
                model = self._resolve_lmstudio_model(base_url)
                res = self._call_openai_compatible(
                    base_url=base_url,
                    api_key=settings.LMSTUDIO_API_KEY or "lm-studio",
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    is_json=True,
                    timeout=settings.LLM_TIMEOUT_SECONDS,
                )
                return {
                    "reply": res.get("reply") or str(res),
                    "suggested_questions": res.get("suggested_questions") or [],
                    "provider": "lmstudio",
                    "model": model,
                }
            if provider == "openai" and settings.OPENAI_API_KEY:
                model = settings.LLM_MODEL or "gpt-4o-mini"
                res = self._call_openai_compatible(
                    base_url="https://api.openai.com/v1",
                    api_key=settings.OPENAI_API_KEY,
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    is_json=True,
                    timeout=30,
                )
                return {
                    "reply": res.get("reply") or str(res),
                    "suggested_questions": res.get("suggested_questions") or [],
                    "provider": "openai",
                    "model": model,
                }
        except Exception as e:
            return {
                "reply": f"I encountered an issue calling `{provider}`: {e}\n\nYou can still inspect the schema or switch providers in **AI Models**.",
                "suggested_questions": self._fallback_assistant_suggestions(schema_context),
                "provider": provider,
                "error": str(e),
            }

        # Smart schema-aware offline assistant response
        suggestions = self._fallback_assistant_suggestions(schema_context)
        parsed = self._parse_schema_tables(schema_context)
        last_user = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
        if not parsed:
            reply = (
                "Connect a PostgreSQL/MySQL database or upload a **CSV / XLS / XLSX** file first. "
                "Once loaded, I can suggest KPIs, breakdowns, and help interpret your query results!"
            )
        else:
            tbl_summary = ", ".join(f"`{t}` ({len(cols)} cols)" for t, cols in list(parsed.items())[:5])
            reply = (
                f"I see **{connection_name or 'your dataset'}** with tables: {tbl_summary}.\n\n"
                f"For your analysis ({last_user[:80] or 'getting started'}), try:\n"
                "1. **Summary & Totals**: Compute overall row counts and sums of numeric metrics.\n"
                "2. **Segment Breakdown**: Group key metrics by categorical columns (e.g. status, category, region).\n"
                "3. **Top-N Outliers**: Rank the highest-value records to spot Pareto drivers.\n\n"
                "Click any suggested query below to run it directly in the Explorer."
            )
        return {
            "reply": reply,
            "suggested_questions": suggestions,
            "provider": "mock",
            "model": "offline-assistant",
        }

    def _fallback_assistant_suggestions(self, schema_context: str) -> List[str]:
        parsed = self._parse_schema_tables(schema_context)
        if not parsed:
            return []
        suggestions: List[str] = []
        for tbl, cols in list(parsed.items())[:2]:
            num_cols = [c for c, t in cols if any(k in t for k in ("INT", "REAL", "FLOAT", "DOUBLE", "NUMERIC")) and c.lower() != "id" and not c.lower().endswith("_id")]
            cat_cols = [c for c, t in cols if c not in num_cols and c.lower() != "id" and not c.lower().endswith("_id")]
            suggestions.append(f"How many records are in {tbl}?")
            if num_cols and cat_cols:
                suggestions.append(f"What is the total {num_cols[0].replace('_', ' ')} by {cat_cols[0].replace('_', ' ')} in {tbl}?")
            elif num_cols:
                suggestions.append(f"Show top 10 {tbl} by {num_cols[0].replace('_', ' ')}")
        return suggestions[:4]

    def _call_openai_compatible(
        self,
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        is_json: bool = True,
        timeout: int = 120,
    ) -> Any:
        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        def send_request(use_json_format: bool) -> Any:
            body: Dict[str, Any] = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.0,
            }
            if use_json_format:
                body["response_format"] = {"type": "json_object"}

            req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"]
                if is_json:
                    parsed = extract_json_payload(content)
                    usage = data.get("usage", {})
                    parsed.setdefault("_tokens_in", usage.get("prompt_tokens", 0))
                    parsed.setdefault("_tokens_out", usage.get("completion_tokens", 0))
                    return parsed
                return content

        try:
            return send_request(is_json)
        except urllib.error.HTTPError as e:
            # Many LM Studio models / chat templates return 400 when response_format=json_object is sent.
            # Retry automatically without response_format and parse JSON from text.
            if is_json and e.code in (400, 422):
                return send_request(False)
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            raise RuntimeError(f"LLM HTTP {e.code}: {err_body or e.reason}") from e

    def _call_gemini(self, system_prompt: str, user_prompt: str, is_json: bool = True) -> Any:
        primary_model = (settings.LLM_MODEL or "gemini-flash-lite-latest").strip().replace("models/", "")
        candidate_models = [primary_model]
        if primary_model != "gemini-3.5-flash":
            candidate_models.append("gemini-3.5-flash")

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": settings.GEMINI_API_KEY or "",
        }
        gen_config: Dict[str, Any] = {"temperature": 0.0}
        if is_json:
            gen_config["response_mime_type"] = "application/json"

        body = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [
                {"role": "user", "parts": [{"text": user_prompt}]}
            ],
            "generationConfig": gen_config,
        }
        encoded_body = json.dumps(body).encode("utf-8")

        last_error: Optional[Exception] = None
        for idx, model in enumerate(candidate_models):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            for attempt in range(2):
                req = urllib.request.Request(url, data=encoded_body, headers=headers, method="POST")
                try:
                    with urllib.request.urlopen(req, timeout=settings.LLM_TIMEOUT_SECONDS) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        parts = data["candidates"][0]["content"].get("parts", [])
                        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
                        if not is_json:
                            return text
                        parsed = extract_json_payload(text)
                        usage = data.get("usageMetadata", {})
                        parsed.setdefault("_tokens_in", usage.get("promptTokenCount", 0))
                        parsed.setdefault("_tokens_out", usage.get("candidatesTokenCount", 0))
                        return parsed
                except urllib.error.HTTPError as e:
                    err_body = ""
                    try:
                        err_body = e.read().decode("utf-8", errors="replace")
                    except Exception:
                        pass
                    last_error = RuntimeError(f"Gemini HTTP {e.code}: {err_body or e.reason}")
                    if e.code in (429, 503):
                        time.sleep(0.8 * (attempt + 1))
                        continue
                    # If model not found, try next candidate
                    if e.code == 404 and idx + 1 < len(candidate_models):
                        break
                    raise last_error from e

        raise last_error or RuntimeError("Gemini request failed")

    @staticmethod
    def _parse_schema_tables(schema_context: str) -> Dict[str, List[Tuple[str, str]]]:
        """Parses compact schema text into {table_name: [(col_name, col_type), ...]}."""
        tables: Dict[str, List[Tuple[str, str]]] = {}
        current_table: Optional[str] = None
        for line in schema_context.splitlines():
            table_match = re.match(r"^TABLE\s+([a-zA-Z0-9_]+)", line.strip(), re.IGNORECASE)
            if table_match:
                current_table = table_match.group(1).lower()
                tables[current_table] = []
            elif current_table and line.startswith("  "):
                parts = line.strip().split()
                if len(parts) >= 2:
                    tables[current_table].append((parts[0], parts[1].upper()))
        return tables

    def _generate_deterministic(self, question: str, schema_context: str) -> Dict[str, Any]:
        """
        Deterministic SQL synthesizer that parses question intent and maps
        tables, joins, metrics, and filters from the schema context.
        Works dynamically on both the demo schema and uploaded CSV/Excel tables.
        """
        q = question.lower().strip()

        # Check clarification condition
        if len(q) < 5 or q in ("data", "show me", "select", "what", "query"):
            return {
                "sql": "",
                "tables_used": [],
                "assumptions": [],
                "needs_clarification": True,
                "clarifying_question": "Could you please specify which entity (e.g. table, metric, or columns) you would like to analyze?"
            }

        parsed_tables = self._parse_schema_tables(schema_context)
        available_tables_lower = list(parsed_tables.keys())

        # Extract primary target table
        target_table = "orders" if "orders" in available_tables_lower else (available_tables_lower[0] if available_tables_lower else "orders")
        for t in available_tables_lower:
            stem = t[:-1] if len(t) > 3 and t.endswith("s") else t
            if re.search(r"\b" + re.escape(t) + r"\b", q) or re.search(r"\b" + re.escape(stem) + r"\b", q):
                target_table = t
                break

        tables_used = [target_table]
        assumptions = []

        # Intent detection using whole-word boundaries
        is_count = bool(re.search(r"\b(?:how many|count|number of|total count)\b", q))
        is_sum = bool(re.search(r"\b(?:total amount|total revenue|total spent|spending|sales|sum|gross)\b", q)) or (
            not is_count and bool(re.search(r"\btotal\b", q)) and not re.search(r"\bin total\b", q)
        )
        is_avg = bool(re.search(r"\b(?:average|avg|mean)\b", q))
        is_top = bool(re.search(r"\b(?:top|highest|best|most expensive|most popular|largest|max)\b", q))
        is_by_category = any(k in q for k in ("by status", "by category", "breakdown", "by country", "per customer", "by "))

        join_clause = ""
        select_cols = []
        group_by = ""
        order_by = ""
        limit_clause = "LIMIT 100"

        table_cols = parsed_tables.get(target_table, [])
        numeric_cols = [c for c, t in table_cols if any(k in t for k in ("INT", "REAL", "FLOAT", "DOUBLE", "NUMERIC", "DECIMAL")) and c.lower() != "id" and not c.lower().endswith("_id")]
        text_cols = [c for c, t in table_cols if c not in numeric_cols and c.lower() != "id" and not c.lower().endswith("_id")]

        if ("customer" in q or "customers" in q) and is_sum and "orders" in available_tables_lower and "customers" in available_tables_lower:
            target_table = "orders"
            tables_used = ["orders", "customers"]
            join_clause = "JOIN customers ON orders.customer_id = customers.id"
            select_cols = ["customers.name", "COUNT(orders.id) AS order_count", "SUM(orders.total_amount) AS total_spent"]
            group_by = "GROUP BY customers.name"
            order_by = "ORDER BY total_spent DESC"
            limit_clause = "LIMIT 10"
            assumptions.append("Grouped by customer name and ranked by total spending")

        elif "customer" in q and target_table == "orders" and "customers" in available_tables_lower:
            tables_used.append("customers")
            join_clause = "JOIN customers ON orders.customer_id = customers.id"
            if is_by_category or "per customer" in q:
                select_cols = ["customers.name", "COUNT(orders.id) AS order_count", "SUM(orders.total_amount) AS total_spent"]
                group_by = "GROUP BY customers.name"
                order_by = "ORDER BY total_spent DESC"
                limit_clause = "LIMIT 10"
                assumptions.append("Grouped by customer name and ranked by total spending")

        elif is_sum and target_table == "orders" and any(c == "total_amount" for c, _ in table_cols):
            if "by status" in q or "status" in q:
                select_cols = ["orders.status", "SUM(orders.total_amount) AS revenue", "COUNT(orders.id) AS order_count"]
                group_by = "GROUP BY orders.status"
                order_by = "ORDER BY revenue DESC"
                assumptions.append("Grouped by order status")
            else:
                select_cols = ["SUM(orders.total_amount) AS total_revenue", "COUNT(orders.id) AS total_orders"]
                assumptions.append("Aggregated total amount across all orders")

        elif is_count and not is_by_category:
            select_cols = [f"COUNT(*) AS total_{target_table}"]

        elif (is_sum or is_avg) and numeric_cols:
            agg_fn = "AVG" if is_avg else "SUM"
            metric_col = next((c for c in numeric_cols if c.lower() in q), numeric_cols[0])
            group_col = next((c for c in text_cols if c.lower().replace("_", " ") in q or c.lower() in q), None)
            if not group_col and is_by_category and text_cols:
                group_col = text_cols[0]

            if group_col:
                select_cols = [f"{target_table}.{group_col}", f"{agg_fn}({target_table}.{metric_col}) AS {agg_fn.lower()}_{metric_col}", f"COUNT(*) AS row_count"]
                group_by = f"GROUP BY {target_table}.{group_col}"
                order_by = f"ORDER BY {agg_fn.lower()}_{metric_col} DESC"
                assumptions.append(f"Computed {agg_fn}({metric_col}) grouped by {group_col}")
            else:
                select_cols = [f"{agg_fn}({target_table}.{metric_col}) AS {agg_fn.lower()}_{metric_col}", "COUNT(*) AS row_count"]
                assumptions.append(f"Computed {agg_fn}({metric_col}) across {target_table}")

        elif is_count and is_by_category and text_cols:
            group_col = next((c for c in text_cols if c.lower().replace("_", " ") in q or c.lower() in q), text_cols[0])
            select_cols = [f"{target_table}.{group_col}", f"COUNT(*) AS count"]
            group_by = f"GROUP BY {target_table}.{group_col}"
            order_by = "ORDER BY count DESC"
            assumptions.append(f"Counted records grouped by {group_col}")

        elif is_top:
            limit_n = 10
            match_limit = re.search(r"top\s+(\d+)", q)
            if match_limit:
                limit_n = int(match_limit.group(1))
            limit_clause = f"LIMIT {limit_n}"

            if target_table == "orders" and any(c == "total_amount" for c, _ in table_cols):
                select_cols = ["orders.id", "orders.customer_id", "orders.total_amount", "orders.created_at"]
                order_by = "ORDER BY orders.total_amount DESC"
                assumptions.append(f"Ranked by total_amount descending to show top {limit_n}")
            elif target_table == "products" and any(c == "price" for c, _ in table_cols):
                select_cols = ["products.id", "products.name", "products.price"]
                order_by = "ORDER BY products.price DESC"
                assumptions.append("Ranked by product price descending")
            elif table_cols:
                all_col_names = [f"{target_table}.{c}" for c, _ in table_cols[:8]]
                sort_col = next((c for c in numeric_cols if c.lower() in q), numeric_cols[0] if numeric_cols else table_cols[0][0])
                select_cols = all_col_names
                order_by = f"ORDER BY {target_table}.{sort_col} DESC"
                assumptions.append(f"Ranked by {sort_col} descending (top {limit_n})")
            else:
                select_cols = [f"{target_table}.id"]
                order_by = f"ORDER BY {target_table}.id DESC"

        else:
            # Explicit column selection from actual table schema
            if target_table == "orders" and any(c == "total_amount" for c, _ in table_cols):
                select_cols = ["orders.id", "orders.customer_id", "orders.status", "orders.total_amount", "orders.created_at"]
            elif target_table == "customers" and any(c == "country" for c, _ in table_cols):
                select_cols = ["customers.id", "customers.name", "customers.email", "customers.country", "customers.created_at"]
            elif target_table == "products" and any(c == "stock_quantity" for c, _ in table_cols):
                select_cols = ["products.id", "products.name", "products.category", "products.price", "products.stock_quantity"]
            elif table_cols:
                select_cols = [f"{target_table}.{c}" for c, _ in table_cols[:10]]
            else:
                select_cols = [f"{target_table}.id"]
            order_by = f"ORDER BY {select_cols[0]} ASC"

        # Filters using word boundaries
        where_clauses = []
        if re.search(r"\bpending\b", q) and any(c == "status" for c, _ in table_cols):
            where_clauses.append(f"{target_table}.status = 'pending'")
            assumptions.append("Filtered for pending status")
        elif re.search(r"\b(?:completed|paid)\b", q) and any(c == "status" for c, _ in table_cols):
            where_clauses.append(f"{target_table}.status = 'paid'")
            assumptions.append("Filtered for paid status")

        where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        sql_parts = [
            f"SELECT {', '.join(select_cols)}",
            f"FROM {target_table}",
            join_clause if join_clause else "",
            where_str if where_str else "",
            group_by if group_by else "",
            order_by if order_by else "",
            limit_clause if limit_clause else ""
        ]
        sql = " ".join([p for p in sql_parts if p.strip()])

        return {
            "sql": sql,
            "tables_used": sorted(list(set(tables_used))),
            "assumptions": assumptions,
            "needs_clarification": False,
            "clarifying_question": None
        }


llm_client = LLMClient()
