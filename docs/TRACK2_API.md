# Track 2 — Task Sequencer: API & IPC Contract Specification

All interactions between the frontend, Rust host, and Python backend use Newline-Delimited JSON (NDJSON) over standard pipes.

---

## 1. Incoming Commands (Frontend/Host -> Python Engine)

Commands are sent via Tauri invoke `send_engine_command({ command: { ... } })`:

### `sequencer_send_message`
Submits natural language user text for processing:
```json
{
  "schema_version": "1.0.0",
  "type": "command",
  "name": "sequencer_send_message",
  "conversation_id": "conv_123",
  "message_text": "I can't start my essay",
  "energy_level": 2
}
```

### `sequencer_action`
Executes progressive refinement on the active task:
```json
{
  "schema_version": "1.0.0",
  "type": "command",
  "name": "sequencer_action",
  "conversation_id": "conv_123",
  "action_name": "make_smaller | change_approach | next_step | complete_step | take_break | not_now",
  "task_id": "task_456",
  "feedback_comment": "Optional user comment"
}
```

### `sequencer_get_conversations`
Lists all local conversation summaries:
```json
{
  "schema_version": "1.0.0",
  "type": "command",
  "name": "sequencer_get_conversations"
}
```

### `sequencer_get_conversation`
Loads message history and active task for a conversation:
```json
{
  "schema_version": "1.0.0",
  "type": "command",
  "name": "sequencer_get_conversation",
  "conversation_id": "conv_123"
}
```

### `sequencer_new_conversation`
Initializes a new empty conversation:
```json
{
  "schema_version": "1.0.0",
  "type": "command",
  "name": "sequencer_new_conversation",
  "title": "Optional Title"
}
```

### `sequencer_delete_conversation`
Deletes a conversation and its messages:
```json
{
  "schema_version": "1.0.0",
  "type": "command",
  "name": "sequencer_delete_conversation",
  "conversation_id": "conv_123"
}
```

### `sequencer_rebuild_index`
Re-indexes and computes local vector embeddings for all curated knowledge documents:
```json
{
  "schema_version": "1.0.0",
  "type": "command",
  "name": "sequencer_rebuild_index"
}
```

### `sequencer_get_diagnostics`
Retrieves live LLM, RAG, and integration metrics:
```json
{
  "schema_version": "1.0.0",
  "type": "command",
  "name": "sequencer_get_diagnostics"
}
```

---

## 2. Outgoing Events (Python Engine -> Frontend)

Events are emitted over Tauri event bus as `"engine://event"`:

### `sequencer_response`
Emitted when a conversational response or action is produced:
```json
{
  "schema_version": "1.0.0",
  "type": "sequencer_response",
  "conversation_id": "conv_123",
  "message_id": "msg_789",
  "contract": {
    "message": "Let's take a single tiny step to overcome activation inertia.",
    "intent": "START_TASK",
    "micro_step": {
      "step_id": "s1",
      "action_text": "Open your document and write a temporary title.",
      "why_suggested": "Reduces activation threshold below cognitive resistance.",
      "estimated_effort": "< 60 seconds",
      "started_immediately": true,
      "completed": false
    },
    "estimated_effort": "< 60 seconds",
    "alternatives": ["Voice dictation", "Handwritten outline"],
    "break_option": false,
    "sources": [
      {
        "doc_id": "INIT-001",
        "title": "Activation & The 2-Minute Physical Threshold",
        "url": "https://www.additudemag.com/how-to-start-a-task-adhd-activation/",
        "author_or_org": "Ellen Littman, Ph.D. / ADDitude",
        "category": "task_initiation",
        "excerpt": "The neurological cost of task initiation is vastly higher than continuing a task.",
        "relevance_score": 0.88
      }
    ],
    "requires_clarification": false,
    "limitations": ""
  },
  "task": {
    "task_id": "task_456",
    "title": "Research Paper",
    "status": "in_progress",
    "current_micro_step": { ... },
    "step_history": [ ... ]
  }
}
```

### `sequencer_status`
Emitted on startup and status query:
```json
{
  "schema_version": "1.0.0",
  "type": "sequencer_status",
  "llm_provider": "ollama",
  "model_name": "llama3.2:latest",
  "ollama_connected": true,
  "model_installed": true,
  "available_models": ["llama3.2:latest"],
  "rag_index_ready": true,
  "rag_documents_count": 9,
  "rag_chunks_count": 9,
  "error_message": null
}
```
