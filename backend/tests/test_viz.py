"""
Unit tests for Visualization Recommender (Section 5.7).
"""

import unittest
from app.services.viz_recommender import viz_recommender


class TestVizRecommender(unittest.TestCase):
    def test_single_numeric_recommends_kpi(self):
        columns = ["total_revenue"]
        rows = [{"total_revenue": 125000.50}]
        spec = viz_recommender.profile_and_recommend(columns, rows)
        self.assertEqual(spec["type"], "kpi")
        self.assertEqual(spec["value"], 125000.50)

    def test_temporal_plus_numeric_recommends_line(self):
        columns = ["order_date", "revenue"]
        rows = [
            {"order_date": "2026-01-01", "revenue": 100},
            {"order_date": "2026-01-02", "revenue": 150},
            {"order_date": "2026-01-03", "revenue": 200},
        ]
        spec = viz_recommender.profile_and_recommend(columns, rows)
        self.assertEqual(spec["type"], "line")
        self.assertEqual(spec["x_axis"], "order_date")
        self.assertEqual(spec["y_axis"], "revenue")

    def test_categorical_plus_numeric_recommends_bar(self):
        columns = ["status", "order_count"]
        rows = [
            {"status": "paid", "order_count": 50},
            {"status": "pending", "order_count": 20},
            {"status": "refunded", "order_count": 5},
        ]
        spec = viz_recommender.profile_and_recommend(columns, rows)
        self.assertEqual(spec["type"], "bar")
        self.assertEqual(spec["x_axis"], "status")
        self.assertEqual(spec["y_axis"], "order_count")

    def test_prefers_short_category_over_long_description(self):
        columns = ["about_product", "category", "rating"]
        rows = [
            {"about_product": "A" * 200 + str(i), "category": "Electronics|Cables" if i % 2 == 0 else "Electronics|Phones", "rating": 4.0 + (i % 5) * 0.1}
            for i in range(40)
        ]
        spec = viz_recommender.profile_and_recommend(columns, rows)
        self.assertEqual(spec["type"], "bar")
        self.assertEqual(spec["x_axis"], "category")
        self.assertIn("grid", spec["echarts_options"])


if __name__ == "__main__":
    unittest.main()

