"""
observer_engine.health_tech.reports
Comprehensive Evidence-Based Report Generation Service for Observer Behavioral Platform.

Generates reproducible, professional multi-section reports from real persisted observation records,
check-ins, and conservative events. Exports structured JSON, clean CSV, and printable HTML/PDF.

Visual and Functional Separation:
1. Header & Session Metadata
2. Direct Physical Measurements
3. Derived Behavioral Metrics & Distributions
4. Conservative Automated Observations & Evidence Traces
5. User-Reported Check-ins & Context
6. Signal Quality, Coverage & Data Limitations
7. Regulatory & Health-Tech Governance Non-Diagnostic Disclaimers
"""

import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from observer_engine.health_tech.schema import (
    ObservationRecord,
    CheckInRecord,
    EventRecord,
    SessionRecord,
    SCHEMA_VERSION,
    ALGORITHM_VERSION,
)
from observer_engine.health_tech.baseline import PersonalBaselineProfile
from observer_engine.health_tech.longitudinal import LongitudinalAnalyzer


NON_DIAGNOSTIC_DISCLAIMER = (
    "NON-CLINICAL & NON-DIAGNOSTIC USE NOTICE:\n"
    "Observer is an individualized behavioral observation and self-monitoring platform. "
    "It is NOT a medical device, diagnostic test, or clinical decision support system. "
    "All reported values are mathematical estimates derived from standard consumer webcams "
    "and desktop interaction patterns relative to the user's personal baseline. "
    "This report does NOT diagnose ADHD, depression, anxiety, neurological disorders, stress, "
    "or any medical condition, and facial geometry does not measure emotional truth or internal feelings. "
    "Share this report with a qualified healthcare provider for clinical interpretation."
)


class ReportGenerator:
    def __init__(self, baseline: Optional[PersonalBaselineProfile] = None):
        self.analyzer = LongitudinalAnalyzer(baseline)

    def generate_report(
        self,
        session: SessionRecord,
        observations: List[ObservationRecord],
        checkins: List[CheckInRecord],
        events: List[EventRecord],
        start_ts: Optional[float] = None,
        end_ts: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Compiles an evidence-based report from stored records.
        """
        start_ts = start_ts or session.start_time
        end_ts = end_ts or (session.end_time or time.time())

        # Filter observations to period
        period_obs = [o for o in observations if start_ts <= o.timestamp <= end_ts]
        period_checkins = [c for c in checkins if start_ts <= c.timestamp <= end_ts]
        period_events = [e for e in events if start_ts <= e.start_time <= end_ts]

        window_analysis = self.analyzer.analyze_window(period_obs, start_ts, end_ts)

        # Separate Direct vs Derived Features
        direct_features: Dict[str, Any] = {}
        derived_features: Dict[str, Any] = {}

        for feat_name, data in window_analysis["features"].items():
            if feat_name in ("ear_left", "ear_right", "ear_avg", "pitch", "yaw", "roll", "mouth_width_ratio", "mouth_opening_ratio"):
                direct_features[feat_name] = data
            else:
                derived_features[feat_name] = data

        start_iso = datetime.fromtimestamp(start_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        end_iso = datetime.fromtimestamp(end_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        csv_text = self._build_csv(period_obs, period_events, period_checkins)
        html_text = self._build_printable_html(
            session=session,
            start_iso=start_iso,
            end_iso=end_iso,
            window_analysis=window_analysis,
            direct_features=direct_features,
            derived_features=derived_features,
            events=period_events,
            checkins=period_checkins,
        )

        return {
            "report_id": f"REP-{session.session_id[:8]}",
            "schema_version": SCHEMA_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "reporting_period": {
                "start_time_iso": start_iso,
                "end_time_iso": end_iso,
                "start_ts": start_ts,
                "end_ts": end_ts,
                "duration_seconds": round(end_ts - start_ts, 1),
            },
            "session_metadata": session.to_dict(),
            "valid_observation_coverage_pct": window_analysis["valid_coverage_pct"],
            "direct_measurements": direct_features,
            "derived_metrics": derived_features,
            "automated_observations": [e.to_dict() for e in period_events],
            "user_reported_context": [c.to_dict() for c in period_checkins],
            "data_quality_limitations": {
                "usable_ratio": window_analysis["valid_coverage_pct"] / 100.0,
                "total_samples": window_analysis["total_observations"],
                "notice": "Intervals with extreme head angle, motion blur, or low illumination were excluded from metric denominators.",
            },
            "csv_export": csv_text,
            "html_printable_export": html_text,
            "disclaimer": NON_DIAGNOSTIC_DISCLAIMER,
        }

    def _build_csv(
        self,
        observations: List[ObservationRecord],
        events: List[EventRecord],
        checkins: List[CheckInRecord],
    ) -> str:
        """Constructs clean multi-table CSV export."""
        lines = [
            "# Observer Behavioral Observation Platform — Structured Data Export",
            f"# Schema Version: {SCHEMA_VERSION} | Algorithm Version: {ALGORITHM_VERSION}",
            f"# Generated: {datetime.now(timezone.utc).isoformat()}",
            f"# {NON_DIAGNOSTIC_DISCLAIMER.replace(chr(10), ' ')}",
            "",
            "### SECTION 1: OBSERVATIONS",
            "observation_id,timestamp_iso,feature_name,measured_value,unit,validity_status,source_stream,provenance",
        ]

        for o in observations[:2000]: # Sample if very large
            ts_iso = datetime.fromtimestamp(o.timestamp, tz=timezone.utc).isoformat()
            val_str = f"{o.measured_value:.4f}" if o.measured_value is not None else "null"
            lines.append(f'"{o.observation_id}","{ts_iso}","{o.feature_name}",{val_str},"{o.unit}","{o.validity_status}","{o.source_stream}","{o.provenance}"')

        lines.extend([
            "",
            "### SECTION 2: CONSERVATIVE AUTOMATED OBSERVATION EVENTS",
            "event_id,start_time_iso,end_time_iso,duration_seconds,event_type,feature_validity,uncertainty,explanation",
        ])
        for e in events:
            s_iso = datetime.fromtimestamp(e.start_time, tz=timezone.utc).isoformat()
            e_iso = datetime.fromtimestamp(e.end_time, tz=timezone.utc).isoformat()
            lines.append(f'"{e.event_id}","{s_iso}","{e_iso}",{e.duration_seconds:.1f},"{e.event_type}","{e.feature_validity}","{e.uncertainty}","{e.explanation}"')

        lines.extend([
            "",
            "### SECTION 3: USER CHECK-INS",
            "checkin_id,timestamp_iso,energy,effort,task_difficulty,feeling_stuck,stress,sleep_quality,notes",
        ])
        for c in checkins:
            c_iso = datetime.fromtimestamp(c.timestamp, tz=timezone.utc).isoformat()
            lines.append(f'"{c.checkin_id}","{c_iso}",{c.energy or ""},{c.effort or ""},{c.task_difficulty or ""},{c.feeling_stuck if c.feeling_stuck is not None else ""},{c.stress or ""},{c.sleep_quality or ""},"{c.notes or ""}"')

        return "\n".join(lines)

    def _build_printable_html(
        self,
        session: SessionRecord,
        start_iso: str,
        end_iso: str,
        window_analysis: Dict[str, Any],
        direct_features: Dict[str, Any],
        derived_features: Dict[str, Any],
        events: List[EventRecord],
        checkins: List[CheckInRecord],
    ) -> str:
        """Constructs clean, printable HTML report with calm aesthetic tokens."""
        direct_rows = "".join(
            f"<tr><td><code>{k}</code></td><td>{v['distribution']['median']} {v['unit']}</td>"
            f"<td>{v['distribution']['p25']} – {v['distribution']['p75']}</td>"
            f"<td>{v.get('baseline_comparison', {}).get('description', 'Calibrated')}</td></tr>"
            for k, v in direct_features.items()
        ) or "<tr><td colspan='4'>No valid direct measurements in period.</td></tr>"

        derived_rows = "".join(
            f"<tr><td><code>{k}</code></td><td>{v['distribution']['median']} {v['unit']}</td>"
            f"<td>{v['distribution']['min']} – {v['distribution']['max']}</td>"
            f"<td>{v.get('baseline_comparison', {}).get('description', 'Normal')}</td></tr>"
            for k, v in derived_features.items()
        ) or "<tr><td colspan='4'>No derived metrics available.</td></tr>"

        event_rows = "".join(
            f"<tr><td><b>{e.event_type}</b><br><small>{e.explanation}</small></td>"
            f"<td>{e.duration_seconds}s</td><td>{e.uncertainty.upper()}</td></tr>"
            for e in events
        ) or "<tr><td colspan='3'>No notable behavioral event thresholds reached.</td></tr>"

        checkin_rows = "".join(
            f"<tr><td>{datetime.fromtimestamp(c.timestamp, tz=timezone.utc).strftime('%H:%M:%S')}</td>"
            f"<td>Energy: {c.energy or '-'}/5 • Stress: {c.stress or '-'}/5 • Stuck: {'Yes' if c.feeling_stuck else 'No'}</td>"
            f"<td>{c.notes or 'None'}</td></tr>"
            for c in checkins
        ) or "<tr><td colspan='3'>No self-reported check-ins recorded.</td></tr>"

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Observer Behavioral Report - {session.session_id[:8]}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #F5F2E9; color: #293B32; padding: 24px; }}
  .report-box {{ max-width: 840px; margin: 0 auto; background: #FFFFFF; padding: 32px; border-radius: 12px; border: 1px solid rgba(0,0,0,0.08); box-shadow: 0 4px 12px rgba(0,0,0,0.04); }}
  h1 {{ font-size: 22px; color: #496B5A; margin-top: 0; }}
  h2 {{ font-size: 15px; border-bottom: 2px solid #DCE5D8; padding-bottom: 6px; margin-top: 24px; color: #293B32; }}
  .meta-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; font-size: 13px; background: #F5F2E9; padding: 12px; border-radius: 8px; margin-bottom: 16px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 8px; }}
  th, td {{ border: 1px solid #ECE7DE; padding: 8px 10px; text-align: left; }}
  th {{ background: #F5F2E9; color: #293B32; }}
  .disclaimer {{ background: #FFF4E5; border: 1px solid #FFE0B2; padding: 12px; border-radius: 6px; font-size: 11px; line-height: 1.5; color: #8A4B08; margin-top: 28px; }}
</style>
</head>
<body>
<div class="report-box">
  <h1>Observer — Physiological-Behavioral Observation Report</h1>
  <div class="meta-grid">
    <div><b>Session ID:</b> {session.session_id}</div>
    <div><b>Coverage Ratio:</b> {window_analysis['valid_coverage_pct']}% valid frames</div>
    <div><b>Period Start:</b> {start_iso}</div>
    <div><b>Period End:</b> {end_iso}</div>
  </div>

  <h2>1. Direct Physical Facial &amp; Head Measurements</h2>
  <table>
    <thead><tr><th>Feature</th><th>Median</th><th>IQR (25th–75th)</th><th>Baseline Comparison</th></tr></thead>
    <tbody>{direct_rows}</tbody>
  </table>

  <h2>2. Derived Behavioral Metrics</h2>
  <table>
    <thead><tr><th>Metric</th><th>Median</th><th>Observed Range</th><th>Comparison</th></tr></thead>
    <tbody>{derived_rows}</tbody>
  </table>

  <h2>3. Conservative Automated Observations</h2>
  <table>
    <thead><tr><th>Observation Event</th><th>Duration</th><th>Uncertainty</th></tr></thead>
    <tbody>{event_rows}</tbody>
  </table>

  <h2>4. User-Reported Context &amp; Check-Ins</h2>
  <table>
    <thead><tr><th>Time (UTC)</th><th>Ratings</th><th>User Note</th></tr></thead>
    <tbody>{checkin_rows}</tbody>
  </table>

  <div class="disclaimer">
    <b>Regulatory &amp; Clinical Notice:</b><br>
    {NON_DIAGNOSTIC_DISCLAIMER.replace(chr(10), '<br>')}
  </div>
</div>
</body>
</html>"""
