"""
test_sequencer.py
Automated test suite for Track 2 (Task Sequencer):
- LLM runtime status checking & graceful handling
- RAG pipeline: ingestion, chunking, deterministic embedding, vector retrieval
- Relevance filtering (top-k and min-relevance thresholding)
- Micro-task progressive decomposition engine ('make_smaller', 'change_approach', 'next_step', 'complete_step', 'take_break')
- Intent parser and capacity constraints
- SQLite persistence of conversations, messages, tasks, feedback, preferences
- Observer and Planner adapters
"""

import os
import tempfile
import time
import pytest

from observer_engine.sequencer.config import SequencerConfig
from observer_engine.sequencer.database import DatabaseManager
from observer_engine.sequencer.rag_engine import RagEngine, LocalEmbeddingVectorizer
from observer_engine.sequencer.intent_parser import IntentParser
from observer_engine.sequencer.decomposition_engine import DecompositionEngine
from observer_engine.sequencer.observer_adapter import ObserverAdapter
from observer_engine.sequencer.planner_adapter import PlannerAdapter
from observer_engine.sequencer.llm_service import LlmService
from observer_engine.sequencer.service import TaskSequencerService
from observer_engine.sequencer.models import (
    TaskRecord,
    MicroStep,
    UserPreferences,
)


@pytest.fixture
def temp_sequencer_env():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test_sequencer.db")
        kb_dir = os.path.join(tmp_dir, "knowledge_base")
        os.makedirs(kb_dir, exist_ok=True)

        # Write dummy curated knowledge
        curated_doc = [
            {
                "doc_id": "TEST-INIT-01",
                "title": "Two-Minute Task Initiation",
                "source_name": "Test Science",
                "url": "https://example.com/init",
                "category": "task_initiation",
                "topic": "Micro-Step Friction Reduction",
                "content": "To overcome task initiation freeze, shrink the first action down to under two minutes. Open the document or editor.",
            },
            {
                "doc_id": "TEST-REST-01",
                "title": "Sensory Decompression Rest",
                "source_name": "Test Rest Org",
                "url": "https://example.com/rest",
                "category": "rest_and_transitions",
                "topic": "Guilt-free Rest",
                "content": "Rest is not earned by productivity; it is a biological requirement for cognitive recovery. Dim lights and close eyes.",
            },
        ]
        import json
        with open(os.path.join(kb_dir, "test_kb.json"), "w", encoding="utf-8") as f:
            json.dump(curated_doc, f)

        cfg = SequencerConfig(
            storage_dir=tmp_dir,
            database_path=db_path,
            knowledge_base_dir=kb_dir,
            min_retrieval_relevance=0.15,
        )
        yield cfg


# -------------------------------------------------------------
# 1. Local Embedding & RAG Engine Tests
# -------------------------------------------------------------
def test_local_embedding_vectorizer():
    vectorizer = LocalEmbeddingVectorizer(dimension=128)
    v1 = vectorizer.embed_text("writing academic research paper")
    v2 = vectorizer.embed_text("writing essay research draft")
    v3 = vectorizer.embed_text("completely unrelated astrophysics pulsar")

    assert len(v1) == 128
    sim_close = vectorizer.cosine_similarity(v1, v2)
    sim_far = vectorizer.cosine_similarity(v1, v3)

    assert sim_close > sim_far
    assert 0.0 <= sim_close <= 1.0


def test_rag_engine_ingestion_and_retrieval(temp_sequencer_env):
    rag = RagEngine(config=temp_sequencer_env)
    assert len(rag.documents) >= 2
    assert len(rag.chunks) >= 2

    # Query for initiation
    matches = rag.retrieve("I cannot start my task opening document", top_k=2)
    assert len(matches) > 0
    assert matches[0].doc_id == "TEST-INIT-01"
    assert "Two-Minute Task Initiation" in matches[0].title
    assert matches[0].relevance_score >= 0.15

    # Irrelevant query filtering
    irrelevant = rag.retrieve("quantum entanglement supercollider", min_relevance=0.45)
    assert len(irrelevant) == 0


def test_rag_index_rebuild(temp_sequencer_env):
    rag = RagEngine(config=temp_sequencer_env)
    res = rag.rebuild_index()
    assert res["status"] == "success"
    assert res["chunks_count"] >= 2
    assert os.path.isfile(rag.index_path)


# -------------------------------------------------------------
# 2. Intent Parser Tests
# -------------------------------------------------------------
def test_intent_parser_categories():
    parser = IntentParser()

    p_break = parser.parse_intent_and_context("I'm so exhausted, I need a break")
    assert p_break["intent"] == "REQUEST_BREAK"

    p_smaller = parser.parse_intent_and_context("That step is way too big and overwhelming")
    assert p_smaller["intent"] == "REDUCE_TASK_SIZE"

    p_approach = parser.parse_intent_and_context("I'm totally stuck, try another approach")
    assert p_approach["intent"] == "CHANGE_APPROACH"

    p_continue = parser.parse_intent_and_context("I completed that step, what is next?")
    assert p_continue["intent"] == "CONTINUE_TASK"


def test_intent_parser_constraints_extraction():
    parser = IntentParser()

    p = parser.parse_intent_and_context("I have 25 minutes to write my history essay, energy is 2/5")
    assert p["time_available_mins"] == 25
    assert p["energy_reported"] == 2
    assert "history essay" in p["task_title"].lower()


# -------------------------------------------------------------
# 3. Micro-Task Progressive Decomposition Engine Tests
# -------------------------------------------------------------
def test_progressive_decomposition():
    decomp = DecompositionEngine()
    task = TaskRecord(
        task_id="t1",
        title="Write Research Paper",
        current_micro_step=MicroStep(
            step_id="s1",
            action_text="Write draft introduction section",
            why_suggested="Initial step",
            estimated_effort="5 mins",
            completed=False,
        ),
    )

    # 1. Make smaller
    smaller = decomp.make_smaller(task)
    assert smaller.step_id != "s1"
    assert "< 60 seconds" in smaller.estimated_effort or "one nonsense word" in smaller.action_text or "open" in smaller.action_text
    assert len(task.step_history) == 1

    # 2. Try another approach
    alt = decomp.change_approach(task)
    assert "dictate" in alt.action_text.lower() or "paper" in alt.action_text.lower() or "voice" in alt.action_text.lower()

    # 3. Complete step
    task_done = decomp.complete_step(task)
    assert task_done.current_micro_step.completed is True

    # 4. Next step
    nxt = decomp.next_step(task_done)
    assert nxt.completed is False
    assert "< 2 minutes" in nxt.estimated_effort

    # 5. Rest transition
    rest = decomp.build_rest_transition(energy_level=1)
    assert rest.intent == "REQUEST_BREAK"
    assert rest.break_option is True
    assert len(rest.sources) > 0


# -------------------------------------------------------------
# 4. Database Persistence Tests
# -------------------------------------------------------------
def test_sqlite_persistence(temp_sequencer_env):
    db = DatabaseManager(db_path=temp_sequencer_env.database_path)

    # Conversations
    conv = db.create_conversation(title="Physics Homework")
    convs = db.list_conversations()
    assert len(convs) == 1
    assert convs[0].title == "Physics Homework"

    # Messages
    m1 = db.save_message(conv.id, "user", "I'm stuck on problem 1")
    m2 = db.save_message(conv.id, "assistant", "Let's read just the first sentence of problem 1.")
    msgs = db.get_conversation_messages(conv.id)
    assert len(msgs) == 2
    assert msgs[0].content == "I'm stuck on problem 1"
    assert msgs[1].sender == "assistant"

    # Tasks
    t = TaskRecord(
        task_id="task_phys_1",
        title="Problem 1",
        current_micro_step=MicroStep(
            step_id="s1",
            action_text="Read problem 1 headline",
            why_suggested="First friction drop",
            estimated_effort="< 60s",
            completed=False,
        ),
    )
    db.save_or_update_task(t, conversation_id=conv.id)
    retrieved_t = db.get_task("task_phys_1")
    assert retrieved_t is not None
    assert retrieved_t.title == "Problem 1"
    assert retrieved_t.current_micro_step.action_text == "Read problem 1 headline"

    # Preferences
    prefs = db.get_preferences()
    assert prefs.energy_level == 3
    prefs.energy_level = 2
    db.update_preferences(prefs)
    assert db.get_preferences().energy_level == 2

    # Cleanup
    db.delete_conversation(conv.id)
    assert len(db.list_conversations()) == 0


# -------------------------------------------------------------
# 5. Observer & Planner Adapters
# -------------------------------------------------------------
def test_observer_adapter():
    adapter = ObserverAdapter()
    assert adapter.get_context_summary() is None  # Initially UNKNOWN/offline

    # Valid tracking event with paralysis
    adapter.update_from_telemetry({
        "vision": {"face_detected": True, "quality_valid": True, "quality_reason": "Good"},
        "prediction": {"state": "PARALYSIS_LIKELY", "confidence": 0.75},
        "ts": time.time(),
    })
    ctx = adapter.get_context_summary()
    assert ctx is not None
    assert "screen fixation" in ctx

    # Invalid tracking should not assume paralysis
    adapter.update_from_telemetry({
        "vision": {"face_detected": False, "quality_valid": False, "quality_reason": "No face"},
        "prediction": {"state": "UNKNOWN", "confidence": 0.0},
        "ts": time.time(),
    })
    assert adapter.get_context_summary() is None


def test_planner_adapter_disconnected():
    adapter = PlannerAdapter()
    assert adapter.is_connected() is False
    assert "disconnected" in adapter.get_status_message()
    assert adapter.get_user_tasks() == []
    prop = adapter.propose_task_creation("New Assignment", "2026-11-01")
    assert prop["requires_user_confirmation"] is True


# -------------------------------------------------------------
# 6. Service Integration & Diagnostics
# -------------------------------------------------------------
def test_task_sequencer_service_actions_and_diagnostics(temp_sequencer_env):
    service = TaskSequencerService(config=temp_sequencer_env)

    # Check status
    st = service.get_status()
    assert st["llm_provider"] == "ollama"
    assert st["rag_index_ready"] is True
    assert st["rag_documents_count"] >= 2

    # Check diagnostics
    diag = service.get_diagnostics()
    assert diag.indexed_documents_count >= 2
    assert "disconnected" in diag.planner_status_message

    # Test progressive action execution
    conv = service.new_conversation("Biology Lab Report")
    msg, contract = service.handle_action(conv.id, "make_smaller")
    assert contract.intent == "REDUCE_TASK_SIZE"
    assert contract.micro_step is not None
    assert len(contract.sources) > 0

    # Test voice-first action aliases: make_easier, explain_another_way, done, say_it_again
    msg_easier, contract_easier = service.handle_action(conv.id, "make_easier")
    assert contract_easier.intent == "REDUCE_TASK_SIZE"
    assert contract_easier.micro_step is not None

    msg_alt, contract_alt = service.handle_action(conv.id, "explain_another_way")
    assert contract_alt.intent == "CHANGE_APPROACH"
    assert contract_alt.micro_step is not None

    msg_rep, contract_rep = service.handle_action(conv.id, "say_it_again")
    assert contract_rep.intent == "REPEAT_STEP"
    assert "Here is your step again" in contract_rep.message

    msg_done, contract_done = service.handle_action(conv.id, "done")
    assert contract_done.intent == "CONTINUE_TASK"
    assert contract_done.current_task.current_micro_step.completed is True

    # Rest action
    msg_rest, contract_rest = service.handle_action(conv.id, "take_break")
    assert contract_rest.intent == "REQUEST_BREAK"
    assert contract_rest.break_option is True
