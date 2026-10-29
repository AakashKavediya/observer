# Track 2 — Task Sequencer: Automated Testing Guide

## 1. Test Overview

The Track 2 implementation includes automated tests across both the Python sidecar backend and the React frontend.

---

## 2. Python Backend Tests

To run the Python test suite:
```bash
# From workspace root
PYTHONPATH=observer/engine python3 -m pytest observer/engine/tests/test_sequencer.py observer/engine/tests/test_evaluation.py
```

### Tested Coverage:
1. **Local Vectorizer & RAG Engine**:
   - `test_local_embedding_vectorizer`: Verifies 256-dim normalization and cosine similarity properties.
   - `test_rag_engine_ingestion_and_retrieval`: Validates document parsing, chunking, and similarity ranking.
   - `test_rag_index_rebuild`: Validates index rebuild and JSON persistence.
2. **Intent Parser & Constraints Extraction**:
   - `test_intent_parser_categories`: Validates 13 intent categories with regex word-boundary precision.
   - `test_intent_parser_constraints_extraction`: Validates extraction of available minutes, energy ratings (1-5), and clean task titles.
3. **Micro-Task Decomposition Engine**:
   - `test_progressive_decomposition`: Validates `make_smaller`, `change_approach`, `complete_step`, `next_step`, and `take_break`.
4. **SQLite Persistence**:
   - `test_sqlite_persistence`: Validates conversations, messages, tasks, feedback records, and user preferences.
5. **Observer & Planner Adapters**:
   - `test_observer_adapter`: Validates safe state translation and UNKNOWN state non-paralysis guarantee.
   - `test_planner_adapter_disconnected`: Validates clean unavailable reporting.

---

## 3. React Frontend Tests

To run the frontend Vitest suite:
```bash
cd observer && npm test
```

### Tested Coverage:
1. `renders Task Sequencer header and input field`
2. `renders proposed micro-step hero card with 1-click action buttons`
3. `allows expanding grounded RAG citations to view source metadata`
4. `updates capacity energy level when pill is clicked`

---

## 4. Rust Core Tests

To run Rust unit tests:
```bash
cd observer/src-tauri && cargo test
```
All 3 unit tests pass in under 0.05 seconds.
