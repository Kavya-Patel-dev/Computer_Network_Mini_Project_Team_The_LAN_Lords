import React, { useEffect, useMemo, useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { api } from '../../api/client';
import { Plan } from '../../types/plan';
import { isHostNode, isRoutingNode } from '../../types/network';
import { PageHeader } from '../../components/common/PageHeader';
import { AlertTriangle, CheckCircle2, FileText } from 'lucide-react';

type Metric = {
  mean_packet_loss?: number;
  mean_path_latency_ms?: number;
  p95_path_latency_ms?: number;
  delivered_throughput_mbps?: number;
  fraction_steps_over_0_9?: number;
  fraction_steps_access_over_0_9?: number;
  mean_max_backbone_utilization?: number;
  decision_trace?: { step: number; source: string; destination: string; candidate_paths: string[][]; q_values: (number | null)[]; chosen_path: string[] | null; fallback_used: boolean; fallback_reason: string; step_max_access_utilization?: number | null }[];
  fallback_reason_counts?: Record<string, number>;
  invalid_actions_accepted?: number;
};
type TrafficCalibration = {
  basis?: string;
  demand_min_mbps?: number;
  demand_max_mbps?: number;
  mean_duration_steps?: number;
  target_backbone_intensity?: number;
  achievable_backbone_intensity?: number;
  note?: string;
};
type SavedRun = {
  id: string;
  runId: string;
  planId: string;
  date: string;
  scenarios: Record<string, { metrics?: Record<string, Metric>; traffic_calibration?: TrafficCalibration }>;
  verdictText: string;
};

const ROUTER_MIN = 5;
const ROUTER_MAX = 50;
const fmt = (value: number | undefined, digits = 2) => typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '—';
const lossPct = (value: number | undefined) => typeof value === 'number' && Number.isFinite(value) ? `${(value * 100).toFixed(3)}%` : '—';

export const U11AnalysisReport: React.FC = () => {
  const { navigate, currentPath } = useViewport();
  const planId = currentPath.split('/')[2] || '';
  const [plan, setPlan] = useState<Plan | null>(null);
  const [latestRun, setLatestRun] = useState<SavedRun | null>(null);
  const [scenario, setScenario] = useState('normal');
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!planId) return;
    Promise.all([
      api.get<Plan>(`/records/${encodeURIComponent(planId)}`),
      api.get<{ items: SavedRun[] }>(`/results?plan_id=${encodeURIComponent(planId)}&limit=100`),
    ]).then(([savedPlan, resultPage]) => {
      setPlan(savedPlan);
      const planRuns = resultPage.items.filter((run) => run.planId === savedPlan.id);
      setLatestRun(planRuns[0] || null);
      setScenario(Object.keys(planRuns[0]?.scenarios || {})[0] || 'normal');
      setError(null);
    }).catch((err) => setError(err instanceof Error ? err.message : 'Could not load the saved analysis.'));
  }, [planId]);

  const inventory = useMemo(() => {
    if (!plan) return null;
    const nodes = plan.topology.nodes || [];
    const links = (plan.topology.links || []).filter((link) => link.simulationIncluded !== false);
    const ids = new Set(nodes.map((node) => node.id));
    const adjacency = new Map(nodes.map((node) => [node.id, new Set<string>()]));
    const dangling = links.filter((link) => !ids.has(link.src) || !ids.has(link.dst));
    for (const link of links) if (ids.has(link.src) && ids.has(link.dst)) {
      adjacency.get(link.src)?.add(link.dst);
      adjacency.get(link.dst)?.add(link.src);
    }
    const routers = nodes.filter((node) => isRoutingNode(node.type, node.simulationRole));
    const hosts = nodes.filter((node) => isHostNode(node.type, node.simulationRole));
    const routerIds = new Set(routers.map((node) => node.id));
    const seen = new Set<string>();
    if (nodes.length) {
      const pending = [nodes[0].id];
      while (pending.length) {
        const id = pending.shift()!;
        if (seen.has(id)) continue;
        seen.add(id);
        pending.push(...(adjacency.get(id) || []));
      }
    }
    const invalidLinks = links.filter((link) => !(link.bandwidth_mbps > 0) || !(link.latency_ms > 0) || (link.loss_percent ?? 0) < 0 || (link.loss_percent ?? 0) > 100);
    const degreeSum = routers.reduce((sum, node) => sum + (adjacency.get(node.id)?.size || 0), 0);
    const capacities = links.map((link) => link.bandwidth_mbps).filter((value) => Number.isFinite(value) && value > 0);
    const backboneLinks = links.filter((link) => routerIds.has(link.src) && routerIds.has(link.dst));
    const leafHosts = hosts.filter((node) => (adjacency.get(node.id)?.size || 0) <= 1).length;
    return {
      nodes, links, routers, hosts, dangling, invalidLinks,
      connected: nodes.length > 0 && seen.size === nodes.length,
      leafHosts,
      routerAverageDegree: routers.length ? degreeSum / routers.length : 0,
      maxCapacity: capacities.length ? Math.max(...capacities) : null,
      backboneLinks,
    };
  }, [plan]);

  if (error) return <div role="alert" className="p-6 text-rose-700">{error}</div>;
  if (!plan || !inventory) return <div className="p-6 text-brand-text-muted">Loading saved topology and simulation report…</div>;

  const checks: [string, boolean][] = [
    ['All links reference existing nodes', inventory.dangling.length === 0],
    ['Topology is connected', inventory.connected],
    ['Link values are in supported ranges', inventory.invalidLinks.length === 0],
    [`Router count is ${ROUTER_MIN}–${ROUTER_MAX}`, inventory.routers.length >= ROUTER_MIN && inventory.routers.length <= ROUTER_MAX],
    ['Every endpoint device is a leaf', inventory.leafHosts === inventory.hosts.length],
    ['At least one router-to-router backbone link exists', inventory.backboneLinks.length > 0],
  ];
  const runScenarios = latestRun?.scenarios || {};
  const metrics = runScenarios[scenario]?.metrics || {};
  const trafficCalibration = runScenarios[scenario]?.traffic_calibration;
  const ai = metrics.ai;
  const trace = ai?.decision_trace || [];
  const fallbackCount = trace.filter((row) => row.fallback_used).length;
  const scenarioKeys = Object.keys(runScenarios);
  const canEdit = plan.status === 'Draft' || plan.status === 'Changes Requested';

  return <div className="space-y-6 p-6">
    <PageHeader
      title={`Analysis Report: ${plan.name}`}
      subtitle="Topology checks are computed from the saved design. AI metrics and route decisions appear after a successful simulation."
      actions={canEdit ? <button onClick={() => navigate(`/plans/${plan.id}/edit/canvas`)} className="px-3 py-2 bg-brand-primary rounded-lg text-white text-caption">Fix topology</button> : plan.status === 'Approved' ? <button onClick={() => navigate(`/plans/${plan.id}/run`)} className="px-3 py-2 bg-emerald-600 rounded-lg text-white text-caption">Run simulation</button> : undefined}
    />

    <section className="grid grid-cols-2 md:grid-cols-4 gap-3">{[
      ['Routers', inventory.routers.length], ['Endpoint devices', inventory.hosts.length], ['Links', inventory.links.length], ['Router to router links', inventory.backboneLinks.length],
    ].map(([label, value]) => <div key={label} className="p-4 bg-brand-surface border border-brand-border rounded-xl"><div className="text-caption text-brand-text-muted">{label}</div><div className="text-h2 font-mono font-bold">{value}</div></div>)}</section>

    <section className="p-5 bg-brand-surface border border-brand-border rounded-xl space-y-3">
      <h2 className="text-h3 font-bold">Topology readiness</h2>
      {checks.map(([label, pass]) => <div key={label} className="flex items-center gap-2 text-caption">{pass ? <CheckCircle2 className="w-4 h-4 text-emerald-600" /> : <AlertTriangle className="w-4 h-4 text-amber-600" />}<span>{label}</span></div>)}
      <p className="text-caption text-brand-text-muted">Router average degree: {inventory.routerAverageDegree.toFixed(2)} · Endpoint leaves: {inventory.leafHosts}/{inventory.hosts.length} · Invalid links: {inventory.invalidLinks.length} · Dangling links: {inventory.dangling.length}</p>
    </section>

    {!latestRun ? (
      <section className="p-5 rounded-xl border border-amber-300 bg-amber-50 text-amber-950 space-y-3">
        <h2 className="font-bold">No AI analysis has been run for this plan yet</h2>
        <p className="text-caption">The trained routing model is called by <strong>Run Simulation</strong>, after a valid topology is submitted and approved. This page will then show measured packet loss, latency, throughput, selected paths, Q scores, and safety-fallback use. No congestion or route prediction is fabricated before a run.</p>
        {plan.status === 'Draft' || plan.status === 'Changes Requested' ? <p className="text-caption">Current status: <strong>{plan.status}</strong>. The model requires a connected network with 5–50 routers. Finish the design, choose traffic and scenarios, then submit it for an administrator to review.</p> : plan.status === 'Pending Review' ? <p className="text-caption">Current status: <strong>Pending Review</strong>. Wait for an administrator to approve this plan.</p> : <p className="text-caption">Current status: <strong>{plan.status}</strong>. Once approved, start the simulation from this page or the Simulation Runs tab.</p>}
        {canEdit && (inventory.routers.length < ROUTER_MIN || inventory.routers.length > ROUTER_MAX) && <button onClick={() => navigate(`/plans/${plan.id}/edit/generate`)} className="px-3 py-2 rounded-lg bg-brand-primary text-white text-caption font-semibold">Generate a valid starter topology in this draft</button>}
        {canEdit && <button onClick={() => navigate(`/plans/${plan.id}/edit/traffic`)} className="ml-2 px-3 py-2 rounded-lg border border-amber-400 text-amber-950 text-caption font-semibold">Configure traffic & scenarios</button>}
        {plan.status === 'Approved' && <button onClick={() => navigate(`/plans/${plan.id}/run`)} className="px-3 py-2 rounded-lg bg-emerald-600 text-white text-caption font-semibold">Run Simulation</button>}
      </section>
    ) : (
      <>
        <section className="p-5 bg-brand-surface border border-brand-border rounded-xl space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-h3 font-bold">Simulation results</h2><p className="text-caption text-brand-text-muted">Latest saved run · {new Date(latestRun.date).toLocaleString()} · {latestRun.verdictText}</p></div><button onClick={() => navigate(`/results/${latestRun.id}`)} className="px-3 py-2 rounded-lg bg-brand-primary text-white text-caption font-semibold flex gap-2 items-center"><FileText className="w-4 h-4" />Full results & AI trace</button></div>
          <div className="flex flex-wrap gap-2">{scenarioKeys.map((key) => <button key={key} onClick={() => setScenario(key)} className={`px-3 py-1 rounded-full text-caption capitalize ${scenario === key ? 'bg-brand-primary text-white' : 'border border-brand-border text-brand-text-secondary'}`}>{key.replace(/_/g, ' ')}</button>)}</div>
          {trafficCalibration && <div className="p-3 rounded-lg border border-brand-border bg-brand-bg text-caption text-brand-text-secondary"><strong className="text-brand-text-primary">Traffic calibration:</strong>{' '}{trafficCalibration.note || (trafficCalibration.demand_min_mbps !== undefined ? `${trafficCalibration.demand_min_mbps.toFixed(1)}–${trafficCalibration.demand_max_mbps?.toFixed(1)} Mbps per generated flow; mean lifetime ${trafficCalibration.mean_duration_steps?.toFixed(1)} steps; target backbone intensity ${(100 * (trafficCalibration.target_backbone_intensity ?? 0)).toFixed(1)}%, achieved ${(100 * (trafficCalibration.achievable_backbone_intensity ?? 0)).toFixed(1)}%.` : `Generated traffic basis: ${trafficCalibration.basis?.replace(/_/g, ' ') || 'unspecified'}.`)}</div>}
          <div className="overflow-x-auto"><table className="w-full text-left text-caption"><thead><tr className="border-b border-brand-border"><th className="p-2">Policy</th><th className="p-2">Packet loss</th><th className="p-2">Mean latency</th><th className="p-2">P95 latency</th><th className="p-2">Mean delivered flow rate</th><th className="p-2">Backbone steps &gt;0.9</th><th className="p-2">Access steps &gt;0.9</th></tr></thead><tbody>{(['static', 'load_aware', 'ai'] as const).map((key) => { const metric = metrics[key]; return <tr key={key} className="border-b border-brand-border last:border-0"><td className="p-2 font-semibold">{{ static: 'Static Dijkstra', load_aware: 'Load-aware Dijkstra', ai: 'Trained AI + fallback' }[key]}</td><td className="p-2">{lossPct(metric?.mean_packet_loss)}</td><td className="p-2">{fmt(metric?.mean_path_latency_ms)} ms</td><td className="p-2">{fmt(metric?.p95_path_latency_ms)} ms</td><td className="p-2">{fmt(metric?.delivered_throughput_mbps)} Mbps</td><td className="p-2">{typeof metric?.fraction_steps_over_0_9 === 'number' ? `${(metric.fraction_steps_over_0_9 * 100).toFixed(2)}%` : '—'}</td><td className="p-2">{typeof metric?.fraction_steps_access_over_0_9 === 'number' ? `${(metric.fraction_steps_access_over_0_9 * 100).toFixed(2)}%` : '—'}</td></tr>; })}</tbody></table></div>
        </section>

        <section className="p-5 bg-brand-surface border border-brand-border rounded-xl space-y-3">
          <div><h2 className="text-h3 font-bold">What the AI did</h2><p className="text-caption text-brand-text-secondary mt-1">The model scores the available candidate routes with Q-values, chooses one, then the safety wrapper may replace unsafe choices. Q-values are ranking scores, not probabilities.</p></div>
          {ai ? <>
            <div className="grid sm:grid-cols-3 gap-3 text-caption"><div className="p-3 bg-brand-bg rounded-lg">Recorded decisions<strong className="block text-body">{trace.length || 'Trace unavailable'}</strong></div><div className="p-3 bg-brand-bg rounded-lg">Fallback decisions<strong className="block text-body">{trace.length ? fallbackCount : '—'}</strong></div><div className="p-3 bg-brand-bg rounded-lg">Invalid actions accepted<strong className="block text-body">{ai.invalid_actions_accepted ?? '—'}</strong></div></div>
            {ai.fallback_reason_counts && <p className="text-caption text-brand-text-secondary">Fallback reasons: {Object.entries(ai.fallback_reason_counts).map(([reason, count]) => `${reason}: ${count}`).join(' · ') || 'none'}</p>}
            {trace.length > 0 && <div className="space-y-2"><h3 className="text-body font-semibold">Example decisions</h3>{trace.slice(0, 5).map((row) => <div key={`${row.step}-${row.source}-${row.destination}`} className="p-3 bg-brand-bg rounded-lg text-caption"><strong>Step {row.step}:</strong> {row.source} → {row.destination}<br /><span className="text-brand-text-secondary">Executed: {row.chosen_path?.join(' → ') || 'no route'}{row.fallback_used ? ` · safety fallback: ${row.fallback_reason}` : ''}</span><div className="text-brand-text-muted mt-1">Candidate routes and Q-scores: {row.candidate_paths.map((path, index) => `${path.join(' → ')} (Q ${fmt(row.q_values[index] ?? undefined, 3)})`).join(' · ')}</div>{row.step_max_access_utilization != null && <div className="text-brand-text-muted">Step max access-link utilization: {fmt(row.step_max_access_utilization * 100, 1)}%</div>}</div>)}</div>}
            {trace.length === 0 && <p className="text-caption text-brand-text-muted">This saved run has aggregate AI metrics but no per-decision trace.</p>}
          </> : <p className="text-caption text-brand-text-muted">No AI metrics were returned for this scenario.</p>}
        </section>
      </>
    )}

    <section className="p-5 bg-brand-surface border border-brand-border rounded-xl space-y-2"><h2 className="text-h3 font-bold">Capacity summary</h2><p className="text-caption text-brand-text-secondary">Maximum configured link capacity: {inventory.maxCapacity ?? '—'} Mbps. Structural checks are not congestion estimates; utilization and performance are measured only in a simulation.</p></section>
  </div>;
};
