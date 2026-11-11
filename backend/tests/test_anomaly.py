"""
Unit tests for Anomaly Detection Engine (Section 5.9).
"""

import unittest
from app.services.anomaly_detector import calculate_median, calculate_mad


class TestAnomalyDetector(unittest.TestCase):
    def test_median_odd_and_even(self):
        self.assertEqual(calculate_median([1, 2, 3, 4, 5]), 3.0)
        self.assertEqual(calculate_median([1, 2, 3, 4]), 2.5)

    def test_mad_calculation(self):
        values = [10, 12, 11, 13, 12, 11, 12]
        med = calculate_median(values)
        mad = calculate_mad(values, med)
        self.assertEqual(med, 12.0)
        self.assertEqual(mad, 1.0)


if __name__ == "__main__":
    unittest.main()

