import React, { useEffect, useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { api } from '../../api/client';
import { PageHeader } from '../../components/common/PageHeader';
import { AlertCircle } from 'lucide-react';

type Metric = { mean_packet_loss?: number; mean_path_latency_ms?: number; delivered_throughput_mbps?: number };
type SavedRun = { id: string; planName: string; scenarios: Record<string, { metrics?: Record<string, Metric> }> };
export const U17FailureTimeline: React.FC = () => {
  const { currentPath, navigate } = useViewport();
  const runId = currentPath.split('/')[2] || '';
  const [run, setRun] = useState<SavedRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (runId) api.get<SavedRun>(`/results/${encodeURIComponent(runId)}`).then(setRun).catch((err) => setError(err instanceof Error ? err.message : 'Could not load saved result.')); }, [runId]);
  if (error) return <div role="alert" className="p-6 text-rose-700">{error}</div>;
  if (!run) return <div className="p-6 text-brand-text-muted">Loading saved result…</div>;
  const rows = Object.entries(run.scenarios).filter(([key]) => key.includes('failure'));
  return <div className="p-6 max-w-5xl mx-auto space-y-5">
    <PageHeader title={`Failure Scenario Summary: ${run.planName}`} subtitle="Actual aggregate metrics saved for failure scenarios." actions={<button onClick={() => navigate(`/results/${run.id}`)} className="px-3 py-2 border border-brand-border rounded-lg">Back to results</button>} />
    {!rows.length && <p className="p-4 bg-brand-surface border border-brand-border rounded-lg text-caption">This run did not save link- or router-failure scenarios.</p>}
    {rows.map(([scenario, data]) => <section key={scenario} className="p-4 bg-brand-surface border border-brand-border rounded-xl space-y-3"><h2 className="text-h3 font-semibold capitalize">{scenario.replace(/_/g, ' ')}</h2><div className="overflow-x-auto"><table className="w-full text-left text-caption"><thead><tr className="border-b border-brand-border"><th className="p-3">Policy</th><th className="p-3">Mean loss</th><th className="p-3">Mean latency</th><th className="p-3">Delivered throughput</th></tr></thead><tbody>{Object.entries(data.metrics || {}).map(([policy, metric]) => <tr key={policy} className="border-b border-brand-border last:border-0"><td className="p-3 capitalize">{policy.replace(/_/g, ' ')}</td><td className="p-3">{typeof metric.mean_packet_loss === 'number' ? `${(metric.mean_packet_loss * 100).toFixed(3)}%` : '—'}</td><td className="p-3">{typeof metric.mean_path_latency_ms === 'number' ? `${metric.mean_path_latency_ms.toFixed(2)} ms` : '—'}</td><td className="p-3">{typeof metric.delivered_throughput_mbps === 'number' ? `${metric.delivered_throughput_mbps.toFixed(2)} Mbps` : '—'}</td></tr>)}</tbody></table></div></section>)}
    <div className="p-4 rounded-lg border border-amber-300 bg-amber-50 text-amber-900 text-caption flex gap-2"><AlertCircle className="w-4 h-4 shrink-0" /><span>The API stores scenario aggregates, not timestamped failure events or recovery traces. This page does not infer a recovery timeline.</span></div>
  </div>;
};
