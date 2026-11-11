"""
Unit tests for SQL Safety Validator (Section 5.4).
"""

import unittest
from app.safety.validator import SQLValidator


class TestSQLValidator(unittest.TestCase):
    def setUp(self):
        self.validator = SQLValidator(
            allowed_tables={"orders", "customers", "products"},
            sensitive_columns={"password_hash", "credit_card_number"}
        )

    def test_valid_select(self):
        sql = "SELECT id, total_amount FROM orders WHERE status = 'paid'"
        res = self.validator.validate(sql)
        self.assertTrue(res.is_valid)
        self.assertIn("LIMIT 1000", res.sanitized_sql)

    def test_disallowed_drop_statement(self):
        sql = "DROP TABLE orders;"
        res = self.validator.validate(sql)
        self.assertFalse(res.is_valid)

    def test_stacked_query_rejected(self):
        sql = "SELECT id FROM orders; DROP TABLE customers;"
        res = self.validator.validate(sql)
        self.assertFalse(res.is_valid)
        self.assertIn("Stacked queries detected", res.error_message)

    def test_dangerous_function_rejected(self):
        sql = "SELECT id, pg_sleep(10) FROM orders"
        res = self.validator.validate(sql)
        self.assertFalse(res.is_valid)
        self.assertIn("pg_sleep", res.error_message)

    def test_table_scope_enforced(self):
        sql = "SELECT id FROM secret_internal_table"
        res = self.validator.validate(sql)
        self.assertFalse(res.is_valid)
        self.assertIn("Table scope violation", res.error_message)

    def test_sensitive_column_rejected(self):
        sql = "SELECT id, credit_card_number FROM customers"
        res = self.validator.validate(sql)
        self.assertFalse(res.is_valid)
        self.assertIn("Column policy violation", res.error_message)

    def test_limit_lowered_to_hard_cap(self):
        sql = "SELECT id FROM orders LIMIT 50000"
        res = self.validator.validate(sql)
        self.assertTrue(res.is_valid)
        self.assertIn("LIMIT 10000", res.sanitized_sql)


if __name__ == "__main__":
    unittest.main()

