"""
Unit tests for Data Visualizer Service and Gmail Export Service.
"""

import unittest
from app.services.visualizer import visualizer_service
from app.services.export_email import email_export_service, build_gmail_compose_url, format_html_report


class TestVisualizerAndExport(unittest.TestCase):
    def test_visualizer_query_and_discover_on_demo_db(self):
        res = visualizer_service.run_visual_query(
            connection_id="conn-demo-ecommerce",
            table_name="orders",
            x_col="status",
            y_col="total_amount",
            aggregation="SUM",
            chart_type="bar",
            limit=10,
        )
        self.assertGreater(res["row_count"], 0)
        self.assertEqual(res["chart_spec"]["type"], "bar")
        self.assertIn("echarts_options", res["chart_spec"])

        discovered = visualizer_service.discover_charts("conn-demo-ecommerce", "orders")
        self.assertGreaterEqual(len(discovered["charts"]), 1)
        self.assertEqual(discovered["table_name"], "orders")

    def test_visualizer_blocks_unknown_or_sensitive_columns(self):
        with self.assertRaises(ValueError):
            visualizer_service.run_visual_query(
                connection_id="conn-demo-ecommerce",
                table_name="orders",
                x_col="nonexistent_col",
            )
        with self.assertRaises(ValueError):
            visualizer_service.run_visual_query(
                connection_id="conn-demo-ecommerce",
                table_name="customers",
                x_col="email",  # Flagged sensitive PII
            )

    def test_gmail_compose_url_and_report_formatting(self):
        url = build_gmail_compose_url(
            to="team@example.com",
            subject="Revenue Report",
            body_text="Total revenue is $10,000",
        )
        self.assertTrue(url.startswith("https://mail.google.com/mail/?"))
        self.assertIn("to=team%40example.com", url)
        self.assertIn("su=Revenue+Report", url)

        res = email_export_service.export_email(
            to="team@example.com",
            subject="Q1 Summary",
            insight="Sales grew 20%",
            sql="SELECT status, COUNT(*) FROM orders GROUP BY status",
            columns=["status", "count"],
            rows=[{"status": "paid", "count": 10}],
            send_direct=False,
        )
        self.assertEqual(res["mode"], "gmail_web")
        self.assertIn("https://mail.google.com/mail/", res["gmail_compose_url"])

        html_out = format_html_report("Q1 Summary", insight="Sales grew 20%", columns=["status"], rows=[{"status": "paid"}])
        self.assertIn("Q1 Summary", html_out)
        self.assertIn("paid", html_out)


if __name__ == "__main__":
    unittest.main()

