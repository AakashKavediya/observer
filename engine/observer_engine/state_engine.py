"""
observer_engine.state_engine
Transparent weighted-evidence model for cognitive state estimation:
- Evidence formulas:
    frozen_score = 0.30*fixation + 0.25*idle + 0.25*tension + 0.10*blink_anomaly + 0.10*stillness
    spinning_score = 0.40*switching + 0.30*tension + 0.30*(1 - productive_input)
- Non-negotiable safety rules:
    * Fixation alone NEVER triggers paralysis; requires fixation + tension + low input.
    * Productive input (low idle with activity) -> FOCUSED.
    * Low tension + steady blinking -> RELAXED.
- EMA smoothing (alpha = 0.15), hysteresis (enter 0.65, exit 0.45), minimum dwell (90s).
- Explainable top-2 plain language signals.
"""

import time
from typing import Dict, List, Tuple, Optional
import numpy as np

from observer_engine.config import CONFIG, StateEngineConfig
from observer_engine.features import WindowedFeatures, FrameFeatures
from observer_engine.baseline import BaselineProfile
from observer_engine.ipc import (
    StateUpdateEvent,
    StateProbabilities,
    PredictionTelemetry,
    FrozenComponents,
    SpinningComponents,
    InterventionStatusTelemetry,
)


class StateEngine:
    def __init__(self, config: StateEngineConfig = CONFIG.state):
        self.config = config

        # Current discrete state: RELAXED, FOCUSED, PARALYSIS_LIKELY, OVERLOAD_LIKELY, UNKNOWN
        self.current_state: str = "UNKNOWN"
        self.last_state_change_ts: float = time.time()

        # Smoothed evidence scores (EMA)
        self.smoothed_frozen: float = 0.0
        self.smoothed_spinning: float = 0.0

        # Dwell time tracking for paralysis
        self.frozen_dwell_start_ts: Optional[float] = None

        # User feedback threshold adjustment (e.g., if user reported wrong_guess)
        self.sensitivity_multiplier: float = 1.0

        # Cached telemetry breakdown
        self.last_prediction_telemetry: Optional[PredictionTelemetry] = None

    def record_feedback(self, kind: str) -> None:
        """
        Adjusts sensitivity threshold based on user feedback.
        If 'wrong_guess', raises the enter threshold by 8% to make detection more conservative.
        """
        if kind == "wrong_guess":
            self.sensitivity_multiplier = min(1.35, self.sensitivity_multiplier * 1.08)
        elif kind == "helped":
            self.sensitivity_multiplier = max(0.85, self.sensitivity_multiplier * 0.98)

    def compute_state(
        self,
        features: WindowedFeatures,
        frame_feat: FrameFeatures,
        baseline: BaselineProfile,
        idle_seconds: float,
        window_switch_count: int,
        now: Optional[float] = None,
    ) -> StateUpdateEvent:
        now = now or time.time()

        # Quality gating check: if recent frames were invalid (low light, extreme angle, face lost)
        if not features.valid or not frame_feat.valid:
            reason = frame_feat.quality_reason or "Face alignment or lighting need adjustment"
            self.last_prediction_telemetry = PredictionTelemetry(
                state="UNKNOWN",
                frozen_score=0.0,
                smoothed_frozen=self.smoothed_frozen,
                smoothed_spinning=self.smoothed_spinning,
                confidence=0.0,
                top_signals=[reason],
                excluded_or_invalid_signals=["vision_tracking_quality"],
                exact_decision_rule=f"Webcam face tracking is not active - awaiting valid biometric signals ({reason}).",
                intervention_status=InterventionStatusTelemetry(
                    eligible=False,
                    reason=f"Suppressed: tracking quality invalid ({reason})",
                    cooldown_remaining_s=0.0,
                ),
            )
            return StateUpdateEvent(
                state="UNKNOWN",
                probabilities=StateProbabilities(relaxed=0.0, focused=0.0, paralysis=0.0, overload=0.0),
                confidence=0.0,
                top_signals=[reason],
                ts=now,
            )

        # 1. Normalize Signals (0.0 to 1.0) vs User's Own Baseline
        # Fixation: lower dispersion = higher fixation
        disp_norm = baseline.dispersion.normalize_01(features.dispersion_30s)
        fixation_norm = float(np.clip(1.0 - disp_norm, 0.0, 1.0))

        # Idle: input stillness from OS
        idle_norm = float(np.clip(idle_seconds / 60.0, 0.0, 1.0))

        # Tension: facial musculature vs baseline
        tension_norm = baseline.tension.normalize_01(features.tension_mean_4s)
        tension_norm = float(np.clip(tension_norm, 0.0, 1.0))

        # Blink Anomaly: depressed blink rate
        base_rate = max(baseline.blink_rate.mean, 4.0)
        blink_rate_diff = max(0.0, base_rate - features.blink_rate_60s)
        blink_anomaly = float(np.clip(blink_rate_diff / base_rate, 0.0, 1.0))

        # Stillness: low head variance
        h_var_norm = baseline.head_variance.normalize_01(features.head_pose_var_4s)
        stillness_norm = float(np.clip(1.0 - h_var_norm, 0.0, 1.0))

        # Switching: window changes over last 60s
        switching_norm = float(np.clip(window_switch_count / 8.0, 0.0, 1.0))

        # Productive Input: active typing/mouse within last 12s
        productive_input = float(np.clip(1.0 - (idle_seconds / 12.0), 0.0, 1.0))

        # 2. Weighted Evidence Formulas
        cfg = self.config
        raw_frozen = (
            cfg.weight_fixation * fixation_norm
            + cfg.weight_idle * idle_norm
            + cfg.weight_tension * tension_norm
            + cfg.weight_blink_anomaly * blink_anomaly
            + cfg.weight_stillness * stillness_norm
        )

        raw_spinning = (
            cfg.weight_switching * switching_norm
            + cfg.weight_spinning_tension * tension_norm
            + cfg.weight_spinning_unproductive * (1.0 - productive_input)
        )

        # 3. NON-NEGOTIABLE SAFETY RULE:
        # "Fixation alone NEVER triggers paralysis; require fixation + tension + low productive input."
        # If tension is low OR active input exists, cap frozen score below enter threshold.
        if tension_norm < 0.35 or idle_seconds < 15.0:
            raw_frozen = min(raw_frozen, cfg.enter_threshold - 0.20)

        # 4. Exponential Moving Average (EMA) Smoothing
        alpha = cfg.ema_alpha
        self.smoothed_frozen = alpha * raw_frozen + (1.0 - alpha) * self.smoothed_frozen
        self.smoothed_spinning = alpha * raw_spinning + (1.0 - alpha) * self.smoothed_spinning

        # Adjusted enter threshold factoring in sensitivity
        enter_thresh = cfg.enter_threshold * self.sensitivity_multiplier
        exit_thresh = cfg.exit_threshold

        # 5. Dwell Time Gate for Paralysis
        if self.smoothed_frozen >= enter_thresh:
            if self.frozen_dwell_start_ts is None:
                self.frozen_dwell_start_ts = now
            dwell_duration = now - self.frozen_dwell_start_ts
        else:
            self.frozen_dwell_start_ts = None
            dwell_duration = 0.0

        # 6. Discrete State Determination with Hysteresis
        new_state = self.current_state

        if self.current_state == "PARALYSIS_LIKELY":
            if self.smoothed_frozen < exit_thresh:
                new_state = "FOCUSED" if productive_input > 0.4 else "RELAXED"
        elif self.current_state == "OVERLOAD_LIKELY":
            if self.smoothed_spinning < exit_thresh:
                new_state = "FOCUSED" if productive_input > 0.4 else "RELAXED"
        else:
            # Transitions into paralysis or overload require sustained threshold
            if (
                self.smoothed_frozen >= enter_thresh
                and dwell_duration >= cfg.min_dwell_seconds
            ):
                new_state = "PARALYSIS_LIKELY"
            elif self.smoothed_spinning >= enter_thresh:
                new_state = "OVERLOAD_LIKELY"
            else:
                # Rule: Productive input -> FOCUSED. Low tension + steady blinking -> RELAXED.
                if productive_input >= 0.40 or (idle_seconds < 10.0 and tension_norm <= 0.60):
                    new_state = "FOCUSED"
                elif tension_norm < 0.35 and features.blink_rate_60s >= (base_rate * 0.7):
                    new_state = "RELAXED"
                else:
                    new_state = "FOCUSED"

        self.current_state = new_state

        # 7. Probability Distribution & Top Contributing Signals
        p_paralysis = float(np.clip(self.smoothed_frozen, 0.0, 1.0))
        p_overload = float(np.clip(self.smoothed_spinning, 0.0, 1.0))
        p_focused = float(np.clip(productive_input * (1.0 - p_paralysis), 0.0, 1.0))
        p_relaxed = float(np.clip((1.0 - tension_norm) * (1.0 - p_paralysis) * (1.0 - p_overload), 0.0, 1.0))

        # Normalize probabilities to sum to 1.0
        total_p = p_paralysis + p_overload + p_focused + p_relaxed + 1e-6
        probabilities = StateProbabilities(
            relaxed=float(p_relaxed / total_p),
            focused=float(p_focused / total_p),
            paralysis=float(p_paralysis / total_p),
            overload=float(p_overload / total_p),
        )

        # 7. Genuine Evidence-Backed Explanations with Real Sensor Measurements
        structured_observations = [
            {
                "feature": "gaze_dispersion",
                "measured_value": f"{features.dispersion_30s:.3f} dispersion",
                "baseline_value": f"{baseline.dispersion.mean:.3f}",
                "deviation": baseline.dispersion.format_deviation(features.dispersion_30s),
                "window": "30s I-DT window",
                "valid": True,
                "score_weight": cfg.weight_fixation * fixation_norm,
                "contribution": f"+{cfg.weight_fixation * fixation_norm:.2f} to frozen score",
                "text": f"Gaze dispersion {features.dispersion_30s:.2f} vs baseline {baseline.dispersion.mean:.2f} ({baseline.dispersion.format_deviation(features.dispersion_30s)} over 30s)",
            },
            {
                "feature": "facial_tension",
                "measured_value": f"{features.tension_mean_4s:.3f} index",
                "baseline_value": f"{baseline.tension.mean:.3f}",
                "deviation": baseline.tension.format_deviation(features.tension_mean_4s),
                "window": "4s blendshapes",
                "score_weight": cfg.weight_tension * tension_norm,
                "contribution": f"+{cfg.weight_tension * tension_norm:.2f} to frozen score",
                "text": f"Facial tension index {features.tension_mean_4s:.2f} vs baseline {baseline.tension.mean:.2f} ({baseline.tension.format_deviation(features.tension_mean_4s)})",
            },
            {
                "feature": "desktop_idle",
                "measured_value": f"{idle_seconds:.1f}s idle",
                "baseline_value": "15.0s active threshold",
                "deviation": f"+{max(0.0, idle_seconds - 15.0):.1f}s",
                "window": "OS event timer",
                "score_weight": cfg.weight_idle * idle_norm,
                "contribution": f"+{cfg.weight_idle * idle_norm:.2f} to frozen score",
                "text": f"Input idle {idle_seconds:.1f}s (productive score {productive_input:.2f})",
            },
            {
                "feature": "blink_rate",
                "measured_value": f"{features.blink_rate_60s:.1f} blinks/min",
                "baseline_value": f"{base_rate:.1f} blinks/min",
                "deviation": baseline.blink_rate.format_deviation(features.blink_rate_60s),
                "window": "60s sliding window",
                "score_weight": cfg.weight_blink_anomaly * blink_anomaly,
                "contribution": f"+{cfg.weight_blink_anomaly * blink_anomaly:.2f} to frozen score",
                "text": f"Blink rate {features.blink_rate_60s:.1f}/min vs baseline {base_rate:.1f}/min ({baseline.blink_rate.format_deviation(features.blink_rate_60s)})",
            },
            {
                "feature": "head_stillness",
                "measured_value": f"{features.head_pose_var_4s:.2f} variance",
                "baseline_value": f"{baseline.head_variance.mean:.2f}",
                "deviation": baseline.head_variance.format_deviation(features.head_pose_var_4s),
                "window": "4s solvePnP window",
                "score_weight": cfg.weight_stillness * stillness_norm,
                "contribution": f"+{cfg.weight_stillness * stillness_norm:.2f} to frozen score",
                "text": f"Head variance {features.head_pose_var_4s:.2f} vs baseline {baseline.head_variance.mean:.2f} ({baseline.head_variance.format_deviation(features.head_pose_var_4s)})",
            },
        ]

        if window_switch_count > 0:
            structured_observations.append({
                "feature": "window_switching",
                "measured_value": f"{window_switch_count} switches",
                "baseline_value": "2.0 switches/min",
                "deviation": f"{window_switch_count} switches",
                "window": "60s window",
                "score_weight": cfg.weight_switching * switching_norm,
                "contribution": f"+{cfg.weight_switching * switching_norm:.2f} to spinning score",
                "text": f"Window switching {window_switch_count} switches / 60s",
            })

        self.last_structured_observations = structured_observations

        # Sort descending by score contribution and pick top 2 evidence statements
        structured_observations.sort(key=lambda o: o["score_weight"], reverse=True)
        top_signals = [o["text"] for o in structured_observations[:2] if o["score_weight"] > 0.05]
        if not top_signals:
            top_signals = [
                f"All signals within your personal baseline bounds (dispersion {features.dispersion_30s:.2f}, tension {features.tension_mean_4s:.2f})"
            ]

        # Evidence score (0.60 to 0.95 depending on distance from threshold)
        confidence = float(np.clip(0.65 + 0.30 * (1.0 - abs(p_paralysis - 0.5)), 0.60, 0.95))

        # Explain exact decision rule
        if self.current_state == "PARALYSIS_LIKELY":
            exact_rule = (
                f"Sustained frozen evidence ({self.smoothed_frozen:.2f} >= enter threshold {enter_thresh:.2f}) "
                f"exceeded minimum dwell time ({dwell_duration:.0f}s >= {cfg.min_dwell_seconds:.0f}s). "
                f"Fixation ({fixation_norm:.2f}), tension ({tension_norm:.2f}), and idle ({idle_norm:.2f}) triggered state."
            )
            intv_status = InterventionStatusTelemetry(
                eligible=True,
                reason="Sustained task paralysis confirmed; intervention eligible",
                cooldown_remaining_s=0.0,
            )
        elif self.current_state == "OVERLOAD_LIKELY":
            exact_rule = (
                f"Spinning evidence ({self.smoothed_spinning:.2f} >= enter threshold {enter_thresh:.2f}) "
                f"from switching ({switching_norm:.2f}) and tension ({tension_norm:.2f})."
            )
            intv_status = InterventionStatusTelemetry(
                eligible=True,
                reason="High task switching and tension overload",
                cooldown_remaining_s=0.0,
            )
        elif self.current_state == "FOCUSED":
            exact_rule = (
                f"Productive input score ({productive_input:.2f} >= 0.40) or steady activity (idle {idle_seconds:.1f}s) "
                f"indicates engaged focus."
            )
            intv_status = InterventionStatusTelemetry(
                eligible=False,
                reason="Suppressed: user is engaged in focused flow",
                cooldown_remaining_s=0.0,
            )
        else: # RELAXED
            exact_rule = (
                f"Low facial tension ({tension_norm:.2f} < 0.35) and regular blinking "
                f"({features.blink_rate_60s:.0f}/min) indicate relaxed resting state."
            )
            intv_status = InterventionStatusTelemetry(
                eligible=False,
                reason="Suppressed: user is in relaxed resting state",
                cooldown_remaining_s=0.0,
            )

        # Build full telemetry breakdown
        self.last_prediction_telemetry = PredictionTelemetry(
            state=self.current_state,
            frozen_score=raw_frozen,
            frozen_components=FrozenComponents(
                fixation=fixation_norm,
                idle=idle_norm,
                tension=tension_norm,
                blink_anomaly=blink_anomaly,
                stillness=stillness_norm,
            ),
            frozen_weights=FrozenComponents(
                fixation=cfg.weight_fixation,
                idle=cfg.weight_idle,
                tension=cfg.weight_tension,
                blink_anomaly=cfg.weight_blink_anomaly,
                stillness=cfg.weight_stillness,
            ),
            spinning_score=raw_spinning,
            spinning_components=SpinningComponents(
                switching=switching_norm,
                tension=tension_norm,
                unproductive=1.0 - productive_input,
            ),
            smoothed_frozen=self.smoothed_frozen,
            smoothed_spinning=self.smoothed_spinning,
            enter_threshold=enter_thresh,
            exit_threshold=exit_thresh,
            dwell_duration_seconds=dwell_duration,
            dwell_required_seconds=cfg.min_dwell_seconds,
            dwell_satisfied=(dwell_duration >= cfg.min_dwell_seconds),
            confidence=confidence,
            top_signals=top_signals,
            excluded_or_invalid_signals=[],
            exact_decision_rule=exact_rule,
            intervention_status=intv_status,
        )

        return StateUpdateEvent(
            state=self.current_state,
            probabilities=probabilities,
            confidence=confidence,
            top_signals=top_signals,
            ts=now,
        )
