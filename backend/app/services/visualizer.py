"""
Interactive Data Visualizer Service.
Safely builds, validates, executes, and charts visual aggregations
from any connected PostgreSQL, MySQL, SQLite, or uploaded CSV/XLS dataset.
"""

from typing import Dict, Any, List, Optional
from app.db.models import Connection, SchemaTable
from app.db.repository import repository
from app.db.target_db import TargetDatabaseManager
from app.safety.validator import SQLValidator
from app.services.viz_recommender import _truncate_label


ALLOWED_AGGREGATIONS = {"COUNT", "SUM", "AVG", "MIN", "MAX", "RAW"}
ALLOWED_CHART_TYPES = {"bar", "hbar", "line", "area", "pie", "scatter"}


def _is_numeric_type(data_type: str) -> bool:
    t = (data_type or "").upper()
    return any(k in t for k in ("INT", "REAL", "FLOAT", "DOUBLE", "NUMERIC", "DECIMAL"))


def _is_temporal_col(col_name: str, data_type: str) -> bool:
    n = col_name.lower()
    t = (data_type or "").upper()
    return any(k in t for k in ("DATE", "TIME")) or any(
        k in n for k in ("date", "time", "created_at", "updated_at", "ordered_at", "month", "year", "day")
    )


class VisualizerService:
    @staticmethod
    def _get_table_and_conn(connection_id: str, table_name: Optional[str] = None):
        conn = repository.get_connection(connection_id)
        if not conn:
            raise ValueError("Connection not found")
        tables = repository.get_schema(connection_id)
        if not tables:
            tables = TargetDatabaseManager.introspect_schema(conn)
            if tables:
                repository.save_schema(connection_id, tables)
        if not tables:
            raise ValueError("No tables discovered for this connection")

        target_table = tables[0]
        if table_name:
            match = next((t for t in tables if t.table_name.lower() == table_name.lower()), None)
            if not match:
                raise ValueError(f"Table '{table_name}' does not exist in connection schema")
            target_table = match
        return conn, tables, target_table

    @staticmethod
    def build_chart_options(
        chart_type: str,
        title: str,
        x_col: str,
        y_col: str,
        rows: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not rows:
            return {"type": chart_type, "title": title, "echarts_options": None}

        keys = list(rows[0].keys())
        actual_x = x_col if x_col in keys else keys[0]
        actual_y = y_col if y_col in keys else (keys[1] if len(keys) > 1 else keys[0])

        full_x = [str(r.get(actual_x) if r.get(actual_x) is not None else "Unknown") for r in rows]
        short_x = [_truncate_label(v, 24) for v in full_x]
        y_vals = [r.get(actual_y) if isinstance(r.get(actual_y), (int, float)) else 0 for r in rows]

        if chart_type == "pie":
            pie_data = [
                {"name": _truncate_label(lbl, 28), "value": y_vals[i]}
                for i, lbl in enumerate(full_x[:12])
            ]
            opts = {
                "tooltip": {"trigger": "item", "formatter": "{b}: <b>{c}</b> ({d}%)"},
                "legend": {"type": "scroll", "bottom": 0},
                "series": [
                    {
                        "name": actual_y,
                        "type": "pie",
                        "radius": ["38%", "68%"],
                        "center": ["50%", "45%"],
                        "itemStyle": {"borderRadius": 6, "borderColor": "#fff", "borderWidth": 2},
                        "data": pie_data,
                    }
                ],
            }
        elif chart_type == "hbar":
            rev_x = list(reversed(short_x))
            rev_full = list(reversed(full_x))
            rev_y = list(reversed(y_vals))
            opts = {
                "tooltip": {
                    "trigger": "axis",
                    "axisPointer": {"type": "shadow"},
                },
                "grid": {"left": 16, "right": 28, "top": 24, "bottom": 16, "containLabel": True},
                "xAxis": {"type": "value"},
                "yAxis": {"type": "category", "data": rev_x, "axisLabel": {"interval": 0}},
                "series": [
                    {
                        "name": actual_y,
                        "type": "bar",
                        "data": rev_y,
                        "barMaxWidth": 28,
                        "itemStyle": {"color": "#4f46e5", "borderRadius": [0, 6, 6, 0]},
                    }
                ],
            }
            _ = rev_full
        elif chart_type in ("line", "area"):
            series_obj: Dict[str, Any] = {
                "name": actual_y,
                "type": "line",
                "smooth": True,
                "data": y_vals,
                "itemStyle": {"color": "#4f46e5"},
                "lineStyle": {"width": 3},
            }
            if chart_type == "area":
                series_obj["areaStyle"] = {
                    "color": {
                        "type": "linear",
                        "x": 0, "y": 0, "x2": 0, "y2": 1,
                        "colorStops": [
                            {"offset": 0, "color": "rgba(79, 70, 229, 0.30)"},
                            {"offset": 1, "color": "rgba(79, 70, 229, 0.02)"},
                        ],
                    }
                }
            opts = {
                "tooltip": {"trigger": "axis"},
                "grid": {"left": 16, "right": 20, "top": 28, "bottom": 20, "containLabel": True},
                "xAxis": {"type": "category", "data": short_x, "axisLabel": {"rotate": 25 if len(short_x) > 5 else 0}},
                "yAxis": {"type": "value"},
                "series": [series_obj],
            }
        elif chart_type == "scatter":
            scatter_data = [
                [
                    r.get(actual_x) if isinstance(r.get(actual_x), (int, float)) else i,
                    r.get(actual_y) if isinstance(r.get(actual_y), (int, float)) else 0,
                ]
                for i, r in enumerate(rows[:250])
            ]
            opts = {
                "tooltip": {"trigger": "item"},
                "grid": {"left": 16, "right": 24, "top": 28, "bottom": 24, "containLabel": True},
                "xAxis": {"type": "value", "name": actual_x},
                "yAxis": {"type": "value", "name": actual_y},
                "series": [
                    {
                        "name": f"{actual_y} vs {actual_x}",
                        "type": "scatter",
                        "symbolSize": 9,
                        "data": scatter_data,
                        "itemStyle": {"color": "#7c3aed"},
                    }
                ],
            }
        else:  # bar
            opts = {
                "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                "grid": {"left": 16, "right": 20, "top": 28, "bottom": 24, "containLabel": True},
                "xAxis": {
                    "type": "category",
                    "data": short_x,
                    "axisLabel": {
                        "interval": 0 if len(short_x) <= 15 else "auto",
                        "rotate": 25 if len(short_x) > 4 else 0,
                    },
                },
                "yAxis": {"type": "value"},
                "series": [
                    {
                        "name": actual_y,
                        "type": "bar",
                        "barMaxWidth": 44,
                        "data": y_vals,
                        "itemStyle": {"color": "#4f46e5", "borderRadius": [6, 6, 0, 0]},
                    }
                ],
            }

        return {
            "type": "bar" if chart_type == "hbar" else ("line" if chart_type == "area" else chart_type),
            "chart_variant": chart_type,
            "title": title,
            "x_axis": actual_x,
            "y_axis": actual_y,
            "echarts_options": opts,
        }

    @staticmethod
    def run_visual_query(
        connection_id: str,
        table_name: str,
        x_col: str,
        y_col: Optional[str] = None,
        aggregation: str = "COUNT",
        chart_type: str = "bar",
        limit: int = 15,
        sort_dir: str = "DESC",
    ) -> Dict[str, Any]:
        conn, all_tables, table = VisualizerService._get_table_and_conn(connection_id, table_name)
        col_map = {c.column_name.lower(): c for c in table.columns}

        if not x_col or x_col.lower() not in col_map:
            raise ValueError(f"Invalid X-axis column: {x_col}")
        x_obj = col_map[x_col.lower()]
        if x_obj.is_sensitive:
            raise ValueError(f"Column '{x_obj.column_name}' is marked sensitive and restricted.")

        agg = (aggregation or "COUNT").upper()
        if agg not in ALLOWED_AGGREGATIONS:
            agg = "COUNT"
        c_type = (chart_type or "bar").lower()
        if c_type not in ALLOWED_CHART_TYPES:
            c_type = "bar"

        safe_limit = max(1, min(int(limit or 15), 500))
        safe_sort = "ASC" if (sort_dir or "").upper() == "ASC" else "DESC"

        y_obj = None
        if y_col and y_col != "*" and y_col.lower() in col_map:
            y_obj = col_map[y_col.lower()]
            if y_obj.is_sensitive:
                raise ValueError(f"Column '{y_obj.column_name}' is marked sensitive and restricted.")

        t_name = table.table_name
        x_name = x_obj.column_name

        if agg == "RAW" or c_type == "scatter":
            if not y_obj:
                raise ValueError("A numeric Y-axis column is required for raw / scatter plots.")
            y_name = y_obj.column_name
            sql = (
                f'SELECT "{x_name}" AS "{x_name}", "{y_name}" AS "{y_name}" '
                f'FROM "{t_name}" '
                f'WHERE "{x_name}" IS NOT NULL AND "{y_name}" IS NOT NULL '
                f'LIMIT {safe_limit}'
            )
            title = f"{y_name.replace('_', ' ').title()} vs {x_name.replace('_', ' ').title()}"
            metric_alias = y_name
        elif agg == "COUNT" or not y_obj:
            metric_alias = "record_count"
            sql = (
                f'SELECT "{x_name}", COUNT(*) AS "{metric_alias}" '
                f'FROM "{t_name}" '
                f'WHERE "{x_name}" IS NOT NULL '
                f'GROUP BY "{x_name}" '
                f'ORDER BY "{metric_alias}" {safe_sort} '
                f'LIMIT {safe_limit}'
            )
            title = f"Count of {t_name.replace('_', ' ').title()} by {x_name.replace('_', ' ').title()}"
        else:
            y_name = y_obj.column_name
            metric_alias = f"{agg.lower()}_{y_name}"
            sql = (
                f'SELECT "{x_name}", ROUND({agg}("{y_name}"), 2) AS "{metric_alias}" '
                f'FROM "{t_name}" '
                f'WHERE "{x_name}" IS NOT NULL AND "{y_name}" IS NOT NULL '
                f'GROUP BY "{x_name}" '
                f'ORDER BY "{metric_alias}" {safe_sort} '
                f'LIMIT {safe_limit}'
            )
            title = f"{agg}({y_name.replace('_', ' ').title()}) by {x_name.replace('_', ' ').title()}"

        # Run through SQL Safety Validator
        allowed_tables = {t.table_name.lower() for t in all_tables}
        sensitive_cols = {c.column_name.lower() for t in all_tables for c in t.columns if c.is_sensitive}
        validator = SQLValidator(allowed_tables=allowed_tables, sensitive_columns=sensitive_cols)
        val_res = validator.validate(sql, dialect=conn.dialect)
        if not val_res:
            raise ValueError(f"Safety check failed: {val_res.error_message}")

        exec_res = TargetDatabaseManager.execute_query(conn, val_res.sanitized_sql, max_rows=safe_limit)
        chart_spec = VisualizerService.build_chart_options(
            chart_type=c_type,
            title=title,
            x_col=x_name,
            y_col=metric_alias,
            rows=exec_res.rows,
        )

        return {
            "sql": val_res.sanitized_sql,
            "columns": exec_res.columns,
            "rows": exec_res.rows,
            "row_count": exec_res.row_count,
            "exec_ms": exec_res.exec_ms,
            "chart_spec": chart_spec,
        }

    @staticmethod
    def discover_charts(connection_id: str, table_name: Optional[str] = None) -> Dict[str, Any]:
        """Automatically discovers up to 4 informative charts and KPI stats for a table."""
        conn, _, table = VisualizerService._get_table_and_conn(connection_id, table_name)
        non_sensitive = [c for c in table.columns if not c.is_sensitive]

        numeric_cols = [
            c for c in non_sensitive
            if _is_numeric_type(c.data_type) and c.column_name.lower() != "id" and not c.column_name.lower().endswith("_id")
        ]
        temporal_cols = [c for c in non_sensitive if _is_temporal_col(c.column_name, c.data_type)]
        categorical_cols = [
            c for c in non_sensitive
            if c not in numeric_cols
            and c not in temporal_cols
            and c.column_name.lower() != "id"
            and not c.column_name.lower().endswith("_id")
            and not any(skip in c.column_name.lower() for skip in ("about", "description", "review_content", "img_link", "product_link", "url"))
        ]
        # Prefer low-cardinality categories first
        categorical_cols.sort(key=lambda c: (c.distinct_estimate or 9999, len(c.column_name)))

        discovered_charts: List[Dict[str, Any]] = []

        # 1. Top Category Bar Chart
        if categorical_cols:
            x_c = categorical_cols[0].column_name
            y_c = numeric_cols[0].column_name if numeric_cols else None
            agg = "AVG" if (y_c and "rating" in y_c.lower()) else ("SUM" if y_c else "COUNT")
            discovered_charts.append(
                VisualizerService.run_visual_query(
                    connection_id, table.table_name, x_c, y_c, agg, "bar", limit=10
                )
            )

        # 2. Distribution Donut / Pie Chart
        if len(categorical_cols) >= 1:
            cat_for_pie = categorical_cols[1] if len(categorical_cols) > 1 else categorical_cols[0]
            discovered_charts.append(
                VisualizerService.run_visual_query(
                    connection_id, table.table_name, cat_for_pie.column_name, None, "COUNT", "pie", limit=8
                )
            )

        # 3. Temporal Trend Line / Area Chart (or Top Items Horizontal Bar)
        if temporal_cols and numeric_cols:
            discovered_charts.append(
                VisualizerService.run_visual_query(
                    connection_id, table.table_name, temporal_cols[0].column_name, numeric_cols[0].column_name, "SUM", "area", limit=20, sort_dir="ASC"
                )
            )
        elif categorical_cols and len(numeric_cols) >= 2:
            discovered_charts.append(
                VisualizerService.run_visual_query(
                    connection_id, table.table_name, categorical_cols[0].column_name, numeric_cols[1].column_name, "SUM", "hbar", limit=10
                )
            )

        # 4. Scatter correlation if >= 2 numeric columns
        if len(numeric_cols) >= 2:
            discovered_charts.append(
                VisualizerService.run_visual_query(
                    connection_id, table.table_name, numeric_cols[0].column_name, numeric_cols[1].column_name, "RAW", "scatter", limit=120
                )
            )

        return {
            "connection_name": conn.name,
            "table_name": table.table_name,
            "kpis": {
                "row_estimate": table.row_estimate,
                "column_count": len(table.columns),
                "numeric_count": len(numeric_cols),
                "categorical_count": len(categorical_cols),
            },
            "charts": discovered_charts,
        }


visualizer_service = VisualizerService()

