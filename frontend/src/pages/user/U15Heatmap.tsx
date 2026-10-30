import React, { useEffect, useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { api } from '../../api/client';
import { PageHeader } from '../../components/common/PageHeader';
import { AlertCircle } from 'lucide-react';

type SavedRun = { id: string; planName: string; scenarios: Record<string, { metrics?: Record<string, { fraction_steps_over_0_9?: number }> }> };
export const U15Heatmap: React.FC = () => {
  const { navigate, currentPath } = useViewport();
  const runId = currentPath.split('/')[2] || '';
  const [run, setRun] = useState<SavedRun | null>(null);
  const [scenario, setScenario] = useState('normal');
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (runId) api.get<SavedRun>(`/results/${encodeURIComponent(runId)}`).then((value) => { setRun(value); setScenario(Object.keys(value.scenarios)[0] || 'normal'); }).catch((err) => setError(err instanceof Error ? err.message : 'Could not load saved result.')); }, [runId]);
  if (error) return <div role="alert" className="p-6 text-rose-700">{error}</div>;
  if (!run) return <div className="p-6 text-brand-text-muted">Loading saved simulation…</div>;
  const metrics = run.scenarios[scenario]?.metrics || {};
  return <div className="p-6 max-w-5xl mx-auto space-y-5">
    <PageHeader title={`Utilization Summary: ${run.planName}`} subtitle="Aggregate utilization metrics saved by this run." actions={<button onClick={() => navigate(`/results/${run.id}`)} className="px-3 py-2 border border-brand-border rounded-lg">Back to results</button>} />
    <div className="flex gap-2 flex-wrap">{Object.keys(run.scenarios).map((key) => <button key={key} onClick={() => setScenario(key)} className={`px-3 py-1 rounded-full text-caption capitalize ${key === scenario ? 'bg-brand-primary text-white' : 'border border-brand-border'}`}>{key.replace(/_/g, ' ')}</button>)}</div>
    <section className="bg-brand-surface border border-brand-border rounded-xl p-4"><h2 className="font-semibold mb-3">Fraction of steps above 0.9 backbone utilization</h2><div className="grid sm:grid-cols-3 gap-3">{Object.entries(metrics).map(([policy, value]) => <div key={policy} className="p-3 bg-brand-bg rounded-lg"><div className="capitalize text-caption">{policy.replace(/_/g, ' ')}</div><div className="text-h2 font-mono">{typeof value.fraction_steps_over_0_9 === 'number' ? `${(value.fraction_steps_over_0_9 * 100).toFixed(2)}%` : '—'}</div></div>)}</div></section>
    <div className="p-4 rounded-lg border border-amber-300 bg-amber-50 text-amber-900 text-caption flex gap-2"><AlertCircle className="w-4 h-4 shrink-0" /><span>Per-link utilization and per-step history were not saved by the backend, so an interactive link heatmap cannot be reconstructed from this run.</span></div>
  </div>;
};
