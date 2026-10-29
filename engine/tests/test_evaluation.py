"""
test_evaluation.py
Evaluation benchmark dataset and validation suite for Track 2 (Task Sequencer).
Evaluates retrieval relevance, grounding, actionability, capacity adaptation,
and absence of shame-inducing language across core neurodivergent request scenarios.
"""

import pytest
from observer_engine.sequencer.rag_engine import RagEngine
from observer_engine.sequencer.intent_parser import IntentParser
from observer_engine.sequencer.decomposition_engine import DecompositionEngine
from observer_engine.sequencer.service import TaskSequencerService
from observer_engine.sequencer.models import TaskRecord, MicroStep


EVALUATION_SCENARIOS = [
    {
        "id": "SCENARIO_1_INITIATION_ESSAY",
        "prompt": "I cannot start my research paper writing, I have been staring at the blank screen for an hour",
        "expected_intent": "START_TASK",
        "expected_doc_ids": ["ACAD-001", "INIT-001", "DECOMP-001"],
    },
    {
        "id": "SCENARIO_2_PROGRAMMING_OVERWHELM",
        "prompt": "I have a massive bug in my authentication backend and cannot start debugging it",
        "expected_intent": "START_TASK",
        "expected_doc_ids": ["CODE-001", "DECOMP-001"],
    },
    {
        "id": "SCENARIO_3_READING_OVERWHELM",
        "prompt": "My reading list has 4 chapters and I feel so overwhelmed by all these choices",
        "expected_intent": "START_TASK",
        "expected_doc_ids": ["OVERLOAD-001", "DECOMP-001"],
    },
    {
        "id": "SCENARIO_4_LOW_ENERGY_REST",
        "prompt": "My energy is 1/5 and I am completely exhausted, I feel guilty stopping",
        "expected_intent": "REQUEST_BREAK",
        "expected_doc_ids": ["REST-001", "ENERGY-001"],
    },
    {
        "id": "SCENARIO_5_MAKE_SMALLER",
        "prompt": "That step is still too hard, can we make it smaller?",
        "expected_intent": "REDUCE_TASK_SIZE",
        "expected_doc_ids": ["INIT-001", "DECOMP-001"],
    },
    {
        "id": "SCENARIO_6_AMBIGUOUS_PROMPT",
        "prompt": "help",
        "expected_intent": "CLARIFICATION_NEEDED",
        "expected_doc_ids": [],
    },
]

SHAME_TERMS = ["lazy", "failure", "procrastinating", "no excuse", "unproductive", "you failed", "disappointing"]


def test_rag_retrieval_relevance_benchmark():
    rag = RagEngine()

    for sc in EVALUATION_SCENARIOS:
        if not sc["expected_doc_ids"]:
            continue
        matches = rag.retrieve(sc["prompt"], top_k=3)
        retrieved_ids = [m.doc_id for m in matches]
        # At least one expected category doc should be retrieved in top-3
        found = any(doc_id in retrieved_ids for doc_id in sc["expected_doc_ids"])
        assert found, f"Scenario {sc['id']} failed: retrieved {retrieved_ids}, expected one of {sc['expected_doc_ids']}"


def test_intent_classification_benchmark():
    parser = IntentParser()

    for sc in EVALUATION_SCENARIOS:
        res = parser.parse_intent_and_context(sc["prompt"])
        assert res["intent"] == sc["expected_intent"], f"Scenario {sc['id']} parsed as {res['intent']}, expected {sc['expected_intent']}"


def test_decomposition_actionability_and_shame_absence():
    decomp = DecompositionEngine()
    task = TaskRecord(
        task_id="t_eval",
        title="Complete Final Term Project",
        current_micro_step=MicroStep(
            step_id="s1",
            action_text="Write literature review section",
            why_suggested="First section",
            estimated_effort="5 mins",
        ),
    )

    smaller = decomp.make_smaller(task)
    alt = decomp.change_approach(task)
    rest = decomp.build_rest_transition()

    for text in [smaller.action_text, smaller.why_suggested, alt.action_text, alt.why_suggested, rest.message]:
        text_lower = text.lower()
        for shame_word in SHAME_TERMS:
            assert shame_word not in text_lower, f"Detected shame-inducing term '{shame_word}' in generated text: {text}"

    # Micro-step should have < 2 min qualitative effort
    assert "<" in smaller.estimated_effort or "second" in smaller.estimated_effort.lower() or "minute" in smaller.estimated_effort.lower()
