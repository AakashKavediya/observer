import React from "react";
import { X, RefreshCw, Cpu, Database, CheckCircle2, AlertTriangle } from "lucide-react";
import { useObserverStore } from "@/store/useObserverStore";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export const SequencerDiagnosticsModal: React.FC<Props> = ({ isOpen, onClose }) => {
  const {
    sequencerDiagnostics,
    sequencerStatus,
    fetchSequencerDiagnostics,
    rebuildRagIndex,
  } = useObserverStore();

  if (!isOpen) return null;

  const diag = sequencerDiagnostics;
  const status = sequencerStatus;

  return (
    <div
      role="dialog"
      aria-labelledby="diag-title"
      className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4"
    >
      <div className="bg-panel border border-sage/40 rounded-card shadow-floating w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="bg-ivory border-b border-black/10 px-5 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-sage text-white flex items-center justify-center">
              <Cpu className="w-4 h-4" aria-hidden="true" />
            </div>
            <div>
              <h3 id="diag-title" className="text-sm font-bold text-ink">
                LLM & RAG Retrieval Diagnostics
              </h3>
              <p className="text-[11px] text-ink-muted">
                Transparent local model runtime and vector knowledge index status
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-ink-muted hover:text-ink rounded-md hover:bg-black/5"
            aria-label="Close diagnostics"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 overflow-y-auto space-y-4 text-xs">
          {/* Runtime & Model Status */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Card className="p-3.5 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="font-bold text-ink-muted uppercase text-[10px]">Ollama Local Runtime</span>
                {status?.ollama_connected ? (
                  <span className="inline-flex items-center gap-1 text-[11px] font-bold text-sage">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Reachable
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-[11px] font-bold text-clay">
                    <AlertTriangle className="w-3.5 h-3.5" /> Disconnected
                  </span>
                )}
              </div>
              <p className="font-mono text-ink text-xs">{diag?.ollama_endpoint || "http://localhost:11434"}</p>
              <div className="pt-1 text-[11px] text-ink-muted">
                Available models in Ollama: <strong>{status?.available_models.join(", ") || "None found"}</strong>
              </div>
            </Card>

            <Card className="p-3.5 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="font-bold text-ink-muted uppercase text-[10px]">Configured Model</span>
                {status?.model_installed ? (
                  <span className="inline-flex items-center gap-1 text-[11px] font-bold text-sage">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Installed
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-[11px] font-bold text-clay">
                    <AlertTriangle className="w-3.5 h-3.5" /> Missing
                  </span>
                )}
              </div>
              <p className="font-mono text-ink text-xs font-bold">{diag?.model_name || "llama3.2:latest"}</p>
              <div className="pt-1 text-[11px] text-ink-muted">
                Last generation latency: <strong>{diag?.last_generation_latency_ms ? `${diag.last_generation_latency_ms.toFixed(0)} ms` : "0 ms"}</strong>
              </div>
            </Card>
          </div>

          {/* RAG Knowledge Base Status */}
          <Card className="p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="font-bold text-ink flex items-center gap-1.5">
                <Database className="w-4 h-4 text-sage" />
                Curated Executive Function Knowledge Base
              </h4>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => rebuildRagIndex()}
                className="text-xs h-7 gap-1 text-sage border border-sage/20 hover:bg-sage/10"
              >
                <RefreshCw className="w-3 h-3" /> Rebuild Index
              </Button>
            </div>

            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="p-2 rounded bg-ivory">
                <span className="text-[10px] text-ink-muted block uppercase font-bold">Source Documents</span>
                <span className="text-base font-bold text-ink font-mono">{diag?.indexed_documents_count ?? status?.rag_documents_count ?? 9}</span>
              </div>
              <div className="p-2 rounded bg-ivory">
                <span className="text-[10px] text-ink-muted block uppercase font-bold">Vector Chunks</span>
                <span className="text-base font-bold text-ink font-mono">{diag?.indexed_chunks_count ?? status?.rag_chunks_count ?? 9}</span>
              </div>
              <div className="p-2 rounded bg-ivory">
                <span className="text-[10px] text-ink-muted block uppercase font-bold">Embedding Model</span>
                <span className="text-xs font-bold text-sage font-mono block mt-1">Local Minilm/Subword</span>
              </div>
            </div>

            {diag?.last_retrieval_query && (
              <div className="p-2.5 rounded bg-ivory border border-black/5 text-[11px] space-y-1">
                <div className="flex justify-between text-ink-muted">
                  <span>Last Retrieval Query:</span>
                  <span>{diag.last_retrieval_latency_ms ? `${diag.last_retrieval_latency_ms.toFixed(1)} ms` : "< 1 ms"}</span>
                </div>
                <p className="font-mono text-ink italic">"{diag.last_retrieval_query}"</p>
                <p className="text-ink-muted text-[10px]">
                  Matches above threshold: <strong>{diag.last_retrieval_matches_count} chunks</strong>
                </p>
              </div>
            )}
          </Card>

          {/* Subsystem Integrations */}
          <div className="grid grid-cols-2 gap-3">
            <Card className="p-3 space-y-1">
              <span className="text-[10px] font-bold text-ink-muted uppercase">Track 1 Observer Integration</span>
              <p className="text-xs font-semibold text-ink">
                Status: <span className={diag?.observer_integration_active ? "text-sage font-bold" : "text-ink-muted"}>
                  {diag?.observer_integration_active ? "Connected & Active" : "Paused / Consented Off"}
                </span>
              </p>
              <p className="text-[10px] text-ink-muted">
                Current estimate: <strong>{diag?.observer_state_estimate || "UNKNOWN"}</strong>
              </p>
            </Card>

            <Card className="p-3 space-y-1">
              <span className="text-[10px] font-bold text-ink-muted uppercase">Track 3 Planner Integration</span>
              <p className="text-xs font-semibold text-ink">
                Status: <span className="text-clay font-bold">Unavailable</span>
              </p>
              <p className="text-[10px] text-ink-muted leading-relaxed">
                {diag?.planner_status_message || "Track 3 Adaptive Planner is currently disconnected. Working with local sequencer tasks."}
              </p>
            </Card>
          </div>
        </div>

        {/* Footer */}
        <div className="bg-ivory border-t border-black/10 px-5 py-3 flex justify-between items-center">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => fetchSequencerDiagnostics()}
            className="text-xs gap-1.5"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Refresh Diagnostics
          </Button>
          <Button variant="secondary" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
};
