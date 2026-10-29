# Track 2 — Task Sequencer: Privacy & Local Data Protection

## 1. Zero Cloud Telemetry
- All conversational messages, tasks, feedback, and user preferences are stored strictly in a local SQLite database at:
  - macOS: `~/Library/Application Support/Observer/sequencer/task_sequencer.db`
  - Windows: `%LOCALAPPDATA%\Observer\sequencer\task_sequencer.db`
- No data is ever transmitted to remote analytics, telemetry endpoints, or cloud storage.

---

## 2. Separation from Biometric Stream
- Track 1 video frames, face landmarks, and audio buffers are **never** passed into or stored by the Task Sequencer database.
- Track 1 only provides high-level discrete state summaries (e.g. `PARALYSIS_LIKELY`, `RELAXED`) when tracking is verified and user consent is active.
- Users can disable the use of Observer context in the Task Sequencer with a single toggle in preferences without affecting chat functionality.

---

## 3. Data Retention & Deletion
- Users can delete individual conversations or wipe the entire history at any time:
  - Via UI: Click **History** -> **Clear All History**.
  - Calling Tauri command: `delete_all_data`.
- Deleted conversations, tasks, and feedback are removed immediately from the local SQLite database.

---

## 4. Voice Privacy
- Voice input is push-to-talk only; no continuous ambient microphone monitoring.
- Audio buffers are processed locally and discarded immediately after transcription.
- Voice input cannot execute operating system commands or delete files.
