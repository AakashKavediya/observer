"""
MotionQ Assistive Control System - Word Prediction Engine for Observer
Adapted from MotionQ-blink (keyboard_ui.py)
Copyright (c) 2026 Aakash Kavediya
Licensed under the MIT License. See LICENSE.MotionQ-blink for details.

Multilingual Word Prediction:
- English (EN): Frequency-sorted prefix completions.
- Hindi (HI): Devanagari prefix dictionary from prediction_hi.json.
- Marathi (MR): Devanagari prefix dictionary from prediction_mr.json.
"""

import os
import json
from typing import List, Dict, Any, Optional

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

# Curated English common word corpus (over 120 most common assistive words)
_COMMON_ENGLISH_WORDS = [
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
    "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
    "this", "but", "his", "by", "from", "they", "we", "say", "her", "she",
    "or", "an", "will", "my", "one", "all", "would", "there", "their", "what",
    "so", "up", "out", "if", "about", "who", "get", "which", "go", "me",
    "when", "make", "can", "like", "time", "no", "just", "him", "know", "take",
    "people", "into", "year", "your", "good", "some", "could", "them", "see", "other",
    "than", "then", "now", "look", "only", "come", "its", "over", "think", "also",
    "back", "after", "use", "two", "how", "our", "work", "first", "well", "way",
    "even", "new", "want", "because", "any", "these", "give", "day", "most", "us",
    "please", "help", "water", "food", "need", "yes", "stop", "call", "start", "open"
]


class WordPredictor:
    def __init__(self, assets_dir: Optional[str] = None):
        self.assets_dir = assets_dir or _ASSETS_DIR
        self._pred_hi: Dict[str, Any] = self._load_json("prediction_hi.json")
        self._pred_mr: Dict[str, Any] = self._load_json("prediction_mr.json")

    def _load_json(self, filename: str) -> Dict[str, Any]:
        path = os.path.join(self.assets_dir, filename)
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[WordPredictor] Warning: could not load {filename}: {e}")
        return {}

    def predict(self, prefix: str, language: str = "EN", limit: int = 3) -> List[str]:
        """Return top N predicted words for the current prefix."""
        prefix = (prefix or "").strip()
        if not prefix:
            return []

        lang = language.upper()

        if lang == "EN":
            p_lower = prefix.lower()
            matches = [w for w in _COMMON_ENGLISH_WORDS if w.startswith(p_lower)]
            return matches[:limit]

        elif lang == "HI":
            # Match directly or by first character
            if prefix in self._pred_hi:
                val = self._pred_hi[prefix]
                return list(val.keys())[:limit] if isinstance(val, dict) else val[:limit]
            # Fallback to single character prefix match
            c = prefix[0]
            if c in self._pred_hi:
                val = self._pred_hi[c]
                candidates = list(val.keys()) if isinstance(val, dict) else val
                filtered = [w for w in candidates if w.startswith(prefix)]
                return (filtered or candidates)[:limit]
            return []

        elif lang == "MR":
            if prefix in self._pred_mr:
                val = self._pred_mr[prefix]
                return list(val.keys())[:limit] if isinstance(val, dict) else val[:limit]
            c = prefix[0]
            if c in self._pred_mr:
                val = self._pred_mr[c]
                candidates = list(val.keys()) if isinstance(val, dict) else val
                filtered = [w for w in candidates if w.startswith(prefix)]
                return (filtered or candidates)[:limit]
            return []

        return []
