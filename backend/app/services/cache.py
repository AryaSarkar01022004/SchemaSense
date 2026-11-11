"""
Caching Layer (Section 5.10).
- Query result cache: key = hash(connection_id, normalized_sql), TTL 5 min, stores up to 1000 rows. Invalidate on schema resync.
- Question to SQL cache: key = hash(connection_id, schema_version, normalized_question).
- Embedding cache: per question text.
"""

import time
import hashlib
from typing import Optional, Any, Dict
from app.config import settings


class CacheService:
    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        # In-memory stores (with Redis integration capability)
        self._query_cache: Dict[str, Dict[str, Any]] = {}
        self._question_sql_cache: Dict[str, Dict[str, Any]] = {}
        self._embedding_cache: Dict[str, list] = {}

    def _normalize_text(self, text: str) -> str:
        return " ".join(text.strip().lower().split())

    def get_query_cache(self, conn_id: str, sql: str) -> Optional[Dict[str, Any]]:
        norm_sql = self._normalize_text(sql)
        key = hashlib.sha256(f"{conn_id}:{norm_sql}".encode()).hexdigest()
        entry = self._query_cache.get(key)
        if entry:
            if time.time() - entry["timestamp"] < self.ttl:
                return entry["data"]
            else:
                del self._query_cache[key]
        return None

    def set_query_cache(self, conn_id: str, sql: str, data: Dict[str, Any]):
        norm_sql = self._normalize_text(sql)
        key = hashlib.sha256(f"{conn_id}:{norm_sql}".encode()).hexdigest()
        self._query_cache[key] = {
            "timestamp": time.time(),
            "data": data
        }

    def get_sql_cache(self, conn_id: str, schema_version: str, question: str) -> Optional[Dict[str, Any]]:
        norm_q = self._normalize_text(question)
        key = hashlib.sha256(f"{conn_id}:{schema_version}:{norm_q}".encode()).hexdigest()
        entry = self._question_sql_cache.get(key)
        if entry and (time.time() - entry["timestamp"] < 3600): # 1 hr TTL for question cache
            return entry["data"]
        return None

    def set_sql_cache(self, conn_id: str, schema_version: str, question: str, sql_data: Dict[str, Any]):
        norm_q = self._normalize_text(question)
        key = hashlib.sha256(f"{conn_id}:{schema_version}:{norm_q}".encode()).hexdigest()
        self._question_sql_cache[key] = {
            "timestamp": time.time(),
            "data": sql_data
        }

    def get_embedding(self, text: str) -> Optional[list]:
        key = hashlib.sha256(text.encode()).hexdigest()
        return self._embedding_cache.get(key)

    def set_embedding(self, text: str, embedding: list):
        key = hashlib.sha256(text.encode()).hexdigest()
        self._embedding_cache[key] = embedding

    def invalidate_connection(self, conn_id: str):
        """Invalidate all cached results when schema is resynced."""
        keys_to_del = [k for k in self._query_cache.keys()]
        self._query_cache.clear()
        self._question_sql_cache.clear()


cache_service = CacheService(ttl_seconds=settings.QUERY_CACHE_TTL_SECONDS)

