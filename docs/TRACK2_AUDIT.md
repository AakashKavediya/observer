# Track 2 — Task Sequencer: Implementation Audit & Architecture Plan

**Audit Timestamp:** 2026-10-29  
**Application:** Observer Desktop (Tauri 2 + React 18 + Rust + Python Sidecar)

---

## 1. Existing System Audit

| Subsystem | Existing Implementation | Status | Reuse Strategy for Track 2 |
| :--- | :--- | :--- | :--- |
| **Desktop Shell** | Tauri 2 (Rust) + React 18 (TypeScript) + Tailwind CSS + Zustand | **Implemented & Verified** | Reused directly. React UI handles conversational screens; Rust forwards commands to Python sidecar. |
| **IPC Bridge** | Stdin/Stdout NDJSON between Rust `sidecar.rs` and Python `main.py` | **Implemented & Verified** | Reused directly. Extend `CommandMessage` in `ipc.py` and Rust `send_engine_command`. |
| **Track 1 Observer** | OpenCV camera capture, MediaPipe Face Landmarker, tension/gaze/blink extraction, state engine | **Implemented & Verified** | Integrate via `ObserverAdapter`. Consumes state (`RELAXED`, `FOCUSED`, `PARALYSIS_LIKELY`, `UNKNOWN`) only when valid and consented. |
| **Persistence** | Host JSON files for settings (`SettingsManager`) & history (`HistoryManager`) | **Implemented & Verified** | Use local SQLite (`task_sequencer.db`) for conversational turns, tasks, feedback, and user preferences. |
| **LLM Runtime** | None | **Missing** | Implement `LlmService` interfacing with local Ollama (`http://localhost:11434`), model reachability checks, timeouts, and JSON contract validation. |
| **RAG & Vector Retrieval** | None | **Missing** | Implement `RagEngine` with curated knowledge base, chunking, metadata preservation, local embedding generation, and cosine similarity vector retrieval. |
| **Micro-Task Decomposition** | Static intervention strings only | **Missing** | Implement progressive decomposition engine (`DecompositionEngine`) supporting "Make it smaller", "Try another approach", "I completed this", and "Take a break". |
| **Track 3 Planner** | None | **Missing** | Implement `PlannerAdapter` with safe interface, explicit confirmation guards, and transparent "Unavailable" status. |

---

## 2. Track 2 Architecture & Data Flow

```
[React Frontend: TaskSequencerScreen]
       │
       ▼ (Tauri IPC: send_engine_command)
[Rust commands.rs -> sidecar.rs (stdin)]
       │
       ▼ (NDJSON stdin)
[Python observer_engine: main.py]
       │
       ├─► [DatabaseManager (SQLite)]
       │     ├── conversations, messages, tasks, feedback, preferences
       │
       ├─► [ObserverAdapter] ── consumes Track 1 Telemetry/StateEvent
       ├─► [PlannerAdapter]  ── Track 3 Contract (Graceful fallback)
       │
       ├─► [IntentParser]    ── Identifies intent & extracts constraints
       │
       ├─► [RagEngine]       ── Local embedding & vector similarity
       │     └── [KnowledgeBase] (7 Curated Categories)
       │
       ├─► [DecompositionEngine] ── Progressive micro-step refinement
       │
       └─► [LlmService]      ── Ollama local inference (llama3.2 / mistral)
             │
             ▼ (Structured JSON validation)
       [NDJSON stdout -> Rust sidecar.rs -> Tauri emit("engine://event")]
             │
             ▼
[React Zustand Store -> TaskSequencerScreen & Diagnostics View]
```

---

## 3. Technology Choices & Rationale

1. **LLM Runtime (Ollama)**:
   - 100% offline, local inference via standard HTTP API (`http://localhost:11434`).
   - Zero cloud telemetry or data leakage.
   - Honest setup state: if Ollama is not running, clearly displays status and retry button without fake fallback.
2. **Local Vector Retrieval**:
   - Curated knowledge documents embedded using local vector representations and cached in local SQLite/JSON index.
   - Supports live rebuilding, top-k retrieval, relevance thresholding, and full citation attribution.
3. **Structured Validation**:
   - Pydantic v2 models validate every LLM response against `SequencerResponseContract`.
   - Prevents hallucinations from breaking UI or task state.
4. **Local SQLite Persistence**:
   - Clean, lightweight, relational storage for conversation history and micro-tasks at `~/Library/Application Support/Observer/task_sequencer.db`.
