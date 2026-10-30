import React, { useState, useEffect } from "react";
import {
  FileText,
  Filter,
  X,
  Trash2,
  Download,
  Clock,
  Printer,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { useObserverStore } from "@/store/useObserverStore";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";

export const ObservationsReportsScreen: React.FC = () => {
  const {
    historyRecords,
    htEvents,
    htObservations,
    htReport,
    generatedReport,
    fetchHistory,
    fetchHtEvents,
    fetchHtObservations,
    sendReviewObservation,
    sendClearHistory,
    sendGenerateReport,
    generateHtReport,
    purgeAllHtData,
  } = useObserverStore();

  const [activeTab, setActiveTab] = useState<"episodes" | "events" | "stream">("episodes");
  const [stateFilter, setStateFilter] = useState<string>("ALL");
  const [selectedRecordId, setSelectedRecordId] = useState<string | null>(null);
  const [showReportModal, setShowReportModal] = useState<boolean>(false);

  useEffect(() => {
    fetchHistory(stateFilter === "ALL" ? undefined : stateFilter);
    fetchHtEvents();
    fetchHtObservations(100);
  }, [stateFilter, fetchHistory, fetchHtEvents, fetchHtObservations]);

  const filteredHistory = historyRecords.filter((rec) => {
    if (stateFilter === "ALL") return true;
    return rec.state === stateFilter;
  });

  const activeReport = (htReport || generatedReport) as any;

  const handleExportCSV = () => {
    if (!activeReport?.csv_export) return;
    const blob = new Blob([activeReport.csv_export as string], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `observer_report_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handlePrintReport = () => {
    if (!activeReport?.html_printable_export) return;
    const printWindow = window.open("", "_blank");
    if (printWindow) {
      printWindow.document.write(activeReport.html_printable_export as string);
      printWindow.document.close();
      printWindow.focus();
      setTimeout(() => printWindow.print(), 250);
    }
  };

  const getStateBadgeVariant = (state: string) => {
    switch (state) {
      case "PARALYSIS_LIKELY":
      case "OVERLOAD_LIKELY":
        return "accent";
      case "FOCUSED":
        return "highlight";
      default:
        return "default";
    }
  };

  return (
    <div className="max-w-5xl mx-auto py-6 px-4 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-2xl font-extrabold tracking-tight text-ink flex items-center gap-2">
              <FileText className="w-5 h-5 text-sage" /> Observations &amp; Reports
            </h2>
            <Badge variant="default" className="text-[10px] bg-sage text-white">
              Data Provenance Verified
            </Badge>
          </div>
          <p className="text-xs text-ink-muted mt-0.5">
            Review past cognitive state episodes, inspect contributing biometric signals, and generate evidence reports.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={async () => {
              await sendGenerateReport();
              await generateHtReport();
              setShowReportModal(true);
            }}
            className="text-xs h-9 px-3.5 gap-1.5 font-bold"
          >
            <FileText className="w-4 h-4 text-sage" />
            <span>Generate Report</span>
          </Button>

          {historyRecords.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="text-clay hover:bg-clay/10 text-xs h-9 px-3 border border-black/10"
              onClick={sendClearHistory}
              aria-label="Delete all observations"
              title="Clear all past observation episodes"
            >
              <Trash2 className="w-3.5 h-3.5 mr-1" />
              <span>Clear History</span>
            </Button>
          )}

          <Button
            variant="ghost"
            size="sm"
            className="text-clay hover:bg-clay/10 text-xs h-9 px-3 border border-black/10"
            onClick={purgeAllHtData}
            aria-label="Purge all data"
            title="Permanently wipe all session observations and events"
          >
            <span>Purge Data</span>
          </Button>
        </div>
      </div>

      {/* Tabs & Filter Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-panel border border-black/5 rounded-2xl shadow-xs">
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg bg-ivory p-0.5 border border-black/10 text-xs">
            <button
              onClick={() => setActiveTab("episodes")}
              className={`px-3 py-1 rounded-md font-semibold transition-all ${
                activeTab === "episodes" ? "bg-sage text-white shadow-xs" : "text-ink-muted hover:text-ink"
              }`}
            >
              Cognitive Episodes ({filteredHistory.length})
            </button>
            <button
              onClick={() => setActiveTab("events")}
              className={`px-3 py-1 rounded-md font-semibold transition-all ${
                activeTab === "events" ? "bg-sage text-white shadow-xs" : "text-ink-muted hover:text-ink"
              }`}
            >
              Behavioral Events ({htEvents.length})
            </button>
            <button
              onClick={() => setActiveTab("stream")}
              className={`px-3 py-1 rounded-md font-semibold transition-all ${
                activeTab === "stream" ? "bg-sage text-white shadow-xs" : "text-ink-muted hover:text-ink"
              }`}
            >
              Raw Feature Stream ({htObservations.length})
            </button>
          </div>
        </div>

        {activeTab === "episodes" && (
          <div className="flex items-center gap-1.5 text-xs">
            <Filter className="w-3.5 h-3.5 text-ink-muted" />
            <span className="text-ink-muted font-medium">State:</span>
            {["ALL", "PARALYSIS_LIKELY", "OVERLOAD_LIKELY", "FOCUSED", "RELAXED"].map((st) => (
              <button
                key={st}
                onClick={() => setStateFilter(st)}
                className={`text-[11px] px-2 py-0.5 rounded font-medium transition-colors ${
                  stateFilter === st ? "bg-sage text-white font-bold" : "bg-ivory text-ink hover:bg-black/5"
                }`}
              >
                {st.replace("_", " ")}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* TAB 1: Cognitive Episodes (Backwards compatible with tests & episode tracking) */}
      {activeTab === "episodes" && (
        <div className="space-y-3">
          {filteredHistory.length === 0 ? (
            <Card className="p-8 text-center bg-panel border-black/5 space-y-2">
              <Clock className="w-8 h-8 text-ink-muted/50 mx-auto" />
              <h3 className="text-sm font-bold text-ink">No Observation Episodes Recorded</h3>
              <p className="text-xs text-ink-muted max-w-sm mx-auto">
                Episodes are recorded automatically when evidence thresholds are sustained over time.
              </p>
            </Card>
          ) : (
            filteredHistory.map((rec) => {
              const isSelected = selectedRecordId === rec.event_id;
              return (
                <Card
                  key={rec.event_id}
                  className="p-4 bg-panel border-black/5 shadow-xs space-y-3 transition-all hover:border-black/20"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Badge variant={getStateBadgeVariant(rec.state)}>
                          {rec.state.replace("_", " ")}
                        </Badge>
                        <span className="text-xs font-bold text-ink font-mono">
                          Duration: {rec.duration_seconds}s
                        </span>
                        <span className="text-xs text-ink-muted">
                          (Score: {Math.round(rec.score * 100)}%)
                        </span>
                      </div>
                      <p className="text-xs text-ink-muted">{rec.qualification_reason}</p>
                    </div>

                    <div className="text-right flex-shrink-0">
                      <span className="text-[10px] font-mono text-ink-muted block">
                        {new Date(rec.start_ts * 1000).toLocaleTimeString()}
                      </span>
                      <button
                        onClick={() => setSelectedRecordId(isSelected ? null : rec.event_id)}
                        className="text-xs text-sage font-semibold hover:underline inline-flex items-center gap-0.5 mt-1"
                      >
                        <span>{isSelected ? "Hide Details" : "Details"}</span>
                        {isSelected ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  </div>

                  {/* Contributing Measurements Drawer */}
                  {isSelected && (
                    <div className="pt-3 border-t border-black/5 text-xs space-y-2">
                      <span className="font-bold text-ink text-[11px] uppercase tracking-wider">
                        Contributing Sensor Measurements
                      </span>
                      <div className="space-y-1.5">
                        {rec.contributing_features.map((f, idx) => (
                          <div
                            key={idx}
                            className="p-2 rounded-lg bg-ivory border border-black/5 flex flex-wrap items-center justify-between gap-2 text-[11px]"
                          >
                            <span className="font-bold text-ink">{f.feature.replace("_", " ")}</span>
                            <span className="font-mono text-sage">{f.measured_value}</span>
                            <span className="font-mono text-ink-muted">Baseline: {f.baseline_value}</span>
                            <span className="font-mono text-clay font-bold">{f.deviation}</span>
                            <span className="text-ink-muted italic">{f.contribution}</span>
                          </div>
                        ))}
                      </div>

                      {/* User Feedback Buttons */}
                      <div className="pt-2 flex items-center justify-between border-t border-black/5">
                        <span className="text-[10px] text-ink-muted">Was this observation accurate?</span>
                        <div className="flex gap-1.5">
                          <button
                            onClick={() => sendReviewObservation(rec.event_id, "useful")}
                            className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${
                              rec.user_review === "useful"
                                ? "bg-sage text-white border-sage"
                                : "bg-white text-ink border-black/10 hover:border-black/20"
                            }`}
                          >
                            Accurate
                          </button>
                          <button
                            onClick={() => sendReviewObservation(rec.event_id, "incorrect")}
                            className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${
                              rec.user_review === "incorrect"
                                ? "bg-clay text-white border-clay"
                                : "bg-white text-ink border-black/10 hover:border-black/20"
                            }`}
                          >
                            Inaccurate
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </Card>
              );
            })
          )}
        </div>
      )}

      {/* TAB 2: Conservative Behavioral Events */}
      {activeTab === "events" && (
        <div className="space-y-3">
          {htEvents.length === 0 ? (
            <Card className="p-8 text-center bg-panel border-black/5 space-y-2">
              <Clock className="w-8 h-8 text-ink-muted/50 mx-auto" />
              <h3 className="text-sm font-bold text-ink">No Behavioral Events Recorded</h3>
              <p className="text-xs text-ink-muted max-w-sm mx-auto">
                Observer generates events for sustained kinematic or interaction states (&ge; 60s low movement or &ge; 90s idle).
              </p>
            </Card>
          ) : (
            htEvents.map((ev) => (
              <Card key={ev.event_id} className="p-4 bg-panel border-black/5 shadow-xs space-y-2">
                <div className="flex items-start justify-between">
                  <div>
                    <span className="font-bold text-ink text-sm">{ev.event_type}</span>
                    <p className="text-xs text-ink-muted mt-0.5">{ev.explanation}</p>
                  </div>
                  <span className="text-[10px] font-mono text-ink-muted">{ev.duration_seconds}s</span>
                </div>
              </Card>
            ))
          )}
        </div>
      )}

      {/* TAB 3: Raw Observation Feature Stream */}
      {activeTab === "stream" && (
        <Card className="p-4 bg-panel border-black/5 shadow-xs space-y-3">
          <div className="flex items-center justify-between text-xs">
            <span className="font-bold text-ink">Granular Biometric Observation Stream</span>
            <span className="text-[10px] text-ink-muted font-mono">{htObservations.length} samples</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-black/10 text-[11px] font-bold text-ink-muted">
                  <th className="pb-2">Time</th>
                  <th className="pb-2">Feature</th>
                  <th className="pb-2">Value</th>
                  <th className="pb-2">Unit</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2">Provenance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-black/5 font-mono text-[11px]">
                {htObservations.map((o) => (
                  <tr key={o.observation_id} className="hover:bg-ivory/50">
                    <td className="py-2 text-ink-muted">{new Date(o.timestamp * 1000).toLocaleTimeString()}</td>
                    <td className="py-2 font-sans font-bold text-ink">{o.feature_name}</td>
                    <td className="py-2 text-sage font-bold">
                      {o.measured_value !== null && o.measured_value !== undefined ? o.measured_value.toFixed(4) : "null"}
                    </td>
                    <td className="py-2 text-ink-muted">{o.unit}</td>
                    <td className="py-2">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-sans ${o.validity_status === "valid" ? "bg-sage/10 text-sage" : "bg-clay/10 text-clay"}`}>
                        {o.validity_status}
                      </span>
                    </td>
                    <td className="py-2 font-sans text-ink-muted">{o.provenance}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Full Multi-Section Report Modal */}
      {showReportModal && activeReport && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <Card className="max-w-3xl w-full max-h-[85vh] flex flex-col bg-white border-black/10 shadow-xl rounded-2xl overflow-hidden">
            {/* Modal Header */}
            <div className="p-4 bg-panel border-b border-black/10 flex items-center justify-between">
              <div>
                <h3 className="font-extrabold text-base text-ink flex items-center gap-2">
                  <FileText className="w-4 h-4 text-sage" /> Longitudinal Behavioral Report
                </h3>
                <span className="text-[11px] font-mono text-ink-muted">
                  ID: {(activeReport as any).report_id || "Observer Report"}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Button size="sm" variant="secondary" onClick={handleExportCSV} className="h-8 text-xs gap-1">
                  <Download className="w-3.5 h-3.5" />
                  <span>Download CSV</span>
                </Button>
                <Button size="sm" variant="primary" onClick={handlePrintReport} className="h-8 text-xs gap-1 font-bold">
                  <Printer className="w-3.5 h-3.5" />
                  <span>Print / PDF</span>
                </Button>
                <button
                  onClick={() => setShowReportModal(false)}
                  className="p-1 rounded-lg text-ink-muted hover:text-ink hover:bg-black/5"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-5 text-xs">
              <div className="p-3.5 rounded-xl bg-ivory border border-black/10 text-[11px] text-ink-muted leading-relaxed">
                <span className="font-bold text-ink">Non-Diagnostic Healthcare Disclaimer: </span>
                This report is compiled from local webcam biometric estimation and user check-ins.
                It does not constitute a clinical, neurological, or psychiatric diagnosis.
              </div>

              {/* Direct Measurements */}
              <div className="space-y-2">
                <h4 className="font-bold text-ink uppercase tracking-wider text-[11px] border-b border-black/5 pb-1">
                  1. Direct Physical Facial &amp; Head Measurements
                </h4>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {Object.entries((activeReport as any).direct_measurements || {}).map(([k, v]: any) => (
                    <div key={k} className="p-2.5 rounded-lg bg-ivory border border-black/5 font-mono">
                      <span className="text-[10px] text-ink-muted block font-sans">{k}</span>
                      <span className="font-bold text-ink text-sm">
                        {v.distribution?.median ?? "--"} {v.unit}
                      </span>
                      <span className="text-[10px] text-ink-muted block font-sans">
                        IQR: {v.distribution?.p25} – {v.distribution?.p75}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Derived Metrics */}
              <div className="space-y-2">
                <h4 className="font-bold text-ink uppercase tracking-wider text-[11px] border-b border-black/5 pb-1">
                  2. Derived Behavioral Metrics
                </h4>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {Object.entries((activeReport as any).derived_metrics || {}).map(([k, v]: any) => (
                    <div key={k} className="p-2.5 rounded-lg bg-ivory border border-black/5 font-mono">
                      <span className="text-[10px] text-ink-muted block font-sans">{k}</span>
                      <span className="font-bold text-sage text-sm">
                        {v.distribution?.median ?? "--"} {v.unit}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Automated Observations */}
              <div className="space-y-2">
                <h4 className="font-bold text-ink uppercase tracking-wider text-[11px] border-b border-black/5 pb-1">
                  3. Conservative Automated Observations ({((activeReport as any).automated_observations || []).length})
                </h4>
                {((activeReport as any).automated_observations || []).length === 0 ? (
                  <p className="text-ink-muted italic">No notable events recorded in selected period.</p>
                ) : (
                  <div className="space-y-1.5">
                    {((activeReport as any).automated_observations || []).map((e: any) => (
                      <div key={e.event_id} className="p-2 rounded bg-ivory border border-black/5 text-xs flex justify-between">
                        <div>
                          <span className="font-bold text-ink">{e.event_type}</span>
                          <p className="text-[10px] text-ink-muted">{e.explanation}</p>
                        </div>
                        <span className="font-mono text-ink-muted">{e.duration_seconds}s</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};
