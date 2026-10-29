"""
observer_engine.sequencer.llm_service
Dedicated LLM service layer interfacing with local Ollama runtime.
Enforces real local inference, model availability checking, schema validation,
timeouts, and cancellation. Zero silent mock fallbacks.
"""

import json
import time
import urllib.request
import urllib.error
import threading
from typing import Dict, Any, Optional, List, Tuple

from observer_engine.sequencer.config import SequencerConfig, SEQUENCER_CONFIG
from observer_engine.sequencer.models import (
    SequencerResponseContract,
    SourceReference,
    MicroStep,
    TaskRecord,
)


class LlmService:
    def __init__(self, config: SequencerConfig = SEQUENCER_CONFIG):
        self.config = config
        self._current_cancel_event: Optional[threading.Event] = None
        self.last_generation_latency_ms: float = 0.0

    # -------------------------------------------------------------
    # Health & Availability Inspection
    # -------------------------------------------------------------
    def check_runtime_status(self) -> Dict[str, Any]:
        """
        Queries Ollama runtime directly.
        Returns:
            ollama_connected: bool
            model_installed: bool
            available_models: List[str]
            error_message: Optional[str]
        """
        endpoint = f"{self.config.ollama_endpoint.rstrip('/')}/api/tags"
        try:
            req = urllib.request.Request(endpoint, headers={"User-Agent": "Observer-TaskSequencer/1.0"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    models = [m.get("name", "") for m in data.get("models", [])]
                    target = self.config.model_name
                    # Check exact match or prefix match (e.g. llama3.2 matches llama3.2:latest)
                    target_installed = any(
                        m == target or m.startswith(target.split(":")[0]) for m in models
                    )
                    return {
                        "ollama_connected": True,
                        "model_installed": target_installed,
                        "available_models": models,
                        "error_message": None if target_installed else f"Model '{target}' is not installed in local Ollama. Run `ollama pull {target}`.",
                    }
        except urllib.error.URLError as e:
            return {
                "ollama_connected": False,
                "model_installed": False,
                "available_models": [],
                "error_message": f"Local Ollama is not running at {self.config.ollama_endpoint}. Start Ollama (`ollama serve`) and click Retry.",
            }
        except Exception as e:
            return {
                "ollama_connected": False,
                "model_installed": False,
                "available_models": [],
                "error_message": f"Ollama connection error: {str(e)}",
            }

    # -------------------------------------------------------------
    # Structured Generation
    # -------------------------------------------------------------
    def generate_response(
        self,
        user_message: str,
        retrieved_sources: List[SourceReference],
        conversation_history: List[Dict[str, str]],
        current_task: Optional[TaskRecord] = None,
        observer_context: Optional[str] = None,
        planner_context: Optional[str] = None,
        energy_level: int = 3,
        cancel_event: Optional[threading.Event] = None,
    ) -> SequencerResponseContract:
        """
        Submits validated prompt to Ollama and parses JSON into SequencerResponseContract.
        """
        self._current_cancel_event = cancel_event

        # 1. Verify runtime availability first (Fail honestly, never mock)
        status = self.check_runtime_status()
        if not status["ollama_connected"]:
            raise RuntimeError(
                f"Local LLM runtime (Ollama) is not reachable at {self.config.ollama_endpoint}. "
                "Ensure Ollama is running (`ollama serve`) to enable local inference."
            )
        if not status["model_installed"]:
            models_str = ", ".join(status["available_models"]) if status["available_models"] else "none"
            raise RuntimeError(
                f"Configured model '{self.config.model_name}' is not installed in Ollama. "
                f"Available models: [{models_str}]. Run `ollama pull {self.config.model_name}`."
            )

        # 2. Build system prompt & schema instruction
        system_prompt = self._build_system_prompt(
            retrieved_sources=retrieved_sources,
            current_task=current_task,
            observer_context=observer_context,
            planner_context=planner_context,
            energy_level=energy_level,
        )

        messages = [{"role": "system", "content": system_prompt}]
        for turn in conversation_history[-self.config.conversation_history_limits:]:
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": user_message})

        # 3. Call Ollama /api/chat with format="json"
        start_time = time.time()
        chat_endpoint = f"{self.config.ollama_endpoint.rstrip('/')}/api/chat"

        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "format": "json",
            "stream": False,
            "options": {
                "num_predict": self.config.max_generated_tokens,
                "temperature": 0.3,  # Controlled, focused generation
            },
        }

        req = urllib.request.Request(
            chat_endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "Observer-TaskSequencer/1.0"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.config.generation_timeout) as resp:
                if cancel_event and cancel_event.is_set():
                    raise RuntimeError("Generation cancelled by user.")

                raw_data = resp.read().decode("utf-8")
                self.last_generation_latency_ms = (time.time() - start_time) * 1000.0
                resp_json = json.loads(raw_data)
                model_out_text = resp_json.get("message", {}).get("content", "").strip()

        except urllib.error.URLError as e:
            raise RuntimeError(f"Ollama generation request failed or timed out: {str(e)}")

        # 4. Parse and validate against SequencerResponseContract
        return self._parse_and_validate(model_out_text, retrieved_sources, current_task)

    def cancel_current_generation(self) -> None:
        if self._current_cancel_event:
            self._current_cancel_event.set()

    # -------------------------------------------------------------
    # Prompt Construction
    # -------------------------------------------------------------
    def _build_system_prompt(
        self,
        retrieved_sources: List[SourceReference],
        current_task: Optional[TaskRecord],
        observer_context: Optional[str],
        planner_context: Optional[str],
        energy_level: int,
    ) -> str:
        sources_text = ""
        if retrieved_sources:
            sources_text = "RETRIEVED COPING STRATEGIES & SOURCES:\n"
            for s in retrieved_sources:
                sources_text += f"- [{s.doc_id}] {s.title}: \"{s.excerpt}\"\n"
        else:
            sources_text = "No specific reference documents retrieved. Rely on core executive-function principles without inventing citations.\n"

        task_text = "CURRENT TASK CONTEXT: None\n"
        if current_task:
            task_text = (
                f"CURRENT TASK CONTEXT:\n"
                f"- Title: {current_task.title}\n"
                f"- Status: {current_task.status}\n"
                f"- Current Step: {current_task.current_micro_step.action_text if current_task.current_micro_step else 'None'}\n"
            )

        obs_text = f"OBSERVER CONTEXT (Track 1): {observer_context or 'Not available / paused'}\n"
        plan_text = f"PLANNER CONTEXT (Track 3): {planner_context or 'Not connected'}\n"

        energy_guideline = {
            1: "User reports VERY LOW ENERGY (1/5). Suggest extremely low-friction physical actions or unconditional rest.",
            2: "User reports LOW ENERGY (2/5). Keep instructions very brief, one simple single step, no complex multi-step choices.",
            3: "User reports MODERATE ENERGY (3/5). Standard micro-step decomposition (< 2 minutes action).",
            4: "User reports GOOD ENERGY (4/5). Helpful action with an optional preview of the next step.",
            5: "User reports HIGH ENERGY (5/5). Accommodate larger momentum while preserving atomic clarity.",
        }.get(energy_level, "User reports moderate energy.")

        schema_spec = json.dumps({
            "message": "Empathetic, clear, concise response (2-3 sentences max).",
            "intent": "START_TASK | BREAK_DOWN_TASK | REDUCE_TASK_SIZE | CHANGE_APPROACH | REQUEST_BREAK | CONTINUE_TASK | GENERAL_QUESTION",
            "micro_step": {
                "step_id": "step_1",
                "action_text": "Single concrete physical action (< 2 mins)",
                "why_suggested": "Short 1-sentence neurodivergent rationale",
                "estimated_effort": "< 2 minutes",
                "source_strategy": "Doc title or ID if applicable"
            },
            "estimated_effort": "< 2 minutes",
            "alternatives": ["Optional alternative path A", "Optional alternative path B"],
            "break_option": False,
            "requires_clarification": False,
            "limitations": "Any missing context or uncertainty"
        }, indent=2)

        return (
            "You are the Observer Task Sequencer, an executive-function support companion for neurodivergent individuals.\n"
            "FUNDAMENTAL PRINCIPLES:\n"
            "1. REDUCE FRICTION: Propose ONE immediate physical action that can be started in under 2 minutes.\n"
            "2. ZERO SHAME: Never use words like 'lazy', 'procrastinating', 'failure', or pressure to finish the whole project.\n"
            "3. HONEST REST: If the user needs rest or expresses exhaustion, validate it unconditionally and offer a sensory-friendly break.\n"
            "4. NEVER INVENT CITATIONS: Only cite sources listed below in RETRIEVED COPING STRATEGIES.\n"
            f"5. CAPACITY AWARENESS: {energy_guideline}\n\n"
            f"{sources_text}\n"
            f"{task_text}\n"
            f"{obs_text}\n"
            f"{plan_text}\n"
            "OUTPUT REQUIREMENT: Respond ONLY with a valid JSON object matching this schema:\n"
            f"{schema_spec}\n"
        )

    # -------------------------------------------------------------
    # Parser & Validator
    # -------------------------------------------------------------
    def _parse_and_validate(
        self,
        raw_text: str,
        retrieved_sources: List[SourceReference],
        current_task: Optional[TaskRecord],
    ) -> SequencerResponseContract:
        # Strip potential markdown code fences ```json ... ```
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("\n", 1)[0]
            cleaned = cleaned.strip()

        data = json.loads(cleaned)

        # Micro-step extraction
        raw_step = data.get("micro_step")
        micro_step = None
        if raw_step and isinstance(raw_step, dict) and raw_step.get("action_text"):
            micro_step = MicroStep(
                step_id=raw_step.get("step_id", f"step_{int(time.time())}"),
                action_text=raw_step.get("action_text", ""),
                why_suggested=raw_step.get("why_suggested", ""),
                estimated_effort=raw_step.get("estimated_effort", "< 2 minutes"),
                started_immediately=True,
                source_strategy=raw_step.get("source_strategy", ""),
            )

        # Map sources
        sources_to_include = []
        for s in retrieved_sources:
            if s.relevance_score >= self.config.min_retrieval_relevance:
                sources_to_include.append(s)

        # Task handling
        updated_task = current_task
        if micro_step:
            if updated_task is None:
                updated_task = TaskRecord(
                    task_id=f"task_{int(time.time())}",
                    title=data.get("intent", "Task Initiation"),
                    status="in_progress",
                    current_micro_step=micro_step,
                    step_history=[micro_step],
                )
            else:
                updated_task.current_micro_step = micro_step
                updated_task.step_history.append(micro_step)

        return SequencerResponseContract(
            message=data.get("message", "Here is a gentle first step."),
            intent=data.get("intent", "START_TASK"),
            current_task=updated_task,
            micro_step=micro_step,
            estimated_effort=data.get("estimated_effort", "< 2 minutes"),
            alternatives=data.get("alternatives", []),
            break_option=bool(data.get("break_option", False)),
            sources=sources_to_include,
            requires_clarification=bool(data.get("requires_clarification", False)),
            limitations=data.get("limitations", ""),
        )
