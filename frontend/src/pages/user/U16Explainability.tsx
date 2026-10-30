import React, { useEffect, useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { api } from '../../api/client';
import { PageHeader } from '../../components/common/PageHeader';
import { AlertCircle } from 'lucide-react';

type ScenarioDiagnostics = {
  metrics?: {
    ai?: {
      decision_trace?: { fallback_used: boolean }[];
      fallback_reason_counts?: Record<string, number>;
      mean_decision_time_ms?: number;
      invalid_actions_accepted?: number;
    };
  };
};
type SavedRun = { id: string; planName: string; modelSha256?: string; scenarios: Record<string, ScenarioDiagnostics> };
export const U16Explainability: React.FC = () => {
  const { navigate, currentPath } = useViewport();
  const runId = currentPath.split('/')[2] || '';
  const [run, setRun] = useState<SavedRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (runId) api.get<SavedRun>(`/results/${encodeURIComponent(runId)}`).then(setRun).catch((err) => setError(err instanceof Error ? err.message : 'Could not load saved result.')); }, [runId]);
  if (error) return <div role="alert" className="p-6 text-rose-700">{error}</div>;
  if (!run) return <div className="p-6 text-brand-text-muted">Loading saved result…</div>;
  const diagnostics = Object.entries(run.scenarios).map(([scenario, value]) => ({
    scenario,
    ai: value.metrics?.ai,
  }));
  return <div className="p-6 max-w-4xl mx-auto space-y-5">
    <PageHeader title={`Model Diagnostics: ${run.planName}`} subtitle={`Saved simulation ${run.id}`} actions={<button onClick={() => navigate(`/results/${run.id}`)} className="px-3 py-2 border border-brand-border rounded-lg">Back to results</button>} />
    <section className="p-4 bg-brand-surface border border-brand-border rounded-xl space-y-2"><h2 className="font-semibold">Model artifact</h2><p className="font-mono text-caption break-all">{run.modelSha256 || 'Checkpoint hash not included in this summary response.'}</p><p className="text-caption text-brand-text-secondary">Decision traces list the model's candidate routes and Q-values, the route executed, and any safety fallback. Q-values are ranking scores, not probabilities.</p></section>
    <section className="p-4 bg-brand-surface border border-brand-border rounded-xl space-y-3"><h2 className="font-semibold">Inference diagnostics by scenario</h2>{diagnostics.map(({ scenario, ai }) => {
      const trace = ai?.decision_trace || [];
      const fallbackCount = trace.filter((decision) => decision.fallback_used).length;
      return <div key={scenario} className="p-3 bg-brand-bg rounded-lg text-caption"><p className="font-semibold capitalize">{scenario.replace(/_/g, ' ')}</p>{ai ? <p className="text-brand-text-secondary mt-1">{trace.length ? `${trace.length} decisions, ${fallbackCount} fallback(s)` : 'No per-decision trace in this older run'} · {ai.invalid_actions_accepted ?? '—'} invalid actions accepted · {typeof ai.mean_decision_time_ms === 'number' ? `${ai.mean_decision_time_ms.toFixed(3)} ms mean decision` : 'decision time unavailable'}</p> : <p className="text-brand-text-muted mt-1">AI diagnostics unavailable.</p>}{ai?.fallback_reason_counts && <p className="text-brand-text-muted mt-1">Fallback reasons: {Object.entries(ai.fallback_reason_counts).map(([reason, count]) => `${reason} ${count}`).join(' · ') || 'none'}</p>}</div>;
    })}</section>
    <div className="p-4 rounded-lg border border-blue-300 bg-blue-50 text-blue-900 text-caption flex gap-2"><AlertCircle className="w-4 h-4 shrink-0" /><span>Open the saved result to inspect candidate paths and Q-values for each recorded AI decision. Runs made before decision-trace recording contain aggregate metrics only.</span></div>
  </div>;
};
