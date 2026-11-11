"""
Visualization Recommender (Section 5.7).
Two-step hybrid:
1. Heuristic profile of result columns (temporal, numeric, categorical, id), cardinalities, row count.
2. Rules-first chart type selection:
   - 1 temporal + 1 numeric -> line
   - 1 categorical (< 25 unique, non-long-prose) + 1 numeric -> bar
   - 2 numerics -> scatter
   - 1 numeric scalar -> kpi card
   - otherwise -> table
3. Spec generation formatted for Apache ECharts with safe grids & label clipping.
"""

import re
from collections import defaultdict
from typing import List, Dict, Any, Optional, Tuple


def is_temporal(col_name: str, sample_val: Any) -> bool:
    name = col_name.lower()
    if any(k in name for k in ("date", "time", "created_at", "updated_at", "ordered_at", "shipped_at", "month", "year", "day", "ts")):
        return True
    if sample_val and isinstance(sample_val, str):
        return bool(re.match(r"^\d{4}-\d{2}-\d{2}", sample_val))
    return False


def is_numeric(sample_val: Any) -> bool:
    if sample_val is None or isinstance(sample_val, bool):
        return False
    return isinstance(sample_val, (int, float))


def is_id_col(col_name: str) -> bool:
    name = col_name.lower()
    return name == "id" or name.endswith("_id") or name in ("img_link", "product_link", "url", "link")


def _truncate_label(val: Any, max_len: int = 24) -> str:
    s = str(val if val is not None else "")
    # For pipe-separated hierarchical categories (e.g. Computers|Cables|USBCables), show the leaf segment
    if "|" in s and len(s) > max_len:
        leaf = s.split("|")[-1].strip()
        if leaf:
            s = leaf
    if len(s) > max_len:
        return s[:max_len - 1] + "…"
    return s


class VizRecommender:
    @staticmethod
    def profile_and_recommend(
        columns: List[str],
        rows: List[Dict[str, Any]],
        question: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Profiles result columns and generates a validated chart spec JSON.
        """
        if not rows or not columns:
            return {"type": "table", "title": "Empty Result", "options": {}}

        temporal_cols: List[str] = []
        numeric_cols: List[str] = []
        categorical_cols: List[Tuple[str, int, float]] = []
        text_cols: List[str] = []
        id_cols: List[str] = []

        first_row = rows[0]
        for col in columns:
            val = first_row.get(col)
            if val is None:
                for r in rows[:15]:
                    if r.get(col) is not None:
                        val = r.get(col)
                        break

            if is_id_col(col):
                id_cols.append(col)
            elif is_temporal(col, val):
                temporal_cols.append(col)
            elif is_numeric(val):
                numeric_cols.append(col)
            else:
                sample_strs = [str(r.get(col)) for r in rows[:100] if r.get(col) is not None]
                unique_vals = len(set(sample_strs))
                avg_len = (sum(len(s) for s in sample_strs) / len(sample_strs)) if sample_strs else 0.0
                # Only treat as categorical if low/moderate cardinality and not long prose paragraphs
                if unique_vals <= 30 and avg_len <= 120:
                    categorical_cols.append((col, unique_vals, avg_len))
                elif avg_len <= 120:
                    text_cols.append(col)

        # Prefer clean low-cardinality short-label categoricals first
        categorical_cols.sort(key=lambda item: (item[1], item[2]))
        row_count = len(rows)

        # Rule 1: Single scalar numeric -> KPI Card
        if row_count == 1 and len(numeric_cols) == 1 and len(columns) <= 2:
            num_col = numeric_cols[0]
            val = first_row.get(num_col)
            return {
                "type": "kpi",
                "title": num_col.replace("_", " ").title(),
                "value": val,
                "label": num_col
            }

        # Rule 2: One temporal + One numeric -> Line Chart
        if len(temporal_cols) >= 1 and len(numeric_cols) >= 1:
            t_col = temporal_cols[0]
            n_col = numeric_cols[0]
            plot_rows = rows[:50]
            x_data = [_truncate_label(r.get(t_col), 20) for r in plot_rows]
            y_data = [r.get(n_col) for r in plot_rows]
            title = f"{n_col.replace('_', ' ').title()} over Time"

            return {
                "type": "line",
                "title": title,
                "x_axis": t_col,
                "y_axis": n_col,
                "available_y_cols": numeric_cols,
                "series": [{"name": n_col, "data": y_data}],
                "echarts_options": {
                    "tooltip": {"trigger": "axis"},
                    "grid": {"left": 16, "right": 20, "top": 24, "bottom": 20, "containLabel": True},
                    "xAxis": {"type": "category", "data": x_data, "axisLabel": {"rotate": 25 if len(x_data) > 6 else 0}},
                    "yAxis": {"type": "value"},
                    "series": [{"name": n_col, "type": "line", "smooth": True, "data": y_data, "itemStyle": {"color": "#4f46e5"}}]
                }
            }

        # Rule 3: Categorical + Numeric -> Bar Chart
        if len(categorical_cols) >= 1 and len(numeric_cols) >= 1:
            cat_col = categorical_cols[0][0]
            num_col = numeric_cols[0]

            if row_count <= 25:
                x_full = [str(r.get(cat_col) or "") for r in rows]
                x_data = [_truncate_label(lbl, 22) for lbl in x_full]
                y_data = [r.get(num_col) for r in rows]
                title = f"{num_col.replace('_', ' ').title()} by {cat_col.replace('_', ' ').title()}"
            else:
                # Aggregate duplicate categories for ungrouped multi-row dumps so chart stays legible
                grouped: Dict[str, List[float]] = defaultdict(list)
                for r in rows:
                    k = str(r.get(cat_col) or "Unknown")
                    v = r.get(num_col)
                    if isinstance(v, (int, float)):
                        grouped[k].append(float(v))
                agg_items = sorted(
                    [(k, round(sum(vals) / len(vals), 2)) for k, vals in grouped.items() if vals],
                    key=lambda kv: kv[1],
                    reverse=True,
                )[:15]
                x_full = [k for k, _ in agg_items]
                x_data = [_truncate_label(k, 22) for k in x_full]
                y_data = [v for _, v in agg_items]
                title = f"Average {num_col.replace('_', ' ').title()} by {cat_col.replace('_', ' ').title()}"

            return {
                "type": "bar",
                "title": title,
                "x_axis": cat_col,
                "y_axis": num_col,
                "available_y_cols": numeric_cols,
                "series": [{"name": num_col, "data": y_data}],
                "echarts_options": {
                    "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                    "grid": {"left": 16, "right": 20, "top": 24, "bottom": 24, "containLabel": True},
                    "xAxis": {
                        "type": "category",
                        "data": x_data,
                        "axisLabel": {"interval": 0, "rotate": 25 if len(x_data) > 4 else 0},
                    },
                    "yAxis": {"type": "value"},
                    "series": [{
                        "name": num_col,
                        "type": "bar",
                        "data": y_data,
                        "barMaxWidth": 48,
                        "itemStyle": {"color": "#4f46e5", "borderRadius": [6, 6, 0, 0]},
                    }],
                },
            }

        # Rule 4: Two numeric columns -> Scatter Plot
        if len(numeric_cols) >= 2 and row_count > 5:
            x_col = numeric_cols[0]
            y_col = numeric_cols[1]
            scatter_data = [[r.get(x_col), r.get(y_col)] for r in rows[:200]]
            title = f"{y_col.replace('_', ' ').title()} vs {x_col.replace('_', ' ').title()}"

            return {
                "type": "scatter",
                "title": title,
                "x_axis": x_col,
                "y_axis": y_col,
                "available_y_cols": numeric_cols,
                "echarts_options": {
                    "tooltip": {"trigger": "item"},
                    "grid": {"left": 16, "right": 20, "top": 24, "bottom": 24, "containLabel": True},
                    "xAxis": {"type": "value", "name": x_col},
                    "yAxis": {"type": "value", "name": y_col},
                    "series": [{"type": "scatter", "symbolSize": 9, "data": scatter_data, "itemStyle": {"color": "#4f46e5"}}]
                }
            }

        # Rule 5: Top-N row list with 1 numeric + 1 short text label -> Horizontal/Vertical Bar
        if len(text_cols) >= 1 and len(numeric_cols) >= 1 and row_count <= 25:
            lbl_col = text_cols[0]
            num_col = numeric_cols[0]
            x_data = [_truncate_label(r.get(lbl_col), 22) for r in rows]
            y_data = [r.get(num_col) for r in rows]
            title = f"{num_col.replace('_', ' ').title()} by {lbl_col.replace('_', ' ').title()}"
            return {
                "type": "bar",
                "title": title,
                "x_axis": lbl_col,
                "y_axis": num_col,
                "available_y_cols": numeric_cols,
                "series": [{"name": num_col, "data": y_data}],
                "echarts_options": {
                    "tooltip": {"trigger": "axis"},
                    "grid": {"left": 16, "right": 20, "top": 24, "bottom": 24, "containLabel": True},
                    "xAxis": {"type": "category", "data": x_data, "axisLabel": {"interval": 0, "rotate": 25}},
                    "yAxis": {"type": "value"},
                    "series": [{"name": num_col, "type": "bar", "data": y_data, "barMaxWidth": 48, "itemStyle": {"color": "#4f46e5", "borderRadius": [6, 6, 0, 0]}}]
                }
            }

        # Default fallback: Table
        return {
            "type": "table",
            "title": "Data Table",
            "columns": columns,
            "row_count": row_count
        }


viz_recommender = VizRecommender()
