# Observer Validation Protocol & Signal Separation Analysis

This protocol outlines the scientific procedure to evaluate the separation of behavioral scores and benchmark false positive/negative rates across neurodivergent cohorts.

---

## 1. Ethical Data Recording Protocol

All validation sessions require explicit written informed consent.
**Strict Privacy Rule**: No raw video frames are permanently retained. Instead, features (EAR, gaze dispersion, blendshape tension metrics) and aggregate OS counters are written to a temporary local testing CSV during the session and anonymized immediately.

### 1.1 Controlled Test Phases (15 Minutes Total)
1. **Phase A (Relaxed Watching - 3 min)**:
   * Participant casually watches an engaging, non-stressful video (e.g. nature documentary or hobby clip).
   * Expected state: `RELAXED`. Low tension (< 0.2), normal blink frequency (14-22/min), high gaze dispersion across frame.
2. **Phase B (Active Productive Flow - 5 min)**:
   * Participant works on a comfortable task (typing text, organizing notes, or light coding).
   * Expected state: `FOCUSED`. Moderate input activity (idle < 5s), moderate blink frequency (10-18/min), normal tension (< 0.35).
3. **Phase C (Simulated Task Paralysis / Freeze - 4 min)**:
   * Participant is presented with a complex, ambiguous problem or instructed to freeze and tense brow/jaw while staring blankly at the cursor.
   * Expected state: `PARALYSIS_LIKELY`. Sustained gaze freeze (dispersion < 0.15 for > 30s), elevated tension (> 0.65), input idle (> 45s).
4. **Phase D (Recovery & De-escalation - 3 min)**:
   * Participant takes a deep breath, shifts gaze away, and resumes casual browsing.
   * Expected state: Return to `RELAXED`.

---

## 2. Quantitative Separation Metrics

The primary objective is maximizing signal separation between **Relaxed Video Watching** and **Task Paralysis**, while guaranteeing low false positives during **Normal Reading/Coding**.

### 2.1 Formula Separation Test
$$\text{Separation Ratio} = \frac{\mu_{\text{paralysis}}(\text{Score}) - \mu_{\text{relaxed}}(\text{Score})}{\sqrt{\sigma_{\text{paralysis}}^2 + \sigma_{\text{relaxed}}^2}}$$

Target separation ratio: $\ge 2.5$ standard deviations.

### 2.2 Error Budget & Decision Thresholds
- **Target False Positive Rate (FPR)**: $\le 5\%$ during relaxed watching and regular reading.
- **Target False Negative Rate (FNR)**: $\le 15\%$ during sustained task paralysis (> 90s dwell time).
- In accordance with our ethical non-negotiables, when uncertain between a false positive and false negative, the engine **always defaults to a false negative** (silence).
