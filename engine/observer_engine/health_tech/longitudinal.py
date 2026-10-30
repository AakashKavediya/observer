"""
observer_engine.health_tech.longitudinal
Longitudinal & Temporal Analysis Engine for Observer Behavioral Platform.

Provides deterministic, reproducible statistical windowing across stored observations:
- Short windows: 1-minute, 5-minute
- Session-level summaries
- Daily and weekly longitudinal trends

Calculates:
- Median and mean
- Robust spread: Median Absolute Deviation (MAD), Interquartile Range (IQR)
- Distribution percentiles: 10th, 25th, 50th, 75th, 90th
- Rates (e.g. blinks/min, shifts/min, switches/min)
- Valid observation coverage & missingness percentage
- Statistical deviation relative to personal baseline

Health-Tech Governance:
- Statistical deviations are purely quantitative comparisons to the user's personal baseline.
- NEVER translated into medical risk scores, diagnostic claims, or disease probabilities.
"""

from typing import Optional, List, Dict, Any, Tuple
import numpy as np

from observer_engine.health_tech.schema import ObservationRecord, ValidityStatus
from observer_engine.health_tech.baseline import PersonalBaselineProfile


def compute_distribution_metrics(values: List[float]) -> Optional[Dict[str, Any]]:
    """
    Computes deterministic statistical summaries over an array of numbers.
    Never replaces missing values with zero.
    """
    clean = [float(v) for v in values if v is not None and not np.isnan(v)]
    if not clean:
        return None

    arr = np.array(clean)
    med = float(np.median(arr))
    mad = float(np.median(np.abs(arr - med)))
    p25 = float(np.percentile(arr, 25))
    p75 = float(np.percentile(arr, 75))
    iqr = p75 - p25

    return {
        "count": len(arr),
        "mean": round(float(np.mean(arr)), 4),
        "median": round(med, 4),
        "std": round(float(np.std(arr)), 4),
        "mad": round(mad, 4),
        "iqr": round(iqr, 4),
        "min": round(float(np.min(arr)), 4),
        "max": round(float(np.max(arr)), 4),
        "p10": round(float(np.percentile(arr, 10)), 4),
        "p25": round(p25, 4),
        "p50": round(med, 4),
        "p75": round(p75, 4),
        "p90": round(float(np.percentile(arr, 90)), 4),
    }


class LongitudinalAnalyzer:
    def __init__(self, baseline: Optional[PersonalBaselineProfile] = None):
        self.baseline = baseline

    def set_baseline(self, baseline: PersonalBaselineProfile) -> None:
        self.baseline = baseline

    def analyze_window(
        self,
        observations: List[ObservationRecord],
        window_start_ts: float,
        window_end_ts: float,
    ) -> Dict[str, Any]:
        """
        Analyzes a specific time window [window_start_ts, window_end_ts] of observations.
        """
        window_obs = [
            o for o in observations
            if window_start_ts <= o.timestamp <= window_end_ts
        ]

        total_obs = len(window_obs)
        if total_obs == 0:
            return {
                "window_start": window_start_ts,
                "window_end": window_end_ts,
                "total_observations": 0,
                "valid_coverage_pct": 0.0,
                "features": {},
            }

        valid_count = sum(1 for o in window_obs if o.validity_status == ValidityStatus.VALID.value)
        coverage_pct = round((valid_count / max(1, total_obs)) * 100.0, 1)

        # Group valid observations by feature name
        feature_groups: Dict[str, List[float]] = {}
        for o in window_obs:
            if o.validity_status == ValidityStatus.VALID.value and o.measured_value is not None:
                feature_groups.setdefault(o.feature_name, []).append(o.measured_value)

        features_summary: Dict[str, Any] = {}
        for feat_name, vals in feature_groups.items():
            dist = compute_distribution_metrics(vals)
            if not dist:
                continue

            summary_item = {
                "distribution": dist,
                "unit": self._get_feature_unit(feat_name),
            }

            # Compare to personal baseline if available
            if self.baseline and self.baseline.is_calibrated:
                base_ref = self._compare_to_baseline(feat_name, dist["median"])
                if base_ref:
                    summary_item["baseline_comparison"] = base_ref

            features_summary[feat_name] = summary_item

        return {
            "window_start": window_start_ts,
            "window_end": window_end_ts,
            "total_observations": total_obs,
            "valid_observations": valid_count,
            "valid_coverage_pct": coverage_pct,
            "features": features_summary,
        }

    def aggregate_sessions(
        self,
        sessions: List[Dict[str, Any]],
        session_observations: Dict[str, List[ObservationRecord]],
    ) -> List[Dict[str, Any]]:
        """
        Produces session-level longitudinal summaries for comparative timeline charts.
        """
        summaries = []
        for sess in sessions:
            sid = sess.get("session_id", "")
            obs_list = session_observations.get(sid, [])
            start_t = sess.get("start_time", 0.0)
            end_t = sess.get("end_time") or (obs_list[-1].timestamp if obs_list else start_t + 1.0)
            
            analysis = self.analyze_window(obs_list, start_t, end_t)
            summaries.append({
                "session_id": sid,
                "start_time": start_t,
                "end_time": end_t,
                "duration_seconds": sess.get("duration_seconds", round(end_t - start_t, 1)),
                "valid_coverage_pct": analysis["valid_coverage_pct"],
                "blink_rate_median": analysis["features"].get("blink_rate_60s", {}).get("distribution", {}).get("median"),
                "ear_median": analysis["features"].get("ear_avg", {}).get("distribution", {}).get("median"),
                "smile_score_median": analysis["features"].get("smile_score_avg", {}).get("distribution", {}).get("median"),
                "head_velocity_median": analysis["features"].get("head_angular_velocity", {}).get("distribution", {}).get("median"),
                "task_title": sess.get("associated_task_title"),
            })
        return summaries

    def _compare_to_baseline(self, feat_name: str, median_val: float) -> Optional[Dict[str, Any]]:
        """Computes statistical deviation from personal baseline."""
        if not self.baseline:
            return None

        base_dict = None
        if feat_name in ("ear_avg", "ear_left", "ear_right") and self.baseline.ear_baseline:
            base_dict = self.baseline.ear_baseline
        elif feat_name.startswith("blink_rate") and self.baseline.blink_rate_baseline:
            base_dict = self.baseline.blink_rate_baseline
        elif feat_name == "mouth_width_ratio" and self.baseline.mouth_width_baseline:
            base_dict = self.baseline.mouth_width_baseline
        elif feat_name.startswith("brow_elevation") and self.baseline.brow_elevation_baseline:
            base_dict = self.baseline.brow_elevation_baseline
        elif feat_name == "head_angular_velocity" and self.baseline.head_angular_velocity_baseline:
            base_dict = self.baseline.head_angular_velocity_baseline

        if not base_dict:
            return None

        base_med = base_dict.get("median", 0.0)
        base_mad = base_dict.get("mad", 1e-4)
        z = (median_val - base_med) / max(1e-4, 1.4826 * base_mad)
        pct = ((median_val - base_med) / max(1e-4, abs(base_med))) * 100.0

        return {
            "baseline_median": round(base_med, 4),
            "baseline_mad": round(base_mad, 4),
            "robust_z_score": round(float(z), 2),
            "deviation_pct": round(float(pct), 1),
            "description": f"{'+' if pct >= 0 else ''}{round(pct, 1)}% relative to personal baseline",
        }

    @staticmethod
    def _get_feature_unit(feat: str) -> str:
        if "rate" in feat:
            return "per_min"
        if "velocity" in feat:
            return "deg_per_sec"
        if feat in ("pitch", "yaw", "roll", "shoulder_tilt_deg"):
            return "degrees"
        if "duration" in feat:
            return "seconds"
        if "count" in feat:
            return "count"
        return "ratio"
