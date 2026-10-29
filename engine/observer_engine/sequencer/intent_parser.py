"""
observer_engine.sequencer.intent_parser
Parses user natural language requests into structured intent categories and extracts
explicit task parameters, constraints, and energy states.
Distinguishes explicit user statements from uncertain inferences.
"""

import re
from typing import Dict, Any, Optional, Tuple, List


INTENT_CATEGORIES = [
    "START_TASK",
    "BREAK_DOWN_TASK",
    "CONTINUE_TASK",
    "REDUCE_TASK_SIZE",
    "CHANGE_APPROACH",
    "PLAN_TASK",
    "UNDERSTAND_OVERWHELM",
    "REQUEST_BREAK",
    "RESUME_AFTER_BREAK",
    "UPDATE_ENERGY",
    "QUERY_EXISTING_TASK",
    "GENERAL_QUESTION",
    "CLARIFICATION_NEEDED",
]


class IntentParser:
    def parse_intent_and_context(self, user_text: str) -> Dict[str, Any]:
        """
        Extracts structured intent and explicit parameters from user prompt.
        """
        text_lower = user_text.lower().strip()

        # 1. Detect Intent Category using word boundaries
        intent = "START_TASK"
        if re.search(r"\b(take a break|need a break|rest|tired|exhausted|pause|stop for now|need a breather)\b", text_lower):
            intent = "REQUEST_BREAK"
        elif re.search(r"\b(make it smaller|smaller|too hard|too big|can't do that|cannot do that|overwhelming|simpler|tiny)\b", text_lower):
            intent = "REDUCE_TASK_SIZE"
        elif re.search(r"\b(different approach|another approach|another way|stuck|different angle|alternative)\b", text_lower):
            intent = "CHANGE_APPROACH"
        elif re.search(r"\b(i'm done|finished|completed this|completed|did that|show next step)\b", text_lower):
            intent = "CONTINUE_TASK"
        elif re.search(r"\b(resume work|back to work|ready now|ready to resume)\b", text_lower):
            intent = "RESUME_AFTER_BREAK"
        elif re.search(r"\b(break down|break into steps|chunk|how do i organize)\b", text_lower):
            intent = "BREAK_DOWN_TASK"
        elif re.search(r"\b(energy is|spoons|battery|feeling a 1|feeling a 2|feeling a 5)\b", text_lower):
            intent = "UPDATE_ENERGY"
        elif re.search(r"\b(what is|why is|explain to me|how does)\b", text_lower):
            intent = "GENERAL_QUESTION"
        elif len(text_lower.split()) < 2:
            intent = "CLARIFICATION_NEEDED"

        # 2. Extract Explicit Constraints (Time, Energy, Task Title)
        time_available = self._extract_time_minutes(text_lower)
        energy_reported = self._extract_energy_level(text_lower)
        task_title = self._extract_task_title(user_text)

        return {
            "intent": intent,
            "task_title": task_title,
            "time_available_mins": time_available,
            "energy_reported": energy_reported,
            "explicit_text": user_text,
            "is_ambiguous": (intent == "CLARIFICATION_NEEDED" or len(text_lower.split()) <= 1),
        }

    def _extract_time_minutes(self, text: str) -> Optional[int]:
        m = re.search(r"(\d+)\s*(?:min|minute|mins|minutes)", text)
        if m:
            return int(m.group(1))
        h = re.search(r"(\d+)\s*(?:hour|hours|hr|hrs)", text)
        if h:
            return int(h.group(1)) * 60
        return None

    def _extract_energy_level(self, text: str) -> Optional[int]:
        m = re.search(r"(?:energy|level|spoon|battery)\s*(?:is|at|of)?\s*([1-5])(?:\s*/\s*5)?", text)
        if m:
            return int(m.group(1))
        return None

    def _extract_task_title(self, text: str) -> str:
        # Strip time phrases
        cleaned = re.sub(r"(?:i have\s+)?\d+\s*(?:min|minute|mins|minutes|hour|hours|hr|hrs)(?:\s+to)?", "", text, flags=re.IGNORECASE)
        # Strip energy phrases
        cleaned = re.sub(r",?\s*(?:energy|level|spoon|battery)\s*(?:is|at|of)?\s*[1-5](?:\s*/\s*5)?", "", cleaned, flags=re.IGNORECASE)
        # Strip common prefixes
        cleaned = re.sub(
            r"^(i need to|i have to|help me with|can you help me|i want to|i'm trying to|to)\s+",
            "",
            cleaned.strip(),
            flags=re.IGNORECASE,
        ).strip()
        words = cleaned.split()
        if len(words) > 10:
            return " ".join(words[:10]) + "..."
        return cleaned or "My Task"
