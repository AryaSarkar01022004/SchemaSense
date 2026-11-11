"""
Statistical Anomaly Detection Engine (Section 5.9).
- Evaluates pinned metric time-series.
- Detects anomalies using rolling median and Median Absolute Deviation (MAD).
- Computes robust z-scores: |x - median| / (1.4826 * MAD).
- Flags points where robust z-score > 3.0 or significant week-over-week shift.
- Generates 2-3 sentence insight summary and saves to insights table.
"""

import math
from typing import List, Dict, Any, Optional
from app.db.models import MetricPoint, Insight, generate_uuid, now_utc
from app.db.repository import repository


def calculate_median(values: List[float]) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mid = n // 2
    if n % 2 == 1:
        return sorted_vals[mid]
    return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0


def calculate_mad(values: List[float], median: float) -> float:
    """Calculates Median Absolute Deviation (MAD)."""
    if not values:
        return 0.0
    deviations = [abs(x - median) for x in values]
    return calculate_median(deviations)


class AnomalyDetector:
    @staticmethod
    def detect_metric_anomalies(metric_id: str, metric_name: str) -> Optional[Insight]:
        """
        Runs statistical anomaly scan over historical metric points.
        """
        points = repository.get_metric_points(metric_id, limit=60)
        if len(points) < 5:
            return None # Need minimum baseline points

        values = [p.value for p in points]
        baseline_values = values[:-1] # previous history
        latest_val = values[-1]
        latest_point = points[-1]

        median = calculate_median(baseline_values)
        mad = calculate_mad(baseline_values, median)

        # Standard consistency factor for normal distribution: 1.4826
        mad_scale = 1.4826 * mad if mad > 0 else 0.0001
        robust_z_score = abs(latest_val - median) / mad_scale

        # Week-over-week comparison if sufficient points
        wow_delta_pct = 0.0
        if len(values) >= 8:
            prior_week_val = values[-8]
            if prior_week_val > 0:
                wow_delta_pct = ((latest_val - prior_week_val) / prior_week_val) * 100.0

        # Flag anomaly if robust z-score > 3.0 or delta > 40%
        if robust_z_score > 3.0 or abs(wow_delta_pct) > 40.0:
            severity = "critical" if robust_z_score > 4.5 else "high" if robust_z_score > 3.0 else "medium"
            direction = "surged" if latest_val > median else "dropped"
            pct_change = ((latest_val - median) / (median or 1.0)) * 100.0

            summary = (
                f"{metric_name} {direction} to {latest_val:,.2f} on {latest_point.ts[:10]}, "
                f"a {abs(pct_change):.1f}% deviation from the baseline median ({median:,.2f}). "
                f"Robust anomaly z-score: {robust_z_score:.2f}."
            )

            insight = Insight(
                id=generate_uuid(),
                metric_id=metric_id,
                detected_at=now_utc(),
                severity=severity,
                summary=summary,
                detail={
                    "metric_name": metric_name,
                    "latest_value": latest_val,
                    "baseline_median": median,
                    "mad": mad,
                    "robust_z_score": round(robust_z_score, 2),
                    "wow_delta_pct": round(wow_delta_pct, 1),
                    "timestamp": latest_point.ts
                }
            )
            repository.create_insight(insight)
            return insight

        return None


anomaly_detector = AnomalyDetector()

