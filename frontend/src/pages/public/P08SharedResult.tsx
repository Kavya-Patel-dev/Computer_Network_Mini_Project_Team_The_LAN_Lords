import React, { useEffect, useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { api } from '../../api/client';
import { PageSkeleton } from '../../components/common/SkeletonLoader';
import { ArrowLeft, Share2 } from 'lucide-react';

type Metric = {
  mean_packet_loss?: number;
  mean_path_latency_ms?: number;
  p95_path_latency_ms?: number;
  delivered_throughput_mbps?: number;
  fraction_steps_over_0_9?: number;
};
type SharedRun = {
  id: string;
  planName: string;
  version: string;
  date: string;
  scenarios: Record<string, { metrics?: Record<string, Metric> }>;
  verdictText: string;
};
const POLICY_NAMES: Record<string, string> = { static: 'Static Dijkstra', load_aware: 'Load-aware Dijkstra', ai: 'AI + fallback' };
const number = (value: number | undefined, digits = 3) => typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '—';

export const P08SharedResult: React.FC = () => {
  const { navigate, currentPath } = useViewport();
  const token = currentPath.split('/')[2] || '';
  const [result, setResult] = useState<SharedRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!token) return;
    api.get<SharedRun>(`/shares/${encodeURIComponent(token)}`)
      .then(setResult)
      .catch((err) => setError(err instanceof Error ? err.message : 'This shared result is unavailable.'))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <PageSkeleton />;
  if (error || !result) return (
    <div className="min-h-screen bg-brand-bg flex flex-col items-center justify-center p-6 text-center">
      <h1 className="text-h1 font-bold mb-2">Shared result unavailable</h1>
      <p role="alert" className="text-body text-brand-text-secondary max-w-lg">{error || 'The share token is missing.'}</p>
      <p className="text-caption text-brand-text-muted mt-2">The link may have expired, been revoked, or be invalid.</p>
      <button onClick={() => navigate('/')} className="mt-5 px-4 py-2 rounded-lg bg-brand-primary text-white">Go Home</button>
    </div>
  );

  return (
    <div className="min-h-screen bg-brand-bg text-brand-text-primary p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="p-3 bg-brand-surface border border-brand-border rounded-lg flex items-center gap-2 text-caption text-brand-text-secondary"><Share2 className="w-4 h-4 text-brand-primary" /><span>Read-only shared report · run {result.id}</span></div>
        <header className="flex flex-wrap items-end justify-between gap-3">
          <div><h1 className="text-h1 font-bold">{result.planName} ({result.version})</h1><p className="text-caption text-brand-text-muted mt-1">Saved {new Date(result.date).toLocaleString()}</p></div>
          <button onClick={() => navigate('/')} className="px-3 py-2 rounded-lg border border-brand-border bg-brand-surface text-caption flex items-center gap-2"><ArrowLeft className="w-4 h-4" />Home</button>
        </header>
        <section className="p-4 rounded-lg border border-brand-border bg-brand-surface"><h2 className="font-semibold mb-1">Saved verdict</h2><p className="text-body text-brand-text-secondary">{result.verdictText}</p></section>
        {Object.entries(result.scenarios).map(([scenario, data]) => (
          <section key={scenario} className="bg-brand-surface border border-brand-border rounded-xl p-4 space-y-3">
            <h2 className="text-h3 font-semibold capitalize">{scenario.replace(/_/g, ' ')}</h2>
            <div className="overflow-x-auto"><table className="w-full text-left text-caption"><thead><tr className="border-b border-brand-border"><th className="p-3">Policy</th><th className="p-3">Mean packet loss</th><th className="p-3">Mean latency</th><th className="p-3">P95 latency</th><th className="p-3">Throughput</th><th className="p-3">Steps &gt; 0.9</th></tr></thead><tbody>
              {Object.entries(data.metrics || {}).map(([key, metric]) => <tr key={key} className="border-b border-brand-border last:border-0"><td className="p-3 font-semibold">{POLICY_NAMES[key] || key}</td><td className="p-3">{number(metric.mean_packet_loss !== undefined ? metric.mean_packet_loss * 100 : undefined)}%</td><td className="p-3">{number(metric.mean_path_latency_ms, 2)} ms</td><td className="p-3">{number(metric.p95_path_latency_ms, 2)} ms</td><td className="p-3">{number(metric.delivered_throughput_mbps, 2)} Mbps</td><td className="p-3">{number(metric.fraction_steps_over_0_9 !== undefined ? metric.fraction_steps_over_0_9 * 100 : undefined, 2)}%</td></tr>)}
            </tbody></table></div>
          </section>
        ))}
        <p className="text-caption text-brand-text-muted">Only aggregate metrics saved by the simulation service are shown; per-step traces are not included.</p>
      </div>
    </div>
  );
};
