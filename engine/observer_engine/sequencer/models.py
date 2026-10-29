"""
observer_engine.sequencer.models
Structured Pydantic v2 schemas for Track 2 (Task Sequencer).
Strictly validated request/response models, retrieval citations, and task entities.
"""

from typing import List, Optional, Dict, Any, Literal
import time
from pydantic import BaseModel, Field, ConfigDict


class SourceReference(BaseModel):
    model_config = ConfigDict(extra="ignore")
    doc_id: str
    title: str
    url: str = ""
    author_or_org: str = ""
    category: str = ""
    excerpt: str
    relevance_score: float = Field(ge=0.0, le=1.0)


class MicroStep(BaseModel):
    model_config = ConfigDict(extra="ignore")
    step_id: str
    action_text: str
    why_suggested: str = ""
    estimated_effort: str = "< 2 minutes"
    started_immediately: bool = True
    setup_required: str = "None"
    source_strategy: str = ""
    completed: bool = False
    completed_at: Optional[float] = None


class TaskRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    task_id: str
    title: str
    description: str = ""
    status: Literal["pending", "in_progress", "completed", "paused", "deferred"] = "in_progress"
    current_micro_step: Optional[MicroStep] = None
    step_history: List[MicroStep] = Field(default_factory=list)
    energy_level_reported: int = Field(default=3, ge=1, le=5)
    deadline: Optional[str] = None
    planner_task_id: Optional[str] = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class SequencerResponseContract(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message: str = Field(description="Empathetic, executive-function friendly explanation")
    intent: str = Field(description="Interpreted intent category e.g. START_TASK, REDUCE_TASK_SIZE, etc.")
    current_task: Optional[TaskRecord] = None
    micro_step: Optional[MicroStep] = None
    estimated_effort: str = Field(default="< 2 minutes", description="Qualitative effort estimate")
    alternatives: List[str] = Field(default_factory=list, description="Optional alternative pathways")
    break_option: bool = Field(default=False, description="Whether a gentle rest transition is offered")
    sources: List[SourceReference] = Field(default_factory=list, description="Retrieved RAG citations")
    requires_clarification: bool = Field(default=False, description="True if one concise question is needed")
    limitations: str = Field(default="", description="Relevant uncertainty or missing context")


class UserPreferences(BaseModel):
    model_config = ConfigDict(extra="ignore")
    energy_level: int = Field(default=3, ge=1, le=5)
    preferred_step_size: Literal["micro", "standard", "flexible"] = "micro"
    use_observer_context: bool = True
    use_planner_context: bool = True
    quiet_mode: bool = False
    voice_input_enabled: bool = False


class ConversationMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    conversation_id: str
    sender: Literal["user", "assistant", "system"]
    content: str
    contract: Optional[SequencerResponseContract] = None
    created_at: float = Field(default_factory=time.time)


class ConversationSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    title: str
    message_count: int = 0
    created_at: float
    updated_at: float


class FeedbackRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    feedback_id: str
    conversation_id: str
    step_id: Optional[str] = None
    feedback_type: Literal["helped", "too_big", "wrong_approach", "completed", "declined"]
    user_comment: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)


class SequencerDiagnostics(BaseModel):
    model_config = ConfigDict(extra="ignore")
    llm_provider: str = "ollama"
    model_name: str = "llama3.2:latest"
    ollama_endpoint: str = "http://localhost:11434"
    ollama_connected: bool = False
    model_installed: bool = False
    available_models: List[str] = Field(default_factory=list)
    embedding_model: str = "local_all_minilm"
    vector_index_ready: bool = False
    indexed_documents_count: int = 0
    indexed_chunks_count: int = 0
    last_index_build_ts: float = 0.0
    last_retrieval_query: str = ""
    last_retrieval_matches_count: int = 0
    last_retrieval_latency_ms: float = 0.0
    last_generation_latency_ms: float = 0.0
    observer_integration_active: bool = False
    observer_state_estimate: str = "UNKNOWN"
    planner_integration_active: bool = False
    planner_status_message: str = "Track 3 Planner unavailable"
