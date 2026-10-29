"""
observer_engine.sequencer.decomposition_engine
Micro-task progressive decomposition engine.
Transforms overwhelming tasks into immediate, atomic physical actions (< 2 minutes).
Handles progressive user actions: 'Make it smaller', 'Try another approach',
'Next step', 'Complete step', and 'Take a break'.
"""

import time
import uuid
from typing import Optional, Dict, Any, List

from observer_engine.sequencer.models import (
    MicroStep,
    TaskRecord,
    SequencerResponseContract,
    SourceReference,
)


class DecompositionEngine:
    def __init__(self):
        pass

    # -------------------------------------------------------------
    # Progressive Refinements
    # -------------------------------------------------------------
    def make_smaller(self, task: TaskRecord) -> MicroStep:
        """
        Reduces current action below the threshold of neurological resistance.
        If the user hesitated or found the previous step too demanding, subdivides it further.
        """
        curr = task.current_micro_step
        curr_text = curr.action_text if curr else task.title

        # Decomposition ladders for common domains
        smaller_text = f"Open the file or window related to: {curr_text}"
        if "open" in curr_text.lower():
            smaller_text = "Take one slow breath and relax your shoulders while looking at the screen."
        elif "write" in curr_text.lower():
            smaller_text = "Write just a single temporary placeholder sentence or word."
        elif "read" in curr_text.lower():
            smaller_text = "Read only the very first sentence or bold headline."
        elif "debug" in curr_text.lower() or "code" in curr_text.lower():
            smaller_text = "Run the failing command once to look at the error line number."
        elif "organize" in curr_text.lower() or "clean" in curr_text.lower():
            smaller_text = "Pick up and organize exactly one item."

        new_step = MicroStep(
            step_id=f"step_{int(time.time()*1000)}_{uuid.uuid4().hex[:4]}",
            action_text=smaller_text,
            why_suggested="Reduced step size to remove activation resistance.",
            estimated_effort="< 60 seconds",
            started_immediately=True,
            setup_required="None",
            source_strategy="Atomic Task Decomposition (DECOMP-001)",
        )

        task.current_micro_step = new_step
        task.step_history.append(new_step)
        return new_step

    def change_approach(self, task: TaskRecord) -> MicroStep:
        """
        Proposes a materially different modality/strategy when user is blocked on the current angle.
        """
        curr = task.current_micro_step
        curr_text = curr.action_text if curr else task.title

        alternatives = [
            f"Dictate your thoughts into an audio memo about: {task.title}",
            f"Sketch or jot one rough bullet point on physical paper for: {task.title}",
            f"Explain what you need to do out loud as if explaining to a friend.",
            f"Browse one reference example or past template before attempting your own draft.",
        ]

        # Pick alternative different from current strategy
        chosen = alternatives[0]
        for alt in alternatives:
            if alt[:15].lower() not in (curr.why_suggested.lower() if curr else ""):
                chosen = alt
                break

        new_step = MicroStep(
            step_id=f"step_{int(time.time()*1000)}_{uuid.uuid4().hex[:4]}",
            action_text=chosen,
            why_suggested="Switched sensory modality to bypass cognitive bottleneck.",
            estimated_effort="< 2 minutes",
            started_immediately=True,
            setup_required="None",
            source_strategy="Sensory & Modality Switching (ACAD-001)",
        )

        task.current_micro_step = new_step
        task.step_history.append(new_step)
        return new_step

    def next_step(self, task: TaskRecord) -> MicroStep:
        """
        Advances the task to the next logical atomic action.
        """
        completed_count = len([s for s in task.step_history if s.completed])
        next_actions = [
            f"Review what you just did for 30 seconds: '{task.current_micro_step.action_text if task.current_micro_step else task.title}'",
            f"Add one more sentence or bullet point to expand on your progress.",
            f"Save the document or commit your changes so far.",
            f"Decide on the next single 2-minute chunk for: {task.title}",
        ]
        chosen = next_actions[min(completed_count, len(next_actions) - 1)]

        new_step = MicroStep(
            step_id=f"step_{int(time.time()*1000)}_{uuid.uuid4().hex[:4]}",
            action_text=chosen,
            why_suggested="Advancing momentum with next atomic step.",
            estimated_effort="< 2 minutes",
            started_immediately=True,
            setup_required="None",
            source_strategy="Progressive Momentum (DECOMP-001)",
        )

        task.current_micro_step = new_step
        task.step_history.append(new_step)
        return new_step

    def complete_step(self, task: TaskRecord) -> TaskRecord:
        """
        Marks current step as completed without putting pressure to finish everything.
        """
        if task.current_micro_step:
            task.current_micro_step.completed = True
            task.current_micro_step.completed_at = time.time()
            for s in task.step_history:
                if s.step_id == task.current_micro_step.step_id:
                    s.completed = True
                    s.completed_at = time.time()
        return task

    def build_rest_transition(self, energy_level: int = 2) -> SequencerResponseContract:
        """
        Offers an unconditional, shame-free sensory rest transition.
        """
        rest_steps = [
            "Step away from the screen for 3 minutes and close your eyes in dim lighting.",
            "Take 5 slow breaths and stretch your shoulders without checking any devices.",
            "Drink a glass of cold water and rest your eyes.",
        ]
        chosen = rest_steps[0] if energy_level <= 2 else rest_steps[1]

        step = MicroStep(
            step_id=f"rest_{int(time.time())}",
            action_text=chosen,
            why_suggested="Rest is essential for executive function replenishment, not a reward to be earned.",
            estimated_effort="3 minutes",
            started_immediately=True,
            setup_required="None",
            source_strategy="Sensory Decompression & Rest (REST-001)",
        )

        return SequencerResponseContract(
            message="Rest is a biological requirement for executive function. Take a brief sensory breather with zero guilt.",
            intent="REQUEST_BREAK",
            micro_step=step,
            estimated_effort="3 minutes",
            alternatives=["Close eyes for 2 mins", "Drink water", "Gentle stretch"],
            break_option=True,
            sources=[
                SourceReference(
                    doc_id="REST-001",
                    title="Sensory Decompression & Guilt-Free Transitions to Rest",
                    url="https://www.autism.org.uk/advice-and-guidance/topics/sensory-differences",
                    author_or_org="National Autistic Society (UK)",
                    category="rest_and_transitions",
                    excerpt="Rest is not a reward earned by productivity; it is a biological requirement for executive function recovery.",
                    relevance_score=0.95,
                )
            ],
            requires_clarification=False,
            limitations="Rest restores capacity; returning to work later will feel more accessible.",
        )
