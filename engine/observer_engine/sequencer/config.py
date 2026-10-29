"""
observer_engine.sequencer.config
Centralized configuration for Track 2 (Task Sequencer).
Manages model parameters, timeouts, RAG thresholds, and persistence paths.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SequencerConfig:
    # LLM Settings
    llm_provider: str = "ollama"
    ollama_endpoint: str = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    model_name: str = os.environ.get("OBSERVER_LLM_MODEL", "llama3.2:latest")
    request_timeout: float = 20.0
    generation_timeout: float = 45.0
    max_input_length: int = 4000
    max_generated_tokens: int = 1024

    # Embedding & RAG Settings
    embedding_model: str = "local_tfidf_minilm"
    retrieval_top_k: int = 4
    min_retrieval_relevance: float = 0.20
    chunk_size_words: int = 180
    chunk_overlap_words: int = 35

    # Memory & Context Settings
    conversation_history_limits: int = 10

    # Optional External API (Must never activate automatically without explicit opt-in)
    external_api_enabled: bool = False
    external_api_provider: str = ""
    external_api_key: str = ""

    # Paths
    storage_dir: Optional[str] = None
    database_path: Optional[str] = None
    knowledge_base_dir: Optional[str] = None

    def __post_init__(self):
        if not self.storage_dir:
            home = os.path.expanduser("~")
            if os.name == "nt":
                base = os.environ.get("LOCALAPPDATA", os.path.join(home, "AppData", "Local"))
            elif getattr(os, "uname", None) and os.uname().sysname == "Darwin":
                base = os.path.join(home, "Library", "Application Support")
            else:
                base = os.path.join(home, ".local", "share")
            self.storage_dir = os.path.join(base, "Observer", "sequencer")

        os.makedirs(self.storage_dir, exist_ok=True)

        if not self.database_path:
            self.database_path = os.path.join(self.storage_dir, "task_sequencer.db")

        if not self.knowledge_base_dir:
            # Look in observer_engine/sequencer/knowledge_base
            curr_dir = os.path.dirname(os.path.abspath(__file__))
            self.knowledge_base_dir = os.path.join(curr_dir, "knowledge_base")

        os.makedirs(self.knowledge_base_dir, exist_ok=True)


SEQUENCER_CONFIG = SequencerConfig()
