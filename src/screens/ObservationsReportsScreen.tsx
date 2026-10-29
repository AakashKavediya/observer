import React, { useState, useEffect } from "react";
import {
  FileText,
  Filter,
  Check,
  X,
  HelpCircle,
  Trash2,
  Download,
  Clock,
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
    generatedReport,
    fetchHistory,
    sendReviewObservation,
    sendDeleteObservation,
    sendClearHistory,
    sendGenerateReport,
  } = useObserverStore();

  const [stateFilter, setStateFilter] = useState<string>("ALL");
  const [selectedRecordId, setSelectedRecordId] = useState<string | null>(null);
  const [showReportModal, setShowReportModal] = useState(false);

  useEffect(() => {
    fetchHistory(stateFilter === "ALL" ? undefined : stateFilter);
  }, [stateFilter, fetchHistory]);

  const filteredRecords = historyRecords.filter((rec) => {
    if (stateFilter === "ALL") return true;
    return rec.state === stateFilter;
  });

  const handleExportCSV = () => {
    if (!generatedReport?.csv_export) return;
    const blob = new Blob([generatedReport.csv_export], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `observer_report_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
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
    <div className="max-w-4xl mx-auto py-8 px-4 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-extrabold tracking-tight text-ink">
            Observations & Reports
          </h2>
          <p className="text-xs text-ink-muted mt-1">
            Review past cognitive state episodes, inspect contributing biometric signals, and generate evidence reports.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              sendGenerateReport();
              setShowReportModal(true);
            }}
          >
            <FileText className="w-4 h-4 mr-1.5" />
            <span>Generate Report</span>
          </Button>
          {historyRecords.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="text-clay hover:bg-clay/10"
              onClick={sendClearHistory}
              aria-label="Delete all observations"
            >
              <Trash2 className="w-4 h-4 mr-1" />
              <span>Clear History</span>
            </Button>
          )}
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-panel border border-black/5 rounded-2xl shadow-xs">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-ink-muted ml-1" />
          <span className="text-xs font-semibold text-ink-muted">Filter State:</span>
          {["ALL", "PARALYSIS_LIKELY", "OVERLOAD_LIKELY", "FOCUSED", "RELAXED"].map((st) => (
            <button
              key={st}
              onClick={() => setStateFilter(st)}
              className={`text-xs px-2.5 py-1 rounded-lg font-medium transition-colors ${
                stateFilter === st
                  ? "bg-sage text-white font-bold"
                  : "bg-ivory text-ink hover:bg-black/5"
              }`}
            >
              {st === "ALL" ? "All" : st.replace("_", " ")}
            </button>
          ))}
        </div>

        <div className="text-xs text-ink-muted font-mono pr-2">
          {filteredRecords.length} recorded episode{filteredRecords.length !== 1 ? "s" : ""}
        </div>
      </div>

      {/* Main Records List or Empty State */}
      {filteredRecords.length === 0 ? (
        <Card className="text-center py-12 px-6 space-y-3">
          <div className="w-12 h-12 rounded-2xl bg-sage-pale flex items-center justify-center text-sage mx-auto">
            <Clock className="w-6 h-6" />
          </div>
          <h3 className="text-base font-bold text-ink">No observations recorded yet</h3>
          <p className="text-xs text-ink-muted max-w-md mx-auto leading-relaxed">
            The state engine evaluates signals quietly in the background without unsolicited alerts.
            When an episode of task paralysis or flow sustains beyond dwell thresholds, it will appear here for review.
          </p>
        </Card>
      ) : (
        <div className="space-y-3">
          {filteredRecords.map((rec) => {
            const isSelected = selectedRecordId === rec.event_id;
            const startDt = new Date(rec.start_ts * 1000);
            return (
              <Card
                key={rec.event_id}
                className={`p-4 transition-all ${
                  isSelected ? "border-sage/50 ring-1 ring-sage/30 shadow-md" : "hover:border-black/10"
                }`}
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <Badge variant={getStateBadgeVariant(rec.state)}>
                      {rec.state.replace("_", " ")}
                    </Badge>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-ink">
                          {startDt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                        </span>
                        <span className="text-[11px] text-ink-muted">
                          {startDt.toLocaleDateString([], { month: "short", day: "numeric" })}
                        </span>
                        <span className="text-[10px] bg-black/5 px-1.5 py-0.5 rounded text-ink font-mono">
                          Duration: {rec.duration_seconds.toFixed(0)}s
                        </span>
                      </div>
                      <p className="text-xs text-ink-muted mt-1 leading-snug">
                        {rec.qualification_reason}
                      </p>
                    </div>
                  </div>

                  {/* Right side actions & feedback */}
                  <div className="flex items-center gap-2 self-end sm:self-center">
                    {/* User review status buttons */}
                    <div className="flex items-center gap-1 bg-ivory p-1 rounded-lg border border-black/5">
                      <button
                        title="Mark observation as useful"
                        onClick={() => sendReviewObservation(rec.event_id, "useful")}
                        className={`p-1.5 rounded-md transition-colors ${
                          rec.user_review === "useful"
                            ? "bg-sage text-white font-bold"
                            : "text-ink-muted hover:text-ink"
                        }`}
                      >
                        <Check className="w-3.5 h-3.5" />
                      </button>
                      <button
                        title="Mark as incorrect estimate"
                        onClick={() => sendReviewObservation(rec.event_id, "incorrect")}
                        className={`p-1.5 rounded-md transition-colors ${
                          rec.user_review === "incorrect"
                            ? "bg-clay text-white font-bold"
                            : "text-ink-muted hover:text-ink"
                        }`}
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                      <button
                        title="Mark as uncertain"
                        onClick={() => sendReviewObservation(rec.event_id, "uncertain")}
                        className={`p-1.5 rounded-md transition-colors ${
                          rec.user_review === "uncertain"
                            ? "bg-forest text-white font-bold"
                            : "text-ink-muted hover:text-ink"
                        }`}
                      >
                        <HelpCircle className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setSelectedRecordId(isSelected ? null : rec.event_id)}
                    >
                      <span>Details</span>
                      {isSelected ? <ChevronUp className="w-3.5 h-3.5 ml-1" /> : <ChevronDown className="w-3.5 h-3.5 ml-1" />}
                    </Button>

                    <button
                      onClick={() => sendDeleteObservation(rec.event_id)}
                      title="Delete record"
                      className="p-1.5 text-ink-muted hover:text-clay rounded-md transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Expanded Detailed Breakdown */}
                {isSelected && (
                  <div className="mt-4 pt-4 border-t border-black/5 space-y-4">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                      <div className="p-3 bg-ivory rounded-xl border border-black/5 space-y-1">
                        <span className="text-[11px] text-ink-muted font-semibold uppercase">Evidence Score</span>
                        <p className="text-base font-extrabold text-ink font-mono">
                          {rec.score.toFixed(3)}
                        </p>
                        <p className="text-[11px] text-ink-muted">
                          Formula: {rec.scoring_method}
                        </p>
                      </div>

                      <div className="p-3 bg-ivory rounded-xl border border-black/5 space-y-1">
                        <span className="text-[11px] text-ink-muted font-semibold uppercase">Tracking Quality</span>
                        <p className="text-base font-extrabold text-sage capitalize">
                          {rec.data_quality_status}
                        </p>
                        <p className="text-[11px] text-ink-muted">
                          Event ID: <code className="font-mono text-[10px]">{rec.event_id}</code>
                        </p>
                      </div>
                    </div>

                    {/* Contributing Features Table */}
                    <div>
                      <h4 className="text-xs font-bold text-ink uppercase tracking-wider mb-2">
                        Contributing Sensor Measurements
                      </h4>
                      <div className="overflow-x-auto rounded-xl border border-black/5">
                        <table className="w-full text-left text-xs">
                          <thead className="bg-sage-pale/40 text-ink font-semibold">
                            <tr>
                              <th className="py-2 px-3">Feature</th>
                              <th className="py-2 px-3">Measured Value</th>
                              <th className="py-2 px-3">Baseline</th>
                              <th className="py-2 px-3">Deviation</th>
                              <th className="py-2 px-3">Window</th>
                              <th className="py-2 px-3">Contribution</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-black/5 bg-panel">
                            {rec.contributing_features.map((feat, idx) => (
                              <tr key={idx} className="hover:bg-ivory/50">
                                <td className="py-2 px-3 font-semibold text-ink capitalize">
                                  {feat.feature.replace("_", " ")}
                                </td>
                                <td className="py-2 px-3 font-mono text-ink">{feat.measured_value}</td>
                                <td className="py-2 px-3 font-mono text-ink-muted">{feat.baseline_value}</td>
                                <td className="py-2 px-3 font-mono font-bold text-sage">{feat.deviation}</td>
                                <td className="py-2 px-3 text-ink-muted">{feat.window}</td>
                                <td className="py-2 px-3 font-bold text-clay">{feat.contribution}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    {rec.user_notes && (
                      <div className="p-3 bg-ivory rounded-xl border border-black/5 text-xs text-ink leading-relaxed">
                        <span className="font-bold">Your notes: </span>
                        {rec.user_notes}
                      </div>
                    )}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}

      {/* ========================================================================= */}
      {/* Report Modal                                                               */}
      {/* ========================================================================= */}
      {showReportModal && generatedReport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs">
          <Card className="max-w-2xl w-full max-h-[85vh] overflow-y-auto p-6 space-y-5 bg-panel shadow-2xl border-sage/30">
            <div className="flex items-start justify-between pb-3 border-b border-black/5">
              <div>
                <h3 className="text-xl font-bold text-ink">Cognitive State Observation Report</h3>
                <p className="text-xs text-ink-muted mt-0.5">
                  Reporting Period: {generatedReport.reporting_period}
                </p>
              </div>
              <button
                onClick={() => setShowReportModal(false)}
                className="text-ink-muted hover:text-ink p-1 rounded-md"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Metrics Highlights */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center text-xs">
              <div className="p-3 bg-ivory rounded-xl border border-black/5">
                <span className="text-ink-muted">Total Episodes</span>
                <p className="text-lg font-bold text-ink mt-0.5">{generatedReport.total_observations}</p>
              </div>
              <div className="p-3 bg-ivory rounded-xl border border-black/5">
                <span className="text-ink-muted">Total Duration</span>
                <p className="text-lg font-bold text-ink mt-0.5">
                  {(generatedReport.total_episode_duration_seconds / 60).toFixed(1)} mins
                </p>
              </div>
              <div className="p-3 bg-ivory rounded-xl border border-black/5">
                <span className="text-ink-muted">Paralysis Episodes</span>
                <p className="text-lg font-bold text-clay mt-0.5">
                  {generatedReport.state_distribution["PARALYSIS_LIKELY"] ?? 0}
                </p>
              </div>
              <div className="p-3 bg-ivory rounded-xl border border-black/5">
                <span className="text-ink-muted">User Verified</span>
                <p className="text-lg font-bold text-sage mt-0.5">
                  {generatedReport.user_feedback_summary["useful"] ?? 0}
                </p>
              </div>
            </div>

            {/* Non-clinical limitations notice */}
            <div className="p-3.5 bg-ivory rounded-xl border border-black/5 text-xs text-ink-muted leading-relaxed">
              <p className="font-semibold text-ink mb-1">Non-Clinical Limitations Notice:</p>
              <p>{generatedReport.limitations_notice}</p>
            </div>

            <div className="flex justify-between items-center pt-3 border-t border-black/5">
              <Button variant="ghost" size="sm" onClick={() => setShowReportModal(false)}>
                Close
              </Button>
              <Button variant="primary" size="sm" onClick={handleExportCSV}>
                <Download className="w-4 h-4 mr-1.5" />
                Export CSV Report
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};
