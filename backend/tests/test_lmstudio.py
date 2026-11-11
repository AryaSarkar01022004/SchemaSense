"""
Unit tests for LM Studio local model integration & robust JSON parsing.
"""

import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from app.config import settings
from app.services.llm_client import (
    LLMClient,
    extract_json_payload,
    normalize_openai_base_url,
)


class _DummyHTTPResp:
    def __init__(self, payload: dict):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestLMStudioClient(unittest.TestCase):
    def test_normalize_base_url(self):
        self.assertEqual(normalize_openai_base_url("http://localhost:1234"), "http://localhost:1234/v1")
        self.assertEqual(normalize_openai_base_url("http://127.0.0.1:1234/v1/"), "http://127.0.0.1:1234/v1")

    def test_extract_json_strips_think_and_fences(self):
        raw = (
            "<think>Let me think about the SQL query...</think>\n"
            "Here is your JSON:\n"
            "```json\n"
            '{"sql": "SELECT region, SUM(revenue) FROM sales GROUP BY region LIMIT 100", "tables_used": ["sales"], "assumptions": [], "needs_clarification": false, "clarifying_question": null}\n'
            "```"
        )
        parsed = extract_json_payload(raw)
        self.assertEqual(parsed["tables_used"], ["sales"])
        self.assertIn("SELECT region", parsed["sql"])

    def test_lmstudio_model_listing_and_completion_fallback(self):
        client = LLMClient()
        old_provider = settings.LLM_PROVIDER
        old_model = settings.LLM_MODEL
        try:
            settings.LLM_PROVIDER = "lmstudio"
            settings.LLM_MODEL = ""

            call_count = {"post": 0}

            def fake_urlopen(req, timeout=10):
                url = req.full_url
                if url.endswith("/models"):
                    return _DummyHTTPResp({
                        "data": [
                            {"id": "text-embedding-nomic"},
                            {"id": "qwen2.5-coder-7b-instruct"},
                        ]
                    })
                if url.endswith("/chat/completions"):
                    call_count["post"] += 1
                    body = json.loads(req.data.decode("utf-8"))
                    # First attempt sends response_format; simulate 400 error to verify retry!
                    if "response_format" in body:
                        raise urllib.error.HTTPError(
                            url, 400, "Bad Request", {}, io.BytesIO(b"response_format unsupported")
                        )
                    self.assertEqual(body["model"], "qwen2.5-coder-7b-instruct")
                    return _DummyHTTPResp({
                        "choices": [
                            {
                                "message": {
                                    "content": '{"sql": "SELECT region, SUM(sales) FROM sheet1 GROUP BY region LIMIT 100", "tables_used": ["sheet1"], "assumptions": ["Summed sales"], "needs_clarification": false, "clarifying_question": null}'
                                }
                            }
                        ],
                        "usage": {"prompt_tokens": 50, "completion_tokens": 25},
                    })
                raise AssertionError(f"Unexpected URL: {url}")

            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                models_info = client.list_lmstudio_models()
                self.assertTrue(models_info["connected"])
                self.assertIn("qwen2.5-coder-7b-instruct", models_info["models"])

                res = client.generate_sql_response(
                    system_prompt="sys",
                    user_prompt="user",
                    question="Total sales by region",
                    schema_context="TABLE sheet1 (~10 rows):\n  region TEXT\n  sales REAL",
                )
                self.assertEqual(call_count["post"], 2)
                self.assertEqual(res["tables_used"], ["sheet1"])
                self.assertEqual(res["_tokens_in"], 50)
        finally:
            settings.LLM_PROVIDER = old_provider
            settings.LLM_MODEL = old_model

    def test_deterministic_dynamic_csv_schema(self):
        client = LLMClient()
        old_provider = settings.LLM_PROVIDER
        try:
            settings.LLM_PROVIDER = "mock"
            schema = (
                "TABLE q1_sales (~50 rows): Uploaded CSV\n"
                "  region TEXT {North, South, East}\n"
                "  revenue REAL\n"
                "  units INTEGER"
            )
            res = client.generate_sql_response("sys", "user", "What is total revenue by region?", schema)
            self.assertIn("SUM(q1_sales.revenue)", res["sql"])
            self.assertIn("GROUP BY q1_sales.region", res["sql"])

            assist = client.assistant_chat(
                messages=[{"role": "user", "content": "What should I analyze?"}],
                schema_context=schema,
                connection_name="Q1 Sales",
            )
            self.assertIn("reply", assist)
            self.assertTrue(len(assist["suggested_questions"]) > 0)
        finally:
            settings.LLM_PROVIDER = old_provider

    def test_gemini_call_uses_header_and_skips_thought_parts(self):
        client = LLMClient()
        old_provider = settings.LLM_PROVIDER
        old_key = settings.GEMINI_API_KEY
        old_model = settings.LLM_MODEL
        try:
            settings.LLM_PROVIDER = "gemini"
            settings.GEMINI_API_KEY = "test-gemini-key"
            settings.LLM_MODEL = "gemini-flash-lite-latest"

            def fake_urlopen(req, timeout=30):
                self.assertEqual(req.headers.get("X-goog-api-key"), "test-gemini-key")
                return _DummyHTTPResp({
                    "candidates": [{
                        "content": {
                            "parts": [
                                {"text": "internal thought", "thought": True},
                                {"text": '{"reply": "Try grouping revenue by region.", "suggested_questions": ["Total revenue by region"]}'},
                            ]
                        }
                    }],
                    "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 18},
                })

            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                res = client.assistant_chat(
                    messages=[{"role": "user", "content": "Help me analyze"}],
                    schema_context="TABLE sales (~10 rows):\n  region TEXT\n  revenue REAL",
                )
                self.assertEqual(res["provider"], "gemini")
                self.assertIn("grouping revenue", res["reply"])
                self.assertEqual(res["suggested_questions"], ["Total revenue by region"])
        finally:
            settings.LLM_PROVIDER = old_provider
            settings.GEMINI_API_KEY = old_key
            settings.LLM_MODEL = old_model


if __name__ == "__main__":
    unittest.main()

