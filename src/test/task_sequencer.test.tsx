import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TaskSequencerScreen } from "@/screens/TaskSequencerScreen";
import { useObserverStore } from "@/store/useObserverStore";
import { SequencerMessageItem } from "@/types/ipc";

describe("TaskSequencerScreen Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useObserverStore.setState({
      consentGiven: true,
      activeScreen: "sequencer",
      sequencerMessages: [],
      sequencerConversations: [],
      activeConversationId: "conv_1",
      userEnergyLevel: 3,
      sequencerStatus: {
        schema_version: "1.0.0",
        type: "sequencer_status",
        llm_provider: "ollama",
        model_name: "llama3.2:latest",
        ollama_connected: true,
        model_installed: true,
        available_models: ["llama3.2:latest"],
        rag_index_ready: true,
        rag_documents_count: 9,
        rag_chunks_count: 9,
        error_message: null,
      },
      sequencerDiagnostics: {
        llm_provider: "ollama",
        model_name: "llama3.2:latest",
        ollama_endpoint: "http://localhost:11434",
        ollama_connected: true,
        model_installed: true,
        available_models: ["llama3.2:latest"],
        embedding_model: "local_tfidf_minilm",
        vector_index_ready: true,
        indexed_documents_count: 9,
        indexed_chunks_count: 9,
        last_index_build_ts: Date.now() / 1000,
        last_retrieval_query: "test",
        last_retrieval_matches_count: 2,
        last_retrieval_latency_ms: 1.2,
        last_generation_latency_ms: 450,
        observer_integration_active: true,
        observer_state_estimate: "RELAXED",
        planner_integration_active: false,
        planner_status_message: "Track 3 Adaptive Planner is currently disconnected.",
      },
    });
  });

  it("renders Task Sequencer header, microphone button, and fallback input", () => {
    render(<TaskSequencerScreen />);
    expect(screen.getByText("Task Sequencer")).toBeDefined();
    expect(screen.getByLabelText(/Activate microphone to speak/i)).toBeDefined();
    expect(screen.getByPlaceholderText(/Type your task here if you prefer not to use voice/i)).toBeDefined();
    expect(screen.getByText("Ollama: llama3.2:latest")).toBeDefined();
  });

  it("renders proposed micro-step hero card with 1-click action buttons", () => {
    const testMsg: SequencerMessageItem = {
      id: "msg_asst_1",
      conversation_id: "conv_1",
      sender: "assistant",
      content: "Let's take a single tiny step to overcome activation inertia.",
      created_at: Date.now() / 1000,
      contract: {
        message: "Let's take a single tiny step to overcome activation inertia.",
        intent: "START_TASK",
        micro_step: {
          step_id: "s1",
          action_text: "Open VS Code and write one comment line.",
          why_suggested: "Lowers neurological activation threshold.",
          estimated_effort: "< 60 seconds",
          started_immediately: true,
          completed: false,
        },
        estimated_effort: "< 60 seconds",
        alternatives: [],
        break_option: false,
        sources: [
          {
            doc_id: "INIT-001",
            title: "Activation & The 2-Minute Physical Threshold",
            url: "https://example.com/init",
            author_or_org: "ADDitude",
            category: "task_initiation",
            excerpt: "The neurological cost of task initiation is vastly higher than continuing a task.",
            relevance_score: 0.88,
          },
        ],
        requires_clarification: false,
        limitations: "",
      },
    };

    useObserverStore.setState({ sequencerMessages: [testMsg] });
    render(<TaskSequencerScreen />);

    expect(screen.getByText("Open VS Code and write one comment line.")).toBeDefined();
    expect(screen.getByText(/Lowers neurological activation threshold/i)).toBeDefined();
    expect(screen.getByText("I completed this")).toBeDefined();
    expect(screen.getByText("Make it easier")).toBeDefined();
    expect(screen.getByText("Explain another way")).toBeDefined();
    expect(screen.getByText("Say it again")).toBeDefined();
    expect(screen.getByText("Take a break")).toBeDefined();
    expect(screen.getByText("Not now")).toBeDefined();
  });

  it("speaks the micro-step aloud when 'Say it again' is clicked", () => {
    const testMsg: SequencerMessageItem = {
      id: "msg_asst_speech",
      conversation_id: "conv_1",
      sender: "assistant",
      content: "Here is your next action.",
      created_at: Date.now() / 1000,
      contract: {
        message: "Here is your next action.",
        intent: "START_TASK",
        micro_step: {
          step_id: "s_speech",
          action_text: "Drink a glass of water and sit down comfortably.",
          why_suggested: "Hydrates your brain for task activation.",
          estimated_effort: "< 60 seconds",
          started_immediately: true,
          completed: false,
        },
        estimated_effort: "< 60 seconds",
        alternatives: [],
        break_option: false,
        sources: [],
        requires_clarification: false,
        limitations: "",
      },
    };

    useObserverStore.setState({ sequencerMessages: [testMsg] });
    render(<TaskSequencerScreen />);

    const sayAgainBtn = screen.getByText("Say it again");
    fireEvent.click(sayAgainBtn);

    expect(window.speechSynthesis.speak).toHaveBeenCalled();
  });

  it("allows expanding grounded RAG citations to view source metadata", () => {
    const testMsg: SequencerMessageItem = {
      id: "msg_asst_2",
      conversation_id: "conv_1",
      sender: "assistant",
      content: "Grounded strategy response.",
      created_at: Date.now() / 1000,
      contract: {
        message: "Grounded strategy response.",
        intent: "START_TASK",
        estimated_effort: "< 2 mins",
        alternatives: [],
        break_option: false,
        sources: [
          {
            doc_id: "ACAD-001",
            title: "Overcoming the Blank Page in Academic Writing",
            url: "https://owl.purdue.edu/test",
            author_or_org: "Purdue University",
            category: "academic_workflows",
            excerpt: "Write a junk draft to break perfectionism.",
            relevance_score: 0.92,
          },
        ],
        requires_clarification: false,
        limitations: "",
      },
    };

    useObserverStore.setState({ sequencerMessages: [testMsg] });
    render(<TaskSequencerScreen />);

    const citationBtn = screen.getByText(/Grounded in 1 Coping Strategy Source/i);
    expect(citationBtn).toBeDefined();

    fireEvent.click(citationBtn);
    expect(screen.getByText(/Overcoming the Blank Page in Academic Writing/i)).toBeDefined();
    expect(screen.getByText(/"Write a junk draft to break perfectionism."/i)).toBeDefined();
    expect(screen.getByText("92% match")).toBeDefined();
  });

  it("updates capacity energy level when pill is clicked", () => {
    render(<TaskSequencerScreen />);
    const energyBtn = screen.getByText("1: Depleted");
    fireEvent.click(energyBtn);
    expect(useObserverStore.getState().userEnergyLevel).toBe(1);
  });

  it("toggles voice settings drawer", () => {
    render(<TaskSequencerScreen />);
    const voiceSettingsBtn = screen.getByLabelText(/Toggle voice settings/i);
    fireEvent.click(voiceSettingsBtn);
    expect(screen.getByText("Local Voice Settings")).toBeDefined();
    expect(screen.getByText(/Auto-read micro-steps aloud/i)).toBeDefined();
  });
});
