import React, { useState, useEffect, useRef } from "react";
import {
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Send,
  Sparkles,
  RefreshCw,
  BookOpen,
  CheckCircle2,
  Coffee,
  Minimize2,
  AlertTriangle,
  Plus,
  Trash2,
  ChevronDown,
  ChevronUp,
  Sliders,
  Settings,
  X,
  ExternalLink,
  Edit3,
} from "lucide-react";
import { useObserverStore } from "@/store/useObserverStore";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { SequencerDiagnosticsModal } from "./SequencerDiagnosticsModal";
import {
  useVoiceInput,
  speechSynth,
  cleanTextForSpeech,
} from "@/services/voiceService";

export const TaskSequencerScreen: React.FC = () => {
  const {
    sequencerMessages,
    sequencerStatus,
    sequencerLoading,
    activeConversationId,
    sequencerConversations,
    userEnergyLevel,
    sendSequencerMessage,
    sendSequencerAction,
    fetchSequencerConversations,
    loadSequencerConversation,
    createSequencerConversation,
    deleteSequencerConversation,
    clearSequencerHistory,
    setUserEnergyLevel,
    fetchSequencerDiagnostics,
    cancelSequencerGeneration,
  } = useObserverStore();

  const [inputText, setInputText] = useState("");
  const [showDiagnostics, setShowDiagnostics] = useState(false);
  const [showHistoryDrawer, setShowHistoryDrawer] = useState(false);
  const [showVoiceSettings, setShowVoiceSettings] = useState(false);
  const [expandedSources, setExpandedSources] = useState<Record<string, boolean>>({});
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Voice input hook
  const {
    status: voiceStatus,
    transcript,
    setTranscript,
    interimTranscript,
    errorMessage: voiceError,
    isSpeaking,
    settings: voiceSettings,
    updateSettings: updateVoiceSettings,
    startListening,
    stopListening,
    cancelListening,
    speakAction,
    stopSpeaking,
  } = useVoiceInput();

  // Load voices when available
  useEffect(() => {
    fetchSequencerConversations();
    fetchSequencerDiagnostics();

    const updateVoices = () => {
      setVoices(speechSynth.getAvailableVoices());
    };
    updateVoices();
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.onvoiceschanged = updateVoices;
    }
  }, []);

  // Auto-scroll on new messages
  useEffect(() => {
    if (typeof messagesEndRef.current?.scrollIntoView === "function") {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [sequencerMessages, sequencerLoading]);

  // Find latest assistant micro-step
  const latestAssistantMsg = [...sequencerMessages]
    .reverse()
    .find((m) => m.sender === "assistant" && m.contract?.micro_step);
  const activeMicroStep = latestAssistantMsg?.contract?.micro_step;

  // Auto-speak new micro-actions when they arrive
  const lastSpokenStepIdRef = useRef<string | null>(null);
  useEffect(() => {
    if (
      voiceSettings.autoSpeak &&
      activeMicroStep &&
      activeMicroStep.step_id !== lastSpokenStepIdRef.current
    ) {
      lastSpokenStepIdRef.current = activeMicroStep.step_id;
      speakAction(activeMicroStep.action_text, activeMicroStep.why_suggested);
    }
  }, [activeMicroStep, voiceSettings.autoSpeak, speakAction]);

  const handleSendText = async (textToSend: string) => {
    const trimmed = textToSend.trim();
    if (!trimmed || sequencerLoading) return;
    setInputText("");
    setTranscript("");
    if (isSpeaking) {
      stopSpeaking();
    }
    await sendSequencerMessage(trimmed, userEnergyLevel);
  };

  const handleMicToggle = () => {
    if (voiceStatus === "listening") {
      stopListening();
    } else {
      startListening();
    }
  };

  const handleSayItAgain = () => {
    if (activeMicroStep) {
      speakAction(activeMicroStep.action_text, activeMicroStep.why_suggested);
    } else if (latestAssistantMsg?.content) {
      speechSynth.speak(cleanTextForSpeech(latestAssistantMsg.content), {
        rate: voiceSettings.rate,
        pitch: voiceSettings.pitch,
        voiceName: voiceSettings.voiceName,
      });
    }
  };

  const toggleSourceExpand = (msgId: string) => {
    setExpandedSources((prev) => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  const energyLabels = [
    { level: 1, label: "1: Depleted", desc: "Sensory rest & micro actions" },
    { level: 2, label: "2: Low", desc: "Minimal effort single step" },
    { level: 3, label: "3: Steady", desc: "Standard 2-min micro-step" },
    { level: 4, label: "4: Good", desc: "Active focus & progress" },
    { level: 5, label: "5: High", desc: "Deep flow momentum" },
  ];

  return (
    <div className="max-w-4xl mx-auto py-4 px-4 space-y-4 flex flex-col h-[calc(100vh-110px)] overflow-hidden">
      {/* Top Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-panel p-3.5 rounded-2xl border border-black/5 shadow-xs">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-ink flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-sage" aria-hidden="true" />
              Task Sequencer
            </h2>
            <Badge variant="default" className="text-[10px]">
              Track 2 • Voice-First
            </Badge>
          </div>
          <p className="text-xs text-ink-muted">
            Gentle executive-function assistant. Speaks one atomic action without overwhelm.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Runtime Status Pill */}
          <button
            onClick={() => setShowDiagnostics(true)}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border transition-colors ${
              sequencerStatus?.ollama_connected && sequencerStatus?.model_installed
                ? "bg-sage/10 text-sage border-sage/30 hover:bg-sage/20"
                : "bg-clay/10 text-clay border-clay/30 hover:bg-clay/20"
            }`}
            title="Inspect local model and vector index status"
          >
            {sequencerStatus?.ollama_connected && sequencerStatus?.model_installed ? (
              <>
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Ollama: {sequencerStatus.model_name}</span>
              </>
            ) : (
              <>
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>Ollama Offline / Setup</span>
              </>
            )}
          </button>

          {/* Voice Settings Toggle */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowVoiceSettings(!showVoiceSettings)}
            className="text-xs h-8 gap-1.5 border border-black/10 text-ink"
            aria-label="Toggle voice settings"
          >
            <Settings className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Voice</span>
          </Button>

          {/* Conversations Drawer Toggle */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowHistoryDrawer(!showHistoryDrawer)}
            className="text-xs h-8 gap-1.5 border border-black/10 text-ink"
            aria-label="Toggle conversation history"
          >
            <span>History ({sequencerConversations.length})</span>
            {showHistoryDrawer ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </Button>

          {/* New Task */}
          <Button
            variant="secondary"
            size="sm"
            onClick={() => createSequencerConversation()}
            className="text-xs h-8 gap-1"
          >
            <Plus className="w-3.5 h-3.5" /> New Task
          </Button>
        </div>
      </div>

      {/* Voice Settings Drawer (if expanded) */}
      {showVoiceSettings && (
        <Card className="p-3.5 bg-ivory border-black/10 space-y-3">
          <div className="flex items-center justify-between border-b border-black/5 pb-2">
            <span className="text-xs font-bold text-ink flex items-center gap-1.5">
              <Volume2 className="w-4 h-4 text-sage" /> Local Voice Settings
            </span>
            <button
              onClick={() => setShowVoiceSettings(false)}
              className="text-ink-muted hover:text-ink"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            {/* Speed / Rate */}
            <div className="space-y-1">
              <label className="font-semibold text-ink-muted flex justify-between">
                <span>Reading Speed:</span>
                <span className="font-mono text-sage">{voiceSettings.rate}x</span>
              </label>
              <input
                type="range"
                min="0.8"
                max="1.3"
                step="0.05"
                value={voiceSettings.rate}
                onChange={(e) => updateVoiceSettings({ rate: parseFloat(e.target.value) })}
                className="w-full accent-sage"
              />
            </div>

            {/* Voice Selection */}
            <div className="space-y-1">
              <label className="font-semibold text-ink-muted">Local System Voice:</label>
              <select
                value={voiceSettings.voiceName}
                onChange={(e) => updateVoiceSettings({ voiceName: e.target.value })}
                className="w-full bg-panel border border-black/10 rounded-lg px-2 py-1 text-xs text-ink"
              >
                <option value="">Default OS Voice</option>
                {voices.map((v) => (
                  <option key={v.name} value={v.name}>
                    {v.name} ({v.lang})
                  </option>
                ))}
              </select>
            </div>

            {/* Auto-read toggle */}
            <div className="space-y-1 flex flex-col justify-end">
              <label className="inline-flex items-center gap-2 cursor-pointer font-medium text-ink">
                <input
                  type="checkbox"
                  checked={voiceSettings.autoSpeak}
                  onChange={(e) => updateVoiceSettings({ autoSpeak: e.target.checked })}
                  className="rounded border-black/20 text-sage focus:ring-sage"
                />
                <span>Auto-read micro-steps aloud</span>
              </label>
            </div>
          </div>
        </Card>
      )}

      {/* History Drawer (if expanded) */}
      {showHistoryDrawer && (
        <Card className="p-3 bg-ivory border-black/10 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-ink-muted uppercase">Past Conversations</span>
            <button
              onClick={() => clearSequencerHistory()}
              className="text-[11px] text-clay hover:underline flex items-center gap-1"
            >
              <Trash2 className="w-3 h-3" /> Clear All History
            </button>
          </div>
          <div className="flex gap-2 overflow-x-auto pb-1">
            {sequencerConversations.map((c) => (
              <div
                key={c.id}
                onClick={() => loadSequencerConversation(c.id)}
                className={`flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer border transition-colors flex items-center gap-2 ${
                  c.id === activeConversationId
                    ? "bg-sage text-white border-sage"
                    : "bg-panel text-ink border-black/10 hover:bg-black/5"
                }`}
              >
                <span className="truncate max-w-[140px]">{c.title}</span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteSequencerConversation(c.id);
                  }}
                  className="hover:text-clay"
                  aria-label="Delete conversation"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            ))}
            {sequencerConversations.length === 0 && (
              <p className="text-xs text-ink-muted italic">No past conversations saved.</p>
            )}
          </div>
        </Card>
      )}

      {/* Capacity Energy Level Selector Bar */}
      <div className="bg-panel px-4 py-2.5 rounded-xl border border-black/5 flex flex-wrap items-center justify-between gap-2 text-xs">
        <span className="font-bold text-ink-muted flex items-center gap-1.5">
          <Sliders className="w-3.5 h-3.5 text-sage" />
          <span>Current Capacity:</span>
        </span>
        <div className="flex items-center gap-1.5">
          {energyLabels.map((item) => (
            <button
              key={item.level}
              onClick={() => setUserEnergyLevel(item.level)}
              title={item.desc}
              className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-all ${
                userEnergyLevel === item.level
                  ? "bg-sage text-white shadow-xs"
                  : "bg-ivory text-ink-muted hover:text-ink hover:bg-black/5"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* Ollama Disconnected Setup Banner */}
      {sequencerStatus && !sequencerStatus.ollama_connected && (
        <div className="p-3.5 rounded-xl bg-clay/10 border border-clay/30 flex items-start justify-between gap-3 text-xs text-ink">
          <div className="flex items-start gap-2.5">
            <AlertTriangle className="w-4 h-4 text-clay flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-bold text-clay">Local Ollama runtime is not running</p>
              <p className="text-ink-muted mt-0.5">
                Run <code className="font-mono bg-black/5 px-1.5 py-0.5 rounded text-ink">ollama serve</code> in your terminal and pull a model with{" "}
                <code className="font-mono bg-black/5 px-1.5 py-0.5 rounded text-ink">ollama pull llama3.2</code> to enable private offline inference.
              </p>
            </div>
          </div>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => fetchSequencerDiagnostics()}
            className="text-xs border border-clay/30 text-clay hover:bg-clay/10 flex-shrink-0"
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1" /> Retry
          </Button>
        </div>
      )}

      {/* Main Interactive Surface */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-1">
        {/* Prominent Voice Controller Panel */}
        <div className="bg-panel rounded-2xl p-6 border border-black/5 shadow-xs flex flex-col items-center justify-center text-center space-y-3">
          {/* Circular Microphone Control */}
          <div className="relative">
            <button
              onClick={handleMicToggle}
              aria-label={voiceStatus === "listening" ? "Stop recording speech" : "Activate microphone to speak"}
              className={`w-18 h-18 rounded-full flex items-center justify-center transition-all duration-300 shadow-md ${
                voiceStatus === "listening"
                  ? "bg-clay text-white ring-8 ring-clay/20 animate-pulse scale-105"
                  : isSpeaking
                  ? "bg-sage text-white ring-8 ring-sage/20 scale-100"
                  : "bg-sage/15 text-sage hover:bg-sage hover:text-white"
              }`}
            >
              {voiceStatus === "listening" ? (
                <MicOff className="w-8 h-8" />
              ) : (
                <Mic className="w-8 h-8" />
              )}
            </button>
          </div>

          {/* Status Indicator Pill */}
          <div className="flex items-center gap-2">
            <div
              className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold ${
                voiceStatus === "listening"
                  ? "bg-clay/15 text-clay animate-pulse"
                  : isSpeaking
                  ? "bg-sage/15 text-sage"
                  : sequencerLoading
                  ? "bg-sage/15 text-sage"
                  : "bg-black/5 text-ink-muted"
              }`}
            >
              {voiceStatus === "listening" && (
                <>
                  <span className="w-2 h-2 rounded-full bg-clay animate-ping" />
                  <span>Listening... tap microphone when finished</span>
                </>
              )}
              {voiceStatus === "transcribing" && (
                <>
                  <RefreshCw className="w-3 h-3 animate-spin text-sage" />
                  <span>Transcribing speech...</span>
                </>
              )}
              {sequencerLoading && (
                <>
                  <RefreshCw className="w-3 h-3 animate-spin text-sage" />
                  <span>Formulating gentle micro-step...</span>
                </>
              )}
              {isSpeaking && (
                <>
                  <Volume2 className="w-3 h-3 text-sage animate-bounce" />
                  <span>Speaking micro-action aloud...</span>
                </>
              )}
              {voiceStatus === "idle" && !isSpeaking && !sequencerLoading && (
                <span>Tap microphone to speak, or use text below</span>
              )}
              {voiceStatus === "unsupported" && (
                <span>Local speech recognition unavailable in webview (use text below)</span>
              )}
              {voiceStatus === "permission_denied" && (
                <span>Microphone access needed (check system settings, or type below)</span>
              )}
              {voiceStatus === "error" && (
                <span>{voiceError || "Voice input error (use text below)"}</span>
              )}
            </div>

            {/* Stop Speaking Control */}
            {isSpeaking && (
              <Button
                size="sm"
                variant="ghost"
                onClick={stopSpeaking}
                className="h-6 text-xs text-clay border border-clay/30 hover:bg-clay/10 gap-1 px-2"
              >
                <VolumeX className="w-3 h-3" /> Stop speaking
              </Button>
            )}
          </div>

          {/* Interim speech preview */}
          {interimTranscript && (
            <p className="text-xs text-ink italic font-medium max-w-lg bg-ivory px-3 py-1.5 rounded-lg border border-black/5">
              "{interimTranscript}..."
            </p>
          )}

          {/* Transcript Review & Edit Card */}
          {transcript && voiceStatus !== "listening" && (
            <div className="w-full max-w-lg bg-ivory p-3 rounded-xl border border-sage/30 space-y-2 text-left">
              <div className="flex items-center justify-between text-[11px] font-bold text-ink-muted">
                <span className="flex items-center gap-1 text-sage">
                  <Edit3 className="w-3 h-3" /> Speech Transcript (review or edit):
                </span>
                <button
                  onClick={cancelListening}
                  className="text-clay hover:underline flex items-center gap-0.5"
                >
                  <X className="w-3 h-3" /> Discard
                </button>
              </div>
              <textarea
                value={transcript}
                onChange={(e) => setTranscript(e.target.value)}
                rows={2}
                className="w-full bg-white border border-black/10 rounded-lg p-2 text-xs text-ink focus:outline-hidden focus:border-sage"
              />
              <div className="flex justify-end gap-2">
                <Button
                  size="sm"
                  variant="primary"
                  onClick={() => handleSendText(transcript)}
                  disabled={sequencerLoading}
                  className="text-xs h-7 gap-1"
                >
                  <Send className="w-3 h-3" /> Send to Sequencer
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* Hero Micro-Action Card (Latest Proposed Next Step) */}
        {activeMicroStep && (
          <Card className="p-5 bg-panel border-2 border-sage/40 shadow-sm space-y-4">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <Badge variant="default" className="text-[10px] bg-sage text-white uppercase tracking-wider font-bold">
                  Proposed Next Action
                </Badge>
                <span className="font-mono text-xs bg-sage/10 text-sage px-2 py-0.5 rounded font-semibold">
                  {activeMicroStep.estimated_effort}
                </span>
              </div>

              {/* Say It Again Button */}
              <Button
                size="sm"
                variant="ghost"
                onClick={handleSayItAgain}
                className="text-xs h-7 gap-1 text-sage border border-sage/30 hover:bg-sage/10"
                aria-label="Say action instruction aloud again"
              >
                <Volume2 className="w-3.5 h-3.5" /> Say it again
              </Button>
            </div>

            {/* Action Text starting with concrete action verb */}
            <div className="space-y-1.5">
              <h3 className="text-lg font-extrabold text-ink leading-snug">
                {activeMicroStep.action_text}
              </h3>
              {activeMicroStep.why_suggested && (
                <p className="text-xs text-ink-muted leading-relaxed">
                  {activeMicroStep.why_suggested}
                </p>
              )}
            </div>

            {/* Large, Touch-Friendly Accessible Action Controls */}
            <div className="pt-3 border-t border-black/5 flex flex-wrap gap-2.5">
              {/* Done */}
              <Button
                size="md"
                variant="primary"
                onClick={() => sendSequencerAction("done")}
                disabled={sequencerLoading}
                className="text-xs h-9 px-4 gap-1.5 shadow-xs"
              >
                <CheckCircle2 className="w-4 h-4" /> I completed this
              </Button>

              {/* Make it easier */}
              <Button
                size="md"
                variant="secondary"
                onClick={() => sendSequencerAction("make_easier")}
                disabled={sequencerLoading}
                className="text-xs h-9 px-3.5 gap-1.5"
              >
                <Minimize2 className="w-4 h-4" /> Make it easier
              </Button>

              {/* Explain another way */}
              <Button
                size="md"
                variant="secondary"
                onClick={() => sendSequencerAction("explain_another_way")}
                disabled={sequencerLoading}
                className="text-xs h-9 px-3.5 gap-1.5"
              >
                <RefreshCw className="w-4 h-4" /> Explain another way
              </Button>

              {/* Take a break */}
              <Button
                size="md"
                variant="ghost"
                onClick={() => sendSequencerAction("take_break")}
                disabled={sequencerLoading}
                className="text-xs h-9 px-3.5 gap-1.5 text-ink-muted hover:text-clay border border-black/10 hover:border-clay/30"
              >
                <Coffee className="w-4 h-4" /> Take a break
              </Button>

              {/* Not now */}
              <Button
                size="md"
                variant="ghost"
                onClick={() => sendSequencerAction("not_now")}
                disabled={sequencerLoading}
                className="text-xs h-9 px-3 text-ink-muted"
              >
                Not now
              </Button>
            </div>
          </Card>
        )}

        {/* Empty State Prompt Suggestions */}
        {sequencerMessages.length === 0 && !activeMicroStep && (
          <div className="text-center py-6 px-4 space-y-3 max-w-md mx-auto">
            <h3 className="text-base font-extrabold text-ink">What is on your mind right now?</h3>
            <p className="text-xs text-ink-muted leading-relaxed">
              Tell me about an assignment or task you feel stuck on. You can speak into your microphone or pick a prompt below:
            </p>
            <div className="flex flex-wrap gap-2 justify-center pt-2">
              {[
                "I can't start writing my paper",
                "I have a big programming bug to fix",
                "My reading list is too long",
                "I feel exhausted and need to rest",
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => handleSendText(suggestion)}
                  className="px-3 py-1.5 rounded-full text-xs font-medium bg-panel border border-black/10 hover:border-sage/40 text-ink hover:text-sage transition-colors text-left"
                >
                  "{suggestion}"
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Conversation Message Stream */}
        {sequencerMessages.length > 0 && (
          <div className="space-y-3 pt-2">
            <div className="text-[11px] font-bold uppercase text-ink-muted tracking-wider">
              Recent Conversation
            </div>
            {sequencerMessages.map((msg) => {
              const isUser = msg.sender === "user";
              const contract = msg.contract;

              return (
                <div
                  key={msg.id}
                  className={`flex flex-col ${isUser ? "items-end" : "items-start"} space-y-1`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl p-3.5 text-xs leading-relaxed ${
                      isUser
                        ? "bg-sage text-white font-medium rounded-tr-xs"
                        : "bg-panel border border-black/5 text-ink shadow-xs rounded-tl-xs space-y-2.5"
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{msg.content}</p>

                    {/* Grounded RAG Citations */}
                    {!isUser && contract?.sources && contract.sources.length > 0 && (
                      <div className="pt-2 border-t border-black/5 space-y-1.5 text-[11px]">
                        <button
                          onClick={() => toggleSourceExpand(msg.id)}
                          className="flex items-center gap-1.5 font-bold text-sage hover:underline"
                        >
                          <BookOpen className="w-3.5 h-3.5" />
                          <span>
                            Grounded in {contract.sources.length} Coping Strategy{" "}
                            {contract.sources.length === 1 ? "Source" : "Sources"}
                          </span>
                          {expandedSources[msg.id] ? (
                            <ChevronUp className="w-3 h-3" />
                          ) : (
                            <ChevronDown className="w-3 h-3" />
                          )}
                        </button>

                        {expandedSources[msg.id] && (
                          <div className="space-y-2 mt-2 bg-ivory/60 p-3 rounded-lg border border-black/5">
                            {contract.sources.map((s) => (
                              <div key={s.doc_id} className="space-y-1">
                                <div className="flex items-center justify-between">
                                  <span className="font-bold text-ink">
                                    [{s.doc_id}] {s.title}
                                  </span>
                                  <span className="font-mono text-[10px] text-sage font-bold">
                                    {Math.round(s.relevance_score * 100)}% match
                                  </span>
                                </div>
                                <p className="text-ink-muted italic">"{s.excerpt}"</p>
                                {s.url && (
                                  <a
                                    href={s.url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="inline-flex items-center gap-1 text-[10px] text-sage hover:underline"
                                  >
                                    Source Provenance <ExternalLink className="w-2.5 h-2.5" />
                                  </a>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Loading Indicator */}
        {sequencerLoading && (
          <div className="flex flex-col items-start space-y-1">
            <div className="bg-panel border border-black/5 rounded-2xl p-3 text-xs text-ink-muted flex items-center gap-2.5 shadow-xs">
              <RefreshCw className="w-4 h-4 animate-spin text-sage" />
              <span>Formulating an atomic micro-step with executive coping strategies...</span>
              <button
                onClick={() => cancelSequencerGeneration()}
                className="text-[11px] font-bold text-clay hover:underline ml-2"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Fallback Text Input Form */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSendText(inputText);
        }}
        className="bg-panel p-2.5 rounded-2xl border border-black/5 shadow-xs space-y-2 flex-shrink-0"
      >
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Type your task here if you prefer not to use voice..."
            disabled={sequencerLoading}
            className="flex-1 bg-ivory border border-black/10 rounded-xl px-4 py-2.5 text-xs text-ink placeholder:text-ink-muted focus:outline-hidden focus:border-sage focus:ring-1 focus:ring-sage"
          />
          <Button
            type="submit"
            variant="primary"
            size="md"
            disabled={!inputText.trim() || sequencerLoading}
            className="h-10 px-4"
          >
            <Send className="w-4 h-4 mr-1.5" /> Send
          </Button>
        </div>
      </form>

      {/* Diagnostics Modal */}
      <SequencerDiagnosticsModal
        isOpen={showDiagnostics}
        onClose={() => setShowDiagnostics(false)}
      />
    </div>
  );
};
