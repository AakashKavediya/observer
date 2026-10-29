# Track 2 — Task Sequencer: Architecture & System Design

## 1. Overview
The Task Sequencer is Track 2 of the Observer ecosystem. While Track 1 monitors behavioral and physiological context (webcam gaze dispersion, facial tension, blink anomalies, keyboard/mouse stillness), Track 2 acts as a specialized executive-function support tool.

It translates unstructured feelings of paralysis or overwhelming projects into **one microscopic, actionable step (< 2 minutes)**, grounded in traceable coping strategies from a curated vector knowledge base.

---

## 2. Logical Subsystems

```
┌─────────────────────────────────────────────────────────────┐
│                 React Frontend (Tauri 2)                    │
│   - TaskSequencerScreen.tsx                                 │
│   - Hero Micro-Step Card & 1-Click Refinements              │
│   - RAG Grounding Citation Drawers                          │
│   - Capacity Energy Slider (1 to 5)                         │
│   - SequencerDiagnosticsModal.tsx                           │
└──────────────────────────────┬──────────────────────────────┘
                               │ Tauri IPC: send_engine_command
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 Rust Tauri Core (src-tauri)                 │
│   - commands.rs -> sidecar.rs (stdin NDJSON)                │
│   - sidecar.rs stdout -> Tauri emit("engine://event")       │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│              Python Sidecar (observer_engine)               │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │ TaskSequencerService (Coordinator)                  │   │
│   │                                                     │   │
│   │   ├── DatabaseManager (SQLite: task_sequencer.db)   │   │
│   │   │     - conversations, messages, tasks, feedback  │   │
│   │   │                                                 │   │
│   │   ├── IntentParser                                  │   │
│   │   │     - 13 structured categories & constraints    │   │
│   │   │                                                 │   │
│   │   ├── RagEngine (Local Vector Retrieval)            │   │
│   │   │     - LocalEmbeddingVectorizer (256-dim)        │   │
│   │   │     - Curated Knowledge Base (7 categories)     │   │
│   │   │                                                 │   │
│   │   ├── DecompositionEngine                           │   │
│   │   │     - make_smaller, change_approach, next_step  │   │
│   │   │     - complete_step, take_break, not_now        │   │
│   │   │                                                 │   │
│   │   ├── ObserverAdapter (Track 1 Telemetry Consumer)  │   │
│   │   │                                                 │   │
│   │   ├── PlannerAdapter (Track 3 Safe Interface)       │   │
│   │   │                                                 │   │
│   │   └── LlmService (Ollama Local API Client)          │   │
│   │         - http://localhost:11434/api/chat           │   │
│   │         - Pydantic SequencerResponseContract        │   │
│   └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Data Flow

1. **User Prompt**: The user types a problem (e.g. *"I cannot start my research paper, I have 30 minutes, energy is 2/5"*).
2. **Intent Parsing**: `IntentParser` classifies intent (`START_TASK`), extracts available time (`30 mins`), and reads stated energy (`2/5`).
3. **RAG Vector Search**: `RagEngine` generates subword n-gram vector embedding, queries the local index, filters matches below `min_relevance=0.20`, and retrieves top citations (e.g. `[ACAD-001]`, `[INIT-001]`).
4. **Context Gathering**: `ObserverAdapter` provides recent valid Track 1 state (if consented); `PlannerAdapter` verifies task status.
5. **Local LLM Inference**: `LlmService` calls Ollama (`http://localhost:11434/api/chat`) with strict JSON schema instructions.
6. **Validation & Persistence**: Response is parsed into `SequencerResponseContract`, stored in `task_sequencer.db`, and emitted to the UI as `SequencerResponseEvent`.
7. **Progressive Refinement**: User can click `Make it smaller`, `Try another approach`, `I completed this`, or `Take a break`.
