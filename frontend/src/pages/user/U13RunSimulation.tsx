import React, { useEffect, useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { api } from '../../api/client';
import { Plan } from '../../types/plan';
import { PageHeader } from '../../components/common/PageHeader';
import { Play, CheckCircle2, Clock, FileText, AlertTriangle } from 'lucide-react';

type Metric = {
  mean_packet_loss: number;
  mean_path_latency_ms: number;
  p95_path_latency_ms: number;
  delivered_throughput_mbps: number;
  fraction_steps_over_0_9: number;
  fraction_steps_access_over_0_9?: number;
};
type ScenarioRun = { metrics: { static: Metric; load_aware: Metric; ai: Metric } };
type RunSummary = {
  id: string;
  runId: string;
  planName: string;
  version: string;
  selectedScenarios: string[];
  scenarios: Record<string, ScenarioRun>;
  verdictText: string;
};

export const U13RunSimulation: React.FC = () => {
  const { navigate, currentPath } = useViewport();
  const planId = currentPath.split('/')[2] || '';
  const [plan, setPlan] = useState<Plan | null>(null);
  const [run, setRun] = useState<RunSummary | null>(null);
  const [stage, setStage] = useState<'idle' | 'running' | 'completed' | 'failed'>('idle');
  const [error, setError] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    if (stage !== 'running') return;
    const startedAt = Date.now();
    setElapsedSeconds(0);
    const timer = window.setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [stage]);

  useEffect(() => {
    if (!planId) return;
    api.get<Plan>('/records/' + encodeURIComponent(planId))
      .then(setPlan)
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load this saved plan.'));
  }, [planId]);

  const startSimulation = async () => {
    if (!planId || plan?.status !== 'Approved') return;
    setStage('running');
    setError(null);
    setRun(null);
    try {
      const result = await api.post<RunSummary>('/records/' + encodeURIComponent(planId) + '/runs', {
        seed: 1000,
        max_steps: 500,
      }, { timeoutMs: 20 * 60 * 1000 });
      setRun(result);
      setStage('completed');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The routing simulation failed.');
      setStage('failed');
    }
  };

  const formatMetric = (metric: Metric | undefined) => metric
    ? (metric.mean_packet_loss * 100).toFixed(3) + '% loss · ' +
      metric.mean_path_latency_ms.toFixed(2) + ' ms mean latency · ' +
      metric.delivered_throughput_mbps.toFixed(2) + ' Mbps per routed flow · ' +
      (metric.fraction_steps_access_over_0_9 === undefined
        ? 'access-link saturation unavailable'
        : (metric.fraction_steps_access_over_0_9 * 100).toFixed(1) + '% steps with access util. >0.9')
    : 'Metric unavailable';
  const isApproved = plan?.status === 'Approved';
  const elapsedLabel = `${Math.floor(elapsedSeconds / 60)}m ${String(elapsedSeconds % 60).padStart(2, '0')}s`;

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-8">
      <PageHeader title="Execute Routing Simulation" subtitle="Run the saved approved topology through the selected scenarios using the frozen routing checkpoint." />
      {error && <div role="alert" className="p-4 rounded-lg border border-rose-300 bg-rose-50 text-rose-800 flex items-start gap-2"><AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" /><span className="text-caption">{error}</span></div>}

      {stage === 'idle' && (
        <div className="bg-brand-surface border border-brand-border rounded-xl p-6 space-y-6 shadow-sm">
          <div className="space-y-2">
            <h3 className="text-h3 font-bold text-brand-text-primary">Ready to Launch Simulation</h3>
            <p className="text-body text-brand-text-secondary leading-relaxed">
              {plan ? <>Plan <strong className="font-mono text-brand-text-primary">{plan.name} ({plan.version})</strong> is {plan.status.toLowerCase()}.</> : 'Loading the saved plan…'}
            </p>
          </div>
          {plan && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 p-4 bg-brand-bg rounded-lg border border-brand-border text-caption">
              <div><span className="text-brand-text-muted">Routers</span><p className="font-mono font-bold text-brand-text-primary text-body">{plan.routerCount}</p></div>
              <div><span className="text-brand-text-muted">Hosts</span><p className="font-mono font-bold text-brand-text-primary text-body">{plan.hostCount}</p></div>
              <div><span className="text-brand-text-muted">Scenarios</span><p className="font-mono font-bold text-brand-text-primary text-body">{plan.selectedScenarios.length}</p></div>
              <div><span className="text-brand-text-muted">Traffic</span><p className="font-mono font-bold text-brand-primary text-body">{plan.trafficPreset}</p></div>
            </div>
          )}
          {plan && !isApproved && (
            <div role="status" className="p-4 rounded-lg border border-amber-300 bg-amber-50 text-amber-900 text-caption">
              Simulation is locked while this plan is <strong>{plan.status}</strong>. Submit it for administrator review and wait for approval, then return here. The API rejects unapproved plans too.
            </div>
          )}
          <div className="p-4 rounded-lg border border-brand-border bg-brand-bg text-caption text-brand-text-secondary">
            This run evaluates Static Dijkstra, Load-aware Dijkstra, and AI + safety fallback for each selected scenario (500 steps each). Results are saved when all scenarios finish; large topologies or several scenarios can take a few minutes.
          </div>
          <div className="flex justify-end pt-4 border-t border-brand-border">
            <button onClick={() => void startSimulation()} disabled={!isApproved} className="px-6 py-3 rounded-lg bg-emerald-600 text-white text-btn font-semibold hover:bg-emerald-700 flex items-center gap-2 shadow-md touch-target disabled:opacity-50">
              <Play className="w-5 h-5 fill-current" /><span>Start Simulation</span>
            </button>
          </div>
        </div>
      )}

      {stage === 'running' && (
        <div className="bg-brand-surface border border-brand-border rounded-xl p-6 space-y-6 shadow-xl">
          <div className="flex items-center gap-2 pb-3 border-b border-brand-border"><span className="w-3 h-3 rounded-full bg-blue-500 animate-pulse" /><h3 className="text-h3 font-bold text-brand-text-primary">Simulation running</h3></div>
          <div className="p-4 bg-brand-bg border border-brand-border rounded-lg text-caption text-brand-text-secondary">
            Backend is evaluating {plan?.selectedScenarios.length ?? 0} selected scenario(s) sequentially. Elapsed time: <strong>{elapsedLabel}</strong>. Keep this tab open; this endpoint returns the report after the full run, so it does not stream per-step progress.
          </div>
        </div>
      )}

      {stage === 'completed' && run && (
        <div className="bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-300 dark:border-emerald-800 rounded-xl p-8 space-y-5 shadow-xl">
          <div className="text-center space-y-3">
            <div className="w-14 h-14 rounded-full bg-emerald-100 text-emerald-700 mx-auto flex items-center justify-center"><CheckCircle2 className="w-8 h-8" /></div>
            <h2 className="text-h1 font-bold text-emerald-900 dark:text-emerald-100">Simulation completed</h2>
            <p className="text-body text-emerald-800 dark:text-emerald-200">{run.verdictText}</p>
            <p className="text-caption text-brand-text-muted">Saved run {run.runId}</p>
          </div>
          <div className="overflow-x-auto bg-white/70 dark:bg-black/10 rounded-lg border border-brand-border">
            <table className="w-full text-left text-caption">
              <thead><tr className="border-b border-brand-border"><th className="p-3">Scenario</th><th className="p-3">Static Dijkstra</th><th className="p-3">Load-aware</th><th className="p-3">AI + fallback</th></tr></thead>
              <tbody>{Object.entries(run.scenarios).map(([scenario, value]) => (
                <tr key={scenario} className="border-b border-brand-border last:border-0 align-top">
                  <td className="p-3 font-semibold capitalize">{scenario.replace(/_/g, ' ')}</td>
                  <td className="p-3">{formatMetric(value.metrics.static)}</td>
                  <td className="p-3">{formatMetric(value.metrics.load_aware)}</td>
                  <td className="p-3">{formatMetric(value.metrics.ai)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          <div className="pt-4 flex justify-center gap-3">
            <button onClick={() => navigate('/results/' + run.id)} className="px-6 py-3 rounded-lg bg-brand-primary text-white text-btn font-semibold hover:opacity-90 flex items-center gap-2 shadow-md touch-target"><FileText className="w-5 h-5" /><span>Open Saved Results</span></button>
            <button onClick={() => { setStage('idle'); setRun(null); }} className="px-5 py-3 rounded-lg border border-brand-border text-brand-text-secondary text-btn font-semibold flex items-center gap-2"><Clock className="w-4 h-4" /><span>Run Again</span></button>
          </div>
        </div>
      )}

      {stage === 'failed' && (
        <div className="bg-brand-surface border border-brand-border rounded-xl p-6 text-center space-y-4">
          <p className="text-body text-brand-text-secondary">The failed run was not saved. Fix the reported issue and retry.</p>
          <button onClick={() => { setStage('idle'); setError(null); }} className="px-5 py-2 rounded-lg bg-brand-primary text-white text-btn font-semibold">Back to run setup</button>
        </div>
      )}
    </div>
  );
};

