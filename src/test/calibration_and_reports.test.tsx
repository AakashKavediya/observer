import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CalibrationScreen } from "@/screens/CalibrationScreen";
import { ObservationsReportsScreen } from "@/screens/ObservationsReportsScreen";
import { useObserverStore } from "@/store/useObserverStore";

describe("CalibrationScreen Component", () => {
  beforeEach(() => {
    useObserverStore.setState({
      consentGiven: true,
      activeScreen: "calibration",
      status: {
        schema_version: "1.0.0",
        type: "status",
        camera: "on",
        mode: "live",
        calibrating: false,
        paused: false,
        fps: 15.0,
        engine_ok: true,
      },
      latestTelemetry: {
        schema_version: "1.0.0",
        type: "telemetry",
        seq: 1,
        ts: Date.now(),
        camera: { status: "on", fps: 15.0, width: 640, height: 480, device_index: 0 },
        vision: {
          face_detected: true,
          quality_valid: true,
          quality_reason: "",
          mean_brightness: 120.0,
          ear: { left: 0.28, right: 0.28, avg: 0.28, baseline_mean: 0.28, baseline_std: 0.04, is_blink: false },
          blinks: { count_total: 5, rate_30s: 14.0, rate_60s: 14.0, rate_180s: 14.0, irregularity: 0.8 },
          gaze: { x: 0.5, y: 0.5, raw_x: 0.5, raw_y: 0.5, iris_l: [0.45, 0.45], iris_r: [0.55, 0.45], dispersion_4s: 0.2, dispersion_30s: 0.25, dispersion_120s: 0.3, shifts_per_min: 6, baseline_disp_mean: 0.35 },
          tension: { index: 0.15, brow_down: 0.0, mouth_press: 0.0, jaw_clench: 0.0, eye_squint: 0.0, baseline_mean: 0.18, baseline_std: 0.08 },
          head_pose: { pitch: 0.0, yaw: 0.0, roll: 0.0, variance_4s: 1.0, variance_30s: 1.0, baseline_var_mean: 1.2 },
          landmarks_wireframe: [
            [0.5, 0.5], [0.4, 0.4], [0.6, 0.4], [0.5, 0.6], [0.45, 0.55],
            [0.55, 0.55], [0.35, 0.45], [0.65, 0.45], [0.5, 0.3], [0.5, 0.7],
            [0.4, 0.65], [0.6, 0.65]
          ],
        },
        desktop_input: {
          idle_seconds: 2.0,
          seconds_since_last_key: 2.0,
          seconds_since_last_mouse: 2.0,
          seconds_since_last_scroll: 5.0,
          key_count_window: 10,
          mouse_move_count_window: 5,
          mouse_click_count_window: 2,
          mouse_scroll_count_window: 0,
          window_switch_count_60s: 1,
          productive_input_score: 0.8,
          monitor_status: "active",
        },
        prediction: {
          state: "FOCUSED",
          frozen_score: 0.2,
          frozen_components: { fixation: 0.2, idle: 0.1, tension: 0.1, blink_anomaly: 0.0, stillness: 0.1 },
          frozen_weights: { fixation: 0.3, idle: 0.25, tension: 0.25, blink_anomaly: 0.1, stillness: 0.1 },
          spinning_score: 0.1,
          spinning_components: { switching: 0.1, tension: 0.1, unproductive: 0.2 },
          smoothed_frozen: 0.2,
          smoothed_spinning: 0.1,
          enter_threshold: 0.65,
          exit_threshold: 0.45,
          dwell_duration_seconds: 0.0,
          dwell_required_seconds: 90.0,
          dwell_satisfied: false,
          confidence: 0.85,
          top_signals: ["Steady input rhythm"],
          excluded_or_invalid_signals: [],
          exact_decision_rule: "Active typing focus",
          intervention_status: { eligible: false, reason: "Monitoring", cooldown_remaining_s: 0.0 },
        },
      },
    });
  });

  it("renders Step 1 Hardware verification with active indicators", () => {
    render(<CalibrationScreen />);
    expect(screen.getByText("Step 1: Hardware & Tracking Verification")).toBeDefined();
    expect(screen.getByText("Begin Neutral Baseline")).toBeDefined();
  });

  it("advances to Step 2 when user begins neutral baseline", () => {
    render(<CalibrationScreen />);
    const beginBtn = screen.getByText("Begin Neutral Baseline");
    fireEvent.click(beginBtn);
    expect(screen.getByText("Step 2: Neutral Facial Baseline")).toBeDefined();
  });
});

describe("ObservationsReportsScreen Component", () => {
  beforeEach(() => {
    useObserverStore.setState({
      historyRecords: [
        {
          event_id: "obs_test_123",
          start_ts: 1729837000,
          end_ts: 1729837100,
          duration_seconds: 100,
          state: "PARALYSIS_LIKELY",
          score: 0.74,
          scoring_method: "Weighted evidence formula",
          contributing_features: [
            {
              feature: "gaze_dispersion",
              measured_value: "0.14 dispersion",
              baseline_value: "0.32",
              deviation: "-1.8σ",
              window: "30s",
              valid: true,
              contribution: "+0.26 to frozen score",
            },
          ],
          evidence_strength: "Strong",
          data_quality_status: "valid",
          qualification_reason: "Sustained high frozen score for 100s",
          user_review: "useful",
          user_notes: "Caught coding block",
          created_at_iso: "2026-10-29T16:00:00Z",
        },
      ],
    });
  });

  it("renders observation record with state badge and duration", () => {
    render(<ObservationsReportsScreen />);
    expect(screen.getByText("Observations & Reports")).toBeDefined();
    expect(screen.getAllByText("PARALYSIS LIKELY").length).toBeGreaterThan(0);
    expect(screen.getByText("Duration: 100s")).toBeDefined();
  });

  it("allows expanding observation details to view contributing measurements", () => {
    render(<ObservationsReportsScreen />);
    const detailsBtn = screen.getByText("Details");
    fireEvent.click(detailsBtn);
    expect(screen.getByText("Contributing Sensor Measurements")).toBeDefined();
    expect(screen.getByText("0.14 dispersion")).toBeDefined();
    expect(screen.getByText("-1.8σ")).toBeDefined();
  });
});
