"""
observer_engine.sequencer.service
Central coordinator for Track 2 (Task Sequencer).
Coordinates RAG retrieval, LLM generation, micro-task progressive decomposition,
database persistence, and Observer/Planner adapters.
"""

import time
import uuid
import threading
from typing import Dict, Any, Optional, List, Tuple

from observer_engine.sequencer.config import SequencerConfig, SEQUENCER_CONFIG
from observer_engine.sequencer.models import (
    SequencerResponseContract,
    MicroStep,
    TaskRecord,
    SourceReference,
    ConversationMessage,
    ConversationSummary,
    UserPreferences,
    SequencerDiagnostics,
)
from observer_engine.sequencer.database import DatabaseManager
from observer_engine.sequencer.llm_service import LlmService
from observer_engine.sequencer.rag_engine import RagEngine
from observer_engine.sequencer.intent_parser import IntentParser
from observer_engine.sequencer.decomposition_engine import DecompositionEngine
from observer_engine.sequencer.observer_adapter import ObserverAdapter
from observer_engine.sequencer.planner_adapter import PlannerAdapter


class TaskSequencerService:
    def __init__(self, config: SequencerConfig = SEQUENCER_CONFIG):
        self.config = config
        self.db = DatabaseManager(db_path=config.database_path)
        self.llm = LlmService(config=config)
        self.rag = RagEngine(config=config)
        self.intent_parser = IntentParser()
        self.decomposition = DecompositionEngine()
        self.observer_adapter = ObserverAdapter()
        self.planner_adapter = PlannerAdapter()

        self._cancel_event = threading.Event()

    # -------------------------------------------------------------
    # Status & Diagnostics
    # -------------------------------------------------------------
    def get_status(self) -> Dict[str, Any]:
        llm_status = self.llm.check_runtime_status()
        return {
            "llm_provider": self.config.llm_provider,
            "model_name": self.config.model_name,
            "ollama_connected": llm_status["ollama_connected"],
            "model_installed": llm_status["model_installed"],
            "available_models": llm_status["available_models"],
            "rag_index_ready": len(self.rag.chunks) > 0,
            "rag_documents_count": len(self.rag.documents),
            "rag_chunks_count": len(self.rag.chunks),
            "error_message": llm_status["error_message"],
        }

    def get_diagnostics(self) -> SequencerDiagnostics:
        st = self.get_status()
        prefs = self.db.get_preferences()
        return SequencerDiagnostics(
            llm_provider=self.config.llm_provider,
            model_name=self.config.model_name,
            ollama_endpoint=self.config.ollama_endpoint,
            ollama_connected=st["ollama_connected"],
            model_installed=st["model_installed"],
            available_models=st["available_models"],
            embedding_model=self.config.embedding_model,
            vector_index_ready=len(self.rag.chunks) > 0,
            indexed_documents_count=len(self.rag.documents),
            indexed_chunks_count=len(self.rag.chunks),
            last_index_build_ts=self.rag.last_index_build_ts,
            last_retrieval_query=self.rag.last_retrieval_query,
            last_retrieval_matches_count=self.rag.last_retrieval_matches_count,
            last_retrieval_latency_ms=self.rag.last_retrieval_latency_ms,
            last_generation_latency_ms=self.llm.last_generation_latency_ms,
            observer_integration_active=self.observer_adapter.enabled and prefs.use_observer_context,
            observer_state_estimate=self.observer_adapter.latest_state,
            planner_integration_active=self.planner_adapter.is_connected() and prefs.use_planner_context,
            planner_status_message=self.planner_adapter.get_status_message(),
        )

    def rebuild_rag_index(self) -> Dict[str, Any]:
        return self.rag.rebuild_index()

    # -------------------------------------------------------------
    # Conversational Message Processing
    # -------------------------------------------------------------
    def send_message(
        self,
        conversation_id: Optional[str],
        user_text: str,
        energy_level: Optional[int] = None,
        voice_input: bool = False,
    ) -> Tuple[ConversationMessage, SequencerResponseContract]:
        """
        Processes user request through intent parsing, RAG retrieval, and LLM inference.
        """
        self._cancel_event.clear()

        # 1. Resolve or create conversation
        if not conversation_id:
            summary = self.db.create_conversation(title=user_text[:35] + ("..." if len(user_text) > 35 else ""))
            conversation_id = summary.id

        prefs = self.db.get_preferences()
        effective_energy = energy_level if energy_level is not None else prefs.energy_level

        # 2. Save user message
        self.db.save_message(conversation_id=conversation_id, sender="user", content=user_text)

        # 3. Intent parsing & context extraction
        parsed = self.intent_parser.parse_intent_and_context(user_text)
        if parsed.get("energy_reported"):
            effective_energy = parsed["energy_reported"]

        # 4. RAG Retrieval from curated knowledge base
        retrieved_sources = self.rag.retrieve(user_text)

        # 5. Retrieve existing task context
        latest_task = self.db.get_latest_task_for_conversation(conversation_id)

        # 6. Gather observer & planner context
        obs_ctx = self.observer_adapter.get_context_summary() if prefs.use_observer_context else None
        plan_ctx = self.planner_adapter.get_status_message() if prefs.use_planner_context else None

        # 7. Check if user is explicitly asking for rest or low-spoons break
        if parsed["intent"] == "REQUEST_BREAK":
            contract = self.decomposition.build_rest_transition(energy_level=effective_energy)
            asst_msg = self.db.save_message(
                conversation_id=conversation_id,
                sender="assistant",
                content=contract.message,
                contract=contract,
            )
            return asst_msg, contract

        # 8. Real LLM Inference via Ollama (No fake fallback)
        try:
            history_rows = self.db.get_conversation_messages(conversation_id)
            history_tuples = [
                {"role": "user" if m.sender == "user" else "assistant", "content": m.content}
                for m in history_rows[:-1]  # Exclude current message already appended
            ]

            contract = self.llm.generate_response(
                user_message=user_text,
                retrieved_sources=retrieved_sources,
                conversation_history=history_tuples,
                current_task=latest_task,
                observer_context=obs_ctx,
                planner_context=plan_ctx,
                energy_level=effective_energy,
                cancel_event=self._cancel_event,
            )

        except Exception as e:
            # If Ollama is offline or model is missing, fail honestly with clear setup instructions
            err_msg = str(e)
            contract = SequencerResponseContract(
                message=f"I couldn't connect to your local Ollama model: {err_msg}",
                intent="ERROR",
                micro_step=None,
                estimated_effort="N/A",
                alternatives=[],
                break_option=False,
                sources=retrieved_sources[:2],
                requires_clarification=False,
                limitations="Local LLM inference requires a running Ollama service (`ollama serve`).",
            )

        # 9. Persist updated task & assistant response
        if contract.current_task:
            self.db.save_or_update_task(contract.current_task, conversation_id=conversation_id)

        asst_msg = self.db.save_message(
            conversation_id=conversation_id,
            sender="assistant",
            content=contract.message,
            contract=contract,
        )

        return asst_msg, contract

    # -------------------------------------------------------------
    # Progressive Refinement Actions
    # -------------------------------------------------------------
    def handle_action(
        self,
        conversation_id: str,
        action: str,
        task_id: Optional[str] = None,
        feedback_comment: Optional[str] = None,
    ) -> Tuple[ConversationMessage, SequencerResponseContract]:
        """
        Executes 1-click micro-task actions:
        - make_smaller
        - change_approach
        - next_step
        - complete_step
        - take_break
        - not_now
        """
        task = None
        if task_id:
            task = self.db.get_task(task_id)
        if not task:
            task = self.db.get_latest_task_for_conversation(conversation_id)

        if not task:
            task = TaskRecord(
                task_id=f"task_{int(time.time())}",
                title="Current Activity",
                status="in_progress",
            )

        contract: SequencerResponseContract

        if action in ("make_smaller", "make_easier"):
            new_step = self.decomposition.make_smaller(task)
            self.db.save_or_update_task(task, conversation_id=conversation_id)
            self.db.record_feedback(conversation_id, "too_big", step_id=new_step.step_id, user_comment=feedback_comment)
            contract = SequencerResponseContract(
                message="I made this step smaller so you can start without friction.",
                intent="REDUCE_TASK_SIZE",
                current_task=task,
                micro_step=new_step,
                estimated_effort=new_step.estimated_effort,
                alternatives=["Do 30 seconds only", "Switch to audio dictation"],
                break_option=True,
                sources=self.rag.retrieve("atomic micro-step reduction", top_k=2),
                requires_clarification=False,
                limitations="",
            )

        elif action in ("change_approach", "explain_another_way"):
            new_step = self.decomposition.change_approach(task)
            self.db.save_or_update_task(task, conversation_id=conversation_id)
            self.db.record_feedback(conversation_id, "wrong_approach", step_id=new_step.step_id, user_comment=feedback_comment)
            contract = SequencerResponseContract(
                message="Let's try a different sensory angle to bypass the cognitive bottleneck.",
                intent="CHANGE_APPROACH",
                current_task=task,
                micro_step=new_step,
                estimated_effort=new_step.estimated_effort,
                alternatives=["Draw or sketch", "Voice dictation", "Read 1 heading"],
                break_option=True,
                sources=self.rag.retrieve("decoupling sensory modality", top_k=2),
                requires_clarification=False,
                limitations="",
            )

        elif action in ("complete_step", "done"):
            completed_task = self.decomposition.complete_step(task)
            self.db.save_or_update_task(completed_task, conversation_id=conversation_id)
            self.db.record_feedback(conversation_id, "completed", step_id=task.current_micro_step.step_id if task.current_micro_step else None)
            contract = SequencerResponseContract(
                message="Nice work taking that action! Would you like to do the next step, or pause here?",
                intent="CONTINUE_TASK",
                current_task=completed_task,
                micro_step=None,
                estimated_effort="< 2 minutes",
                alternatives=["Show next step", "Take a breather", "Finish for now"],
                break_option=True,
                sources=[],
                requires_clarification=False,
                limitations="",
            )

        elif action == "next_step":
            new_step = self.decomposition.next_step(task)
            self.db.save_or_update_task(task, conversation_id=conversation_id)
            contract = SequencerResponseContract(
                message="Here is the next manageable piece of the task.",
                intent="CONTINUE_TASK",
                current_task=task,
                micro_step=new_step,
                estimated_effort=new_step.estimated_effort,
                alternatives=[],
                break_option=True,
                sources=[],
                requires_clarification=False,
                limitations="",
            )

        elif action in ("say_it_again", "repeat"):
            curr_step = task.current_micro_step
            repeat_msg = (
                f"Here is your step again: {curr_step.action_text}"
                if curr_step
                else f"Here is your current focus: {task.title}"
            )
            contract = SequencerResponseContract(
                message=repeat_msg,
                intent="REPEAT_STEP",
                current_task=task,
                micro_step=curr_step,
                estimated_effort=curr_step.estimated_effort if curr_step else "< 2 minutes",
                alternatives=[],
                break_option=True,
                sources=[],
                requires_clarification=False,
                limitations="",
            )

        elif action in ("take_break", "rest"):
            contract = self.decomposition.build_rest_transition()
            self.db.record_feedback(conversation_id, "declined", user_comment="User opted for sensory rest.")

        else:  # "not_now"
            self.db.record_feedback(conversation_id, "declined", user_comment="Dismissed without penalty.")
            contract = SequencerResponseContract(
                message="No problem at all. We will pause here—no penalties, no lost streaks. Whenever you are ready, I am here.",
                intent="PAUSE_TASK",
                current_task=task,
                micro_step=None,
                estimated_effort="N/A",
                alternatives=[],
                break_option=True,
                sources=[],
                requires_clarification=False,
                limitations="",
            )

        asst_msg = self.db.save_message(
            conversation_id=conversation_id,
            sender="assistant",
            content=contract.message,
            contract=contract,
        )

        return asst_msg, contract

    def cancel_generation(self) -> None:
        self._cancel_event.set()
        self.llm.cancel_current_generation()

    # -------------------------------------------------------------
    # Conversation Management
    # -------------------------------------------------------------
    def list_conversations(self) -> List[ConversationSummary]:
        return self.db.list_conversations()

    def get_conversation_messages(self, conversation_id: str) -> List[ConversationMessage]:
        return self.db.get_conversation_messages(conversation_id)

    def new_conversation(self, title: str = "New Task Support") -> ConversationSummary:
        return self.db.create_conversation(title=title)

    def delete_conversation(self, conversation_id: str) -> None:
        self.db.delete_conversation(conversation_id)

    def clear_all_history(self) -> None:
        self.db.clear_all()

    # -------------------------------------------------------------
    # User Preferences
    # -------------------------------------------------------------
    def get_preferences(self) -> UserPreferences:
        return self.db.get_preferences()

    def update_preferences(self, prefs: UserPreferences) -> UserPreferences:
        return self.db.update_preferences(prefs)

    # -------------------------------------------------------------
    # Observer Telemetry Integration
    # -------------------------------------------------------------
    def update_observer_telemetry(self, telemetry_data: Dict[str, Any]) -> None:
        self.observer_adapter.update_from_telemetry(telemetry_data)
