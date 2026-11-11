"""
Schema Retrieval Engine (Section 5.3 - Stage 2).
- Vector cosine similarity search against table and column embeddings.
- Selects top 8 tables.
- Expands tables reachable by FK from selected tables (one hop), capping total at 15.
- If schema has under 20 tables, skips retrieval and sends everything.
- Formats schema into compact notation.
"""

import math
import hashlib
from typing import List, Dict, Set, Optional, Tuple
from app.db.models import SchemaTable, SchemaColumn
from app.services.cache import cache_service


def compute_dense_embedding(text: str, dim: int = 1536) -> List[float]:
    """
    Computes a deterministic dense normalized embedding vector for text.
    Provides offline compatibility with standard 1536-dim vector databases.
    """
    cached = cache_service.get_embedding(text)
    if cached:
        return cached

    vec = [0.0] * dim
    words = text.lower().split()
    for w in words:
        h = int(hashlib.md5(w.encode()).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if ((h >> 4) % 2 == 0) else -1.0
        vec[idx] += sign

    # Normalize vector to unit length
    magnitude = math.sqrt(sum(x * x for x in vec)) or 1.0
    normalized = [x / magnitude for x in vec]
    cache_service.set_embedding(text, normalized)
    return normalized


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0.0 or mag2 == 0.0:
        return 0.0
    return dot / (mag1 * mag2)


class SchemaRetriever:
    @staticmethod
    def retrieve_schema(question: str, all_tables: List[SchemaTable]) -> Tuple[List[SchemaTable], str]:
        """
        Retrieves relevant tables and renders compact schema format.
        """
        if not all_tables:
            return [], ""

        # If schema has under 20 tables, skip retrieval and send everything (Section 5.3 Stage 2)
        if len(all_tables) < 20:
            selected_tables = all_tables
        else:
            q_emb = compute_dense_embedding(question)
            scored_tables: List[Tuple[float, SchemaTable]] = []
            
            for table in all_tables:
                # Score table embedding
                t_score = 0.0
                if table.embedding:
                    t_score = cosine_similarity(q_emb, table.embedding)
                else:
                    t_emb = compute_dense_embedding(f"{table.table_name}: {table.description}")
                    t_score = cosine_similarity(q_emb, t_emb)
                
                # Boost if column names match
                col_boost = 0.0
                for col in table.columns:
                    if col.column_name.lower() in question.lower():
                        col_boost += 0.2
                
                total_score = t_score + col_boost
                scored_tables.append((total_score, table))

            # Sort descending and take top 8
            scored_tables.sort(key=lambda x: x[0], reverse=True)
            top_tables = [t for _, t in scored_tables[:8]]
            selected_ids = {t.id for t in top_tables}
            table_by_id = {t.id: t for t in all_tables}
            table_by_name = {t.table_name.lower(): t for t in all_tables}

            # One-hop FK expansion (cap total at 15)
            fk_neighbors: List[SchemaTable] = []
            for t in top_tables:
                for col in t.columns:
                    target_table = None
                    if col.fk_table_id and col.fk_table_id in table_by_id:
                        target_table = table_by_id[col.fk_table_id]
                    elif col.fk_table_name and col.fk_table_name.lower() in table_by_name:
                        target_table = table_by_name[col.fk_table_name.lower()]
                    
                    if target_table and target_table.id not in selected_ids:
                        selected_ids.add(target_table.id)
                        fk_neighbors.append(target_table)
                        if len(top_tables) + len(fk_neighbors) >= 15:
                            break
                if len(top_tables) + len(fk_neighbors) >= 15:
                    break

            selected_tables = top_tables + fk_neighbors

        # Format into compact schema representation
        compact_text = SchemaRetriever.format_compact_schema(selected_tables)
        return selected_tables, compact_text

    @staticmethod
    def format_compact_schema(tables: List[SchemaTable]) -> str:
        """
        Renders the exact compact schema format specified in Section 5.3:
        TABLE orders (~2.1M rows): customer orders
          id bigint PK
          customer_id bigint FK -> customers.id
          status text {pending, paid, shipped, refunded}
          total_amount numeric(10,2)
          created_at timestamptz
        """
        lines = []
        for t in tables:
            rows_repr = f"~{t.row_estimate:,} rows" if t.row_estimate else "row count unknown"
            lines.append(f"TABLE {t.table_name} ({rows_repr}): {t.description}")
            for col in t.columns:
                col_parts = [f"  {col.column_name} {col.data_type}"]
                if col.is_pk:
                    col_parts.append("PK")
                if col.fk_column:
                    target_t = col.fk_table_name or "table"
                    col_parts.append(f"FK -> {target_t}.{col.fk_column}")
                if col.sample_values and len(col.sample_values) > 0 and not col.is_sensitive:
                    samples_str = "{" + ", ".join(str(s) for s in col.sample_values[:5]) + "}"
                    col_parts.append(samples_str)
                lines.append(" ".join(col_parts))
            lines.append("") # blank line between tables
        return "\n".join(lines).strip()

