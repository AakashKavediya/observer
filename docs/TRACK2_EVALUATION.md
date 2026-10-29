# Track 2 — Task Sequencer: Evaluation & Quality Report

## 1. Evaluation Methodology
Per requirements in Section 18, Track 2 includes an automated benchmark test suite (`observer/engine/tests/test_evaluation.py`) assessing:
1. **Retrieval Relevance**: Does the local RAG engine retrieve genuinely relevant coping strategy documents for specific neurodivergent distress patterns?
2. **Grounding & Provenance**: Are all citations tied to real documents without hallucinating URLs or authors?
3. **Actionability & Step Sizing**: Does the decomposition engine produce an immediate physical action that can be started in under 2 minutes?
4. **Shame & Stigma Absence**: Are patronizing or shame-inducing terms ("lazy", "failure", "procrastinating", "no excuses") strictly excluded from all system outputs?
5. **Capacity Awareness**: Does low energy produce restorative rest or minimal-effort options?

---

## 2. Benchmark Scenario Matrix

| Scenario ID | Test Prompt | Interpreted Intent | Top Retrieved Documents | Actionability (< 2m) | Shame-Free Verified |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **SCENARIO_1** | *"I cannot start my research paper writing, I have been staring at the blank screen for an hour"* | `START_TASK` | `[ACAD-001]` Purdue OWL Junk Draft, `[INIT-001]` 2-Min Physical Threshold | **PASS** (Write junk headline) | **PASS** |
| **SCENARIO_2** | *"I have a massive bug in my authentication backend and cannot start debugging it"* | `START_TASK` | `[CODE-001]` Micro-Debugging Assertion, `[DECOMP-001]` Decomposition | **PASS** (Run test once to check error line) | **PASS** |
| **SCENARIO_3** | *"My reading list has 4 chapters and I feel so overwhelmed by all these choices"* | `START_TASK` | `[OVERLOAD-001]` ASAN Choice Reduction, `[DECOMP-001]` Decomposition | **PASS** (Read 1 bold heading) | **PASS** |
| **SCENARIO_4** | *"My energy is 1/5 and I am completely exhausted, I feel guilty stopping"* | `REQUEST_BREAK` | `[REST-001]` Sensory Rest & Guilt-Free Transitions | **PASS** (3-min dim lighting rest) | **PASS** |
| **SCENARIO_5** | *"That step is still too hard, can we make it smaller?"* | `REDUCE_TASK_SIZE` | `[INIT-001]` Friction Reduction, `[DECOMP-001]` Atomic Breakdown | **PASS** (Subdivided to < 60s) | **PASS** |
| **SCENARIO_6** | *"help"* | `CLARIFICATION_NEEDED` | None (irrelevant query filtered out) | **PASS** (Asks concise question) | **PASS** |

---

## 3. Evaluation Limitations
- Automated testing covers retrieval precision, schema adherence, and terminology filtering.
- It does **not** constitute clinical validation of therapeutic effectiveness.
- The system is explicitly designed and disclosed as an executive-function support tool, not a clinical treatment or diagnosis.
