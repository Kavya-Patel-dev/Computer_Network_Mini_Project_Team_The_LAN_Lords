import React, { useEffect, useMemo, useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { api } from '../../api/client';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/common/SkeletonLoader';
import { ErrorBanner } from '../../components/common/ErrorBanner';
import { ScenarioType } from '../../types/network';
import { Download, Share2, HelpCircle } from 'lucide-react';

type Metric = {
  mean_packet_loss?: number;
  mean_path_latency_ms?: number;
  p95_path_latency_ms?: number;
  delivered_throughput_mbps?: number;
  fraction_steps_over_0_9?: number;
  mean_max_access_utilization?: number;
  fraction_steps_access_over_0_9?: number;
  mean_decision_time_ms?: number;
  invalid_actions_accepted?: number;
  fallback_reason_counts?: Record<string, number>;
  decision_trace?: DecisionTraceRow[];
};
type DecisionTraceRow = {
  step: number;
  measured: boolean;
  flow_id: string;
  source: string;
  destination: string;
  candidate_paths: string[][];
  q_values: (number | null)[];
  chosen_candidate_index: number | null;
  chosen_path: string[] | null;
  fallback_used: boolean;
  fallback_reason: string;
  path_latency_ms: number | null;
  path_loss: number | null;
  step_max_backbone_utilization: number | null;
  step_max_access_utilization?: number | null;
};
type TrafficCalibration = {
  basis?: string;
  median_access_capacity_mbps?: number;
  demand_min_mbps?: number;
  demand_max_mbps?: number;
  mean_duration_steps?: number;
  target_backbone_intensity?: number;
  achievable_backbone_intensity?: number;
  note?: string;
};
type ScenarioRun = { metrics?: Record<string, Metric>; traffic_calibration?: TrafficCalibration };
type SavedRun = {
  id: string;
  runId: string;
  planName: string;
  version: string;
  date: string;
  scenarios: Record<string, ScenarioRun>;
  verdictText: string;
};

const POLICIES = [
  ['static', 'Static Dijkstra'],
  ['load_aware', 'Load-aware Dijkstra'],
  ['ai', 'AI + fallback'],
] as const;

const format = (value: number | undefined, digits = 3) =>
  typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '—';

export const U14ResultsOverview: React.FC = () => {
  const { navigate, openOverlay, currentPath } = useViewport();
  const runId = currentPath.split('/')[2] || '';
  const [run, setRun] = useState<SavedRun | null>(null);
  const [scenario, setScenario] = useState('normal');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    setLoading(true);
    api.get<SavedRun>(`/results/${encodeURIComponent(runId)}`)
      .then((result) => {
        setRun(result);
        setScenario(Object.keys(result.scenarios)[0] || 'normal');
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load this saved result.'))
      .finally(() => setLoading(false));
  }, [runId]);

  const metrics = run?.scenarios[scenario]?.metrics || {};
  const trafficCalibration = run?.scenarios[scenario]?.traffic_calibration;
  const rows = useMemo(() => POLICIES.map(([key, label]) => ({ key, label, metric: metrics[key] })), [metrics]);
  const aiMetric = metrics.ai;
  const aiTrace = aiMetric?.decision_trace || [];
  const fallbackCount = aiTrace.filter((decision) => decision.fallback_used).length;

  if (loading) return <PageSkeleton />;
  if (error || !run) return <div className="p-6"><ErrorBanner message={error || 'No saved result was selected.'} onRetry={() => navigate('/results')} /></div>;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <PageHeader
        title={`Simulation Results: ${run.planName}`}
        subtitle={`Saved run ${run.runId} · ${run.version} · ${new Date(run.date).toLocaleString()}`}
        actions={<div className="flex gap-2">
          <button onClick={() => openOverlay('O12')} className="px-3 py-2 rounded-lg border border-brand-border bg-brand-surface text-caption font-semibold flex items-center gap-2"><HelpCircle className="w-4 h-4" />Limitations</button>
          <button onClick={() => navigate(`/results/${run.id}/share`)} className="px-3 py-2 rounded-lg border border-brand-border bg-brand-surface text-caption font-semibold flex items-center gap-2"><Share2 className="w-4 h-4" />Share</button>
          <button onClick={() => openOverlay('O11', { runId: run.id })} className="px-3 py-2 rounded-lg bg-brand-primary text-white text-caption font-semibold flex items-center gap-2"><Download className="w-4 h-4" />Export JSON</button>
        </div>}
      />

      <section className="p-4 rounded-lg border border-brand-border bg-brand-surface text-body">
        <h2 className="font-semibold mb-1">Saved verdict</h2><p className="text-brand-text-secondary">{run.verdictText}</p>
      </section>

      <section className="bg-brand-surface border border-brand-border rounded-xl p-4 space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-overline text-brand-text-muted mr-1">Scenario:</span>
          {Object.keys(run.scenarios).map((key) => <button key={key} onClick={() => setScenario(key)} className={`px-3 py-1 rounded-full text-caption capitalize ${scenario === key ? 'bg-brand-primary text-white' : 'border border-brand-border text-brand-text-secondary'}`}>{key.replace(/_/g, ' ')}</button>)}
        </div>
        {trafficCalibration && <div className="p-3 rounded-lg border border-brand-border bg-brand-bg text-caption text-brand-text-secondary">
          <strong className="text-brand-text-primary">Traffic calibration:</strong>{' '}
          {trafficCalibration.note || (trafficCalibration.demand_min_mbps !== undefined
            ? `${trafficCalibration.demand_min_mbps.toFixed(1)}–${trafficCalibration.demand_max_mbps?.toFixed(1)} Mbps per generated flow, based on ${trafficCalibration.basis?.replace(/_/g, ' ')}; mean lifetime ${trafficCalibration.mean_duration_steps?.toFixed(1)} steps; target backbone intensity ${(100 * (trafficCalibration.target_backbone_intensity ?? 0)).toFixed(1)}%, achieved ${(100 * (trafficCalibration.achievable_backbone_intensity ?? 0)).toFixed(1)}%.`
            : `Generated flow mode: ${trafficCalibration.basis?.replace(/_/g, ' ') || 'unspecified'}.`)}
        </div>}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-caption">
            <thead><tr className="border-b border-brand-border"><th className="p-3">Policy</th><th className="p-3">Mean packet loss</th><th className="p-3">Mean latency</th><th className="p-3">P95 latency</th><th className="p-3">Mean delivered flow rate</th><th className="p-3">Backbone steps &gt;0.9</th><th className="p-3">Access steps &gt;0.9</th></tr></thead>
            <tbody>{rows.map(({ key, label, metric }) => <tr key={key} className="border-b border-brand-border last:border-0"><td className="p-3 font-semibold">{label}</td><td className="p-3">{format(metric?.mean_packet_loss !== undefined ? metric.mean_packet_loss * 100 : undefined)}%</td><td className="p-3">{format(metric?.mean_path_latency_ms, 2)} ms</td><td className="p-3">{format(metric?.p95_path_latency_ms, 2)} ms</td><td className="p-3">{format(metric?.delivered_throughput_mbps, 2)} Mbps</td><td className="p-3">{format(metric?.fraction_steps_over_0_9 !== undefined ? metric.fraction_steps_over_0_9 * 100 : undefined, 2)}%</td><td className="p-3">{format(metric?.fraction_steps_access_over_0_9 !== undefined ? metric.fraction_steps_access_over_0_9 * 100 : undefined, 2)}%</td></tr>)}</tbody>
          </table>
        </div>
        {Object.keys(metrics).length === 0 && <p className="text-caption text-brand-text-muted">The saved run does not include metrics for this scenario.</p>}
      </section>

      <section className="bg-brand-surface border border-brand-border rounded-xl p-4 space-y-4">
        <div>
          <h2 className="font-semibold text-brand-text-primary">What the AI did</h2>
          <p className="text-caption text-brand-text-secondary mt-1">
            The trace records the candidate paths and their Q-values, the path actually executed, and whether the safety fallback replaced the model choice. Q-values rank candidates; they are not probabilities.
          </p>
        </div>
        {aiMetric ? (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-caption">
              <div className="p-3 bg-brand-bg rounded-lg"><span className="text-brand-text-muted">Recorded decisions</span><p className="font-semibold text-body">{aiTrace.length || 'Unavailable'}</p></div>
              <div className="p-3 bg-brand-bg rounded-lg"><span className="text-brand-text-muted">Fallback decisions</span><p className="font-semibold text-body">{aiTrace.length ? fallbackCount : 'Unavailable'}</p></div>
              <div className="p-3 bg-brand-bg rounded-lg"><span className="text-brand-text-muted">Invalid actions accepted</span><p className="font-semibold text-body">{format(aiMetric.invalid_actions_accepted, 0)}</p></div>
              <div className="p-3 bg-brand-bg rounded-lg"><span className="text-brand-text-muted">Mean decision time</span><p className="font-semibold text-body">{format(aiMetric.mean_decision_time_ms, 3)} ms</p></div>
            </div>
            {aiMetric.fallback_reason_counts && (
              <div className="text-caption text-brand-text-secondary">
                <strong>Fallback reason counts:</strong>{' '}
                {Object.entries(aiMetric.fallback_reason_counts).map(([reason, count]) => `${reason}: ${count}`).join(' · ') || 'none'}
              </div>
            )}
            {aiTrace.length > 0 ? (
              <>
                <div className="max-h-[34rem] overflow-auto border border-brand-border rounded-lg">
                  <table className="w-full min-w-[1050px] text-left text-caption">
                    <thead className="sticky top-0 bg-brand-bg"><tr className="border-b border-brand-border"><th className="p-3">Step</th><th className="p-3">Flow</th><th className="p-3">Candidate paths · Q</th><th className="p-3">Executed path</th><th className="p-3">Outcome</th></tr></thead>
                    <tbody>{aiTrace.slice(0, 100).map((decision) => (
                      <tr key={`${decision.step}-${decision.flow_id}`} className="border-b border-brand-border last:border-0 align-top">
                        <td className="p-3 font-mono">{decision.step}{decision.measured ? '' : ' (warm-up)'}</td>
                        <td className="p-3">{decision.source} → {decision.destination}<div className="text-brand-text-muted">{decision.flow_id}</div></td>
                        <td className="p-3 space-y-1">{decision.candidate_paths.map((path, index) => (
                          <div key={index} className={decision.chosen_candidate_index === index ? 'font-semibold text-brand-primary' : 'text-brand-text-secondary'}>
                            C{index}{decision.chosen_candidate_index === index ? ' ✓' : ''}: {path.join(' → ')} <span className="font-mono">Q={format(decision.q_values[index] ?? undefined, 3)}</span>
                          </div>
                        ))}</td>
                        <td className="p-3">{decision.chosen_path?.length ? decision.chosen_path.join(' → ') : 'No route'}{decision.fallback_used && <div className="mt-1 text-amber-700">Fallback: {decision.fallback_reason}</div>}</td>
                        <td className="p-3">{decision.path_loss === null ? '—' : `${format(decision.path_loss * 100, 3)}% loss`}<div>{decision.path_latency_ms === null ? '—' : `${format(decision.path_latency_ms, 2)} ms`}</div><div>{decision.step_max_backbone_utilization === null ? '—' : `${format(decision.step_max_backbone_utilization * 100, 1)}% max backbone util.`}</div><div>{decision.step_max_access_utilization == null ? 'Access utilization unavailable' : `${format(decision.step_max_access_utilization * 100, 1)}% max access util.`}</div></td>
                      </tr>
                    ))}</tbody>
                  </table>
                </div>
                {aiTrace.length > 100 && <p className="text-caption text-brand-text-muted">Showing the first 100 of {aiTrace.length} recorded decisions. Use Export JSON for the complete trace.</p>}
              </>
            ) : (
              <p className="text-caption text-brand-text-muted">This saved run predates decision-trace recording; it has aggregate AI metrics only.</p>
            )}
          </>
        ) : <p className="text-caption text-brand-text-muted">No AI metrics were saved for this scenario.</p>}
      </section>

      <div className="flex flex-wrap gap-3 text-caption">
        <button onClick={() => navigate(`/results/${run.id}/heatmap`)} className="px-3 py-2 border border-brand-border rounded-lg">Open utilization view</button>
        <button onClick={() => navigate(`/results/${run.id}/explain`)} className="px-3 py-2 border border-brand-border rounded-lg">Open model diagnostics</button>
        <button onClick={() => navigate(`/results/${run.id}/failure`)} className="px-3 py-2 border border-brand-border rounded-lg">Open failure view</button>
      </div>
    </div>
  );
};
