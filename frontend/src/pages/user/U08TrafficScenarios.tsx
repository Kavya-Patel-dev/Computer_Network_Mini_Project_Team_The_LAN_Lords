import React, { useEffect, useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { api } from '../../api/client';
import { PageHeader } from '../../components/common/PageHeader';
import { NetworkNode, ScenarioType, TrafficClass, TrafficFlow, isHostNode } from '../../types/network';
import { 
  Zap, 
  Activity, 
  Scissors, 
  PowerOff, 
  TrendingUp, 
  Gauge, 
  HelpCircle, 
  ArrowRight, 
  Plus, 
  Trash2, 
  Check 
} from 'lucide-react';

export const U08TrafficScenarios: React.FC = () => {
  const { navigate, currentPath } = useViewport();
  const planId = currentPath.split('/')[2] || '';

  const [trafficMode, setTrafficMode] = useState<'preset' | 'manual'>('preset');
  const [selectedPreset, setSelectedPreset] = useState<'latency_focused' | 'light' | 'medium' | 'heavy'>('medium');

  // Multi-select Scenarios
  const [selectedScenarios, setSelectedScenarios] = useState<ScenarioType[]>(['normal']);
  const [hostNodes, setHostNodes] = useState<NetworkNode[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Manual flows table
  const [flows, setFlows] = useState<TrafficFlow[]>([]);
  const [flowSource, setFlowSource] = useState('');
  const [flowDestination, setFlowDestination] = useState('');
  const [flowDemand, setFlowDemand] = useState(10);
  const [flowClass, setFlowClass] = useState<TrafficClass>('bulk');

  useEffect(() => {
    if (!planId) return;
    api.get<{ topology: { nodes?: NetworkNode[] }; trafficPreset: string; flows: TrafficFlow[]; selectedScenarios: ScenarioType[] }>(`/records/${encodeURIComponent(planId)}`)
      .then((plan) => {
        const nodes = plan.topology.nodes || [];
        const hosts = nodes.filter((node) => isHostNode(node.type, node.simulationRole));
        setHostNodes(hosts);
        setFlowSource(hosts[0]?.id || '');
        setFlowDestination(hosts[1]?.id || hosts[0]?.id || '');
        setFlows(plan.flows || []);
        setSelectedScenarios(plan.selectedScenarios || ['normal']);
        if (['latency_focused', 'light', 'medium', 'heavy'].includes(plan.trafficPreset)) {
          setSelectedPreset(plan.trafficPreset as 'latency_focused' | 'light' | 'medium' | 'heavy');
          setTrafficMode('preset');
        } else {
          setTrafficMode('manual');
        }
      })
      .catch((error) => setLoadError(error instanceof Error ? error.message : 'Could not load this plan.'));
  }, [planId]);

  const addManualFlow = () => {
    if (!flowSource || !flowDestination || flowSource === flowDestination || flowDemand <= 0) return;
    setFlows((previous) => [...previous, { id: crypto.randomUUID(), src: flowSource, dst: flowDestination, demand_mbps: flowDemand, class: flowClass }]);
  };

  const continueToReview = async () => {
    if (!planId) return;
    setSaving(true);
    setSaveError(null);
    try {
      await api.patch(`/records/${encodeURIComponent(planId)}`, {
        traffic_preset: trafficMode === 'manual' ? 'manual' : selectedPreset,
        flows,
        selected_scenarios: selectedScenarios,
      });
      navigate(`/plans/${planId}/edit/review`);
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'Could not save traffic settings.');
    } finally {
      setSaving(false);
    }
  };

  const toggleScenario = (sc: ScenarioType) => {
    setSelectedScenarios((prev) =>
      prev.includes(sc) ? prev.filter((s) => s !== sc) : [...prev, sc]
    );
  };

  const scenariosList = [
    {
      id: 'normal' as ScenarioType,
      title: 'Normal Operation',
      icon: <Activity className="w-6 h-6 text-emerald-500" />,
      desc: 'Nominal traffic flows with standard link delay and queue buffer dynamics.',
    },
    {
      id: 'link_failure' as ScenarioType,
      title: 'Link Cut Failure',
      icon: <Scissors className="w-6 h-6 text-rose-500" />,
      desc: 'Drop core link L-R3-R5 at step 40; measures rerouting latency and packet loss.',
    },
    {
      id: 'router_failure' as ScenarioType,
      title: 'Router Hardware Failure',
      icon: <PowerOff className="w-6 h-6 text-amber-500" />,
      desc: 'Complete power loss of distribution router R3; tests heuristic fallback stability.',
    },
    {
      id: 'traffic_spike' as ScenarioType,
      title: '4x Traffic Spike Surge',
      icon: <TrendingUp className="w-6 h-6 text-purple-500" />,
      desc: 'Instantaneous 400% surge across host workstations for 15 seconds.',
    },
    {
      id: 'bandwidth_drop' as ScenarioType,
      title: '50% Bandwidth Degradation',
      icon: <Gauge className="w-6 h-6 text-blue-500" />,
      desc: 'Core trunks degrade by half, forcing dynamic load-balancing adjustments.',
    },
  ];

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-8">
      {/* Page Header */}
      <div>
        <PageHeader
          title="Traffic & Evaluation Scenarios"
          subtitle="Configure flow demands and stress scenarios for the routing simulation."
        />
      {(loadError || saveError) && <div role="alert" className="p-3 rounded-lg border border-rose-300 bg-rose-50 text-rose-800 text-caption">{loadError || saveError}</div>}

        {/* Stepper */}
        <div className="flex items-center justify-between max-w-md mx-auto my-6 text-caption">
          <div className="flex items-center gap-2 text-emerald-600 font-medium">
            <span className="w-6 h-6 rounded-full bg-emerald-100 text-emerald-800 flex items-center justify-center text-xs">✓</span>
            <span>Network Design</span>
          </div>
          <div className="h-0.5 w-12 bg-emerald-500" />
          <div className="flex items-center gap-2 text-brand-primary font-bold">
            <span className="w-6 h-6 rounded-full bg-brand-primary text-white flex items-center justify-center text-xs">2</span>
            <span>Traffic & Scenarios</span>
          </div>
          <div className="h-0.5 w-12 bg-brand-border" />
          <div className="flex items-center gap-2 text-brand-text-muted font-medium">
            <span className="w-6 h-6 rounded-full bg-brand-surface border border-brand-border flex items-center justify-center text-xs">3</span>
            <span>Review & Submit</span>
          </div>
        </div>
      </div>

      {/* Part 1: Traffic Profile */}
      <div className="bg-brand-surface border border-brand-border rounded-xl p-6 space-y-6 shadow-sm">
        <div className="flex items-center justify-between pb-3 border-b border-brand-border">
          <div>
            <h3 className="text-h3 font-bold text-brand-text-primary">1. Synthetic Traffic Profile</h3>
            <p className="text-caption text-brand-text-secondary mt-0.5">
              Specify Poisson traffic arrival rates or manual peer-to-peer flows.
            </p>
          </div>

          {/* Toggle Preset vs Manual */}
          <div className="inline-flex p-1 bg-brand-bg border border-brand-border rounded-lg text-caption">
            <button
              onClick={() => setTrafficMode('preset')}
              className={`px-3 py-1 font-semibold rounded ${
                trafficMode === 'preset'
                  ? 'bg-brand-surface text-brand-primary shadow-sm'
                  : 'text-brand-text-muted hover:text-brand-text-primary'
              }`}
            >
              Preset Intensity
            </button>
            <button
              onClick={() => setTrafficMode('manual')}
              className={`px-3 py-1 font-semibold rounded ${
                trafficMode === 'manual'
                  ? 'bg-brand-surface text-brand-primary shadow-sm'
                  : 'text-brand-text-muted hover:text-brand-text-primary'
              }`}
            >
              Manual QoS Flows
            </button>
          </div>
        </div>

        {trafficMode === 'preset' ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            {[
              {
                id: 'latency_focused' as const,
                title: 'Low latency (0.025 intensity)',
                desc: 'Very light offered load to reduce queue buildup. Compare policies with the same topology, scenario, and seed.',
              },
              {
                id: 'light' as const,
                title: 'Light (0.05 Intensity)',
                desc: 'Minimal buffer occupancy; baseline latency validation.',
              },
              {
                id: 'medium' as const,
                title: 'Medium (0.10 Intensity)',
                desc: 'Balanced load creating moderate bottleneck links (Standard benchmark).',
              },
              {
                id: 'heavy' as const,
                title: 'Heavy (0.20 Intensity)',
                desc: 'High queue saturation; tests congestion mitigation and packet drop.',
              },
            ].map((p) => (
              <div
                key={p.id}
                onClick={() => setSelectedPreset(p.id)}
                className={`p-4 rounded-xl border-2 cursor-pointer transition-all ${
                  selectedPreset === p.id
                    ? 'border-brand-primary bg-brand-primary/5 shadow-sm'
                    : 'border-brand-border bg-brand-bg hover:border-brand-primary/40'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-body font-bold text-brand-text-primary">{p.title}</h4>
                  {selectedPreset === p.id && (
                    <Check className="w-4 h-4 text-brand-primary" />
                  )}
                </div>
                <p className="text-caption text-brand-text-secondary">{p.desc}</p>
              </div>
            ))}
          </div>
        ) : (
          /* Manual Flows Table */
          <div className="space-y-3">
            <div className="overflow-x-auto bg-brand-bg border border-brand-border rounded-lg">
              <table className="w-full text-left text-body border-collapse">
                <thead>
                  <tr className="border-b border-brand-border bg-brand-surface">
                    <th className="py-2.5 px-3 text-overline text-brand-text-muted">Source</th>
                    <th className="py-2.5 px-3 text-overline text-brand-text-muted">Destination</th>
                    <th className="py-2.5 px-3 text-overline text-brand-text-muted">Demand</th>
                    <th className="py-2.5 px-3 text-overline text-brand-text-muted">Traffic Class</th>
                    <th className="py-2.5 px-3 text-overline text-brand-text-muted text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-brand-border">
                  {flows.length === 0 && <tr><td colSpan={5} className="p-4 text-center text-caption text-brand-text-muted">No manual flows added yet.</td></tr>}
                  {flows.map((flow) => (
                    <tr key={flow.id}>
                      <td className="py-2 px-3 font-mono font-bold">{flow.src}</td>
                      <td className="py-2 px-3 font-mono font-bold">{flow.dst}</td>
                      <td className="py-2 px-3 font-mono">{flow.demand_mbps} Mbps</td>
                      <td className="py-2 px-3">
                        <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-brand-surface border border-brand-border">
                          {flow.class === 'real_time' && 'Video Call (Real-time)'}
                          {flow.class === 'streaming' && 'Streaming Media'}
                          {flow.class === 'bulk' && 'File Download (Bulk)'}
                          {flow.class === 'background' && 'Backup (Background)'}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-right">
                        <button
                          onClick={() => setFlows(flows.filter((f) => f.id !== flow.id))}
                          className="p-1 text-brand-text-muted hover:text-rose-600 rounded"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2 items-end">
              <label className="text-caption text-brand-text-secondary">Source<select value={flowSource} onChange={(e) => setFlowSource(e.target.value)} className="block w-full mt-1 p-2 rounded border border-brand-border bg-brand-bg">{hostNodes.map((n) => <option key={n.id} value={n.id}>{n.label || n.id}</option>)}</select></label>
              <label className="text-caption text-brand-text-secondary">Destination<select value={flowDestination} onChange={(e) => setFlowDestination(e.target.value)} className="block w-full mt-1 p-2 rounded border border-brand-border bg-brand-bg">{hostNodes.map((n) => <option key={n.id} value={n.id}>{n.label || n.id}</option>)}</select></label>
              <label className="text-caption text-brand-text-secondary">Demand (Mbps)<input type="number" min="0.01" step="0.01" value={flowDemand} onChange={(e) => setFlowDemand(Number(e.target.value))} className="block w-full mt-1 p-2 rounded border border-brand-border bg-brand-bg" /></label>
              <label className="text-caption text-brand-text-secondary">Class<select value={flowClass} onChange={(e) => setFlowClass(e.target.value as TrafficClass)} className="block w-full mt-1 p-2 rounded border border-brand-border bg-brand-bg"><option value="real_time">Real time</option><option value="streaming">Streaming</option><option value="bulk">Bulk</option><option value="background">Background</option></select></label>
              <button type="button" onClick={addManualFlow} disabled={hostNodes.length < 2 || flowSource === flowDestination} className="p-2 rounded bg-brand-primary text-white text-caption font-semibold disabled:opacity-50">Add flow</button>
            </div>
            <p className="text-[11px] text-brand-text-muted">
              ℹ️ Real-time video traffic has tight jitter tolerances and is most sensitive to queuing delay.
            </p>
          </div>
        )}
      </div>

      {/* Part 2: Scenarios Selection */}
      <div className="bg-brand-surface border border-brand-border rounded-xl p-6 space-y-4 shadow-sm">
        <div className="flex items-center justify-between pb-3 border-b border-brand-border">
          <div>
            <h3 className="text-h3 font-bold text-brand-text-primary">2. Simulation Scenarios</h3>
            <p className="text-caption text-brand-text-secondary mt-0.5">
              Select which conditions will be tested against Static Dijkstra, Load-aware Dijkstra, and the AI agent.
            </p>
          </div>
          <span className="text-caption font-mono text-brand-text-muted">
            {selectedScenarios.length} of 5 Active
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {scenariosList.map((sc) => {
            const isChecked = selectedScenarios.includes(sc.id);
            return (
              <div
                key={sc.id}
                onClick={() => toggleScenario(sc.id)}
                className={`p-4 rounded-xl border-2 cursor-pointer transition-all flex items-start gap-3.5 ${
                  isChecked
                    ? 'border-brand-primary bg-brand-bg shadow-sm'
                    : 'border-brand-border bg-brand-surface opacity-60 hover:opacity-100'
                }`}
              >
                <div className="p-2 rounded-lg bg-brand-surface border border-brand-border shrink-0">
                  {sc.icon}
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <h4 className="text-body font-bold text-brand-text-primary">{sc.title}</h4>
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => toggleScenario(sc.id)}
                      className="rounded text-brand-primary"
                    />
                  </div>
                  <p className="text-caption text-brand-text-secondary mt-1">{sc.desc}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Navigation Buttons */}
      <div className="flex justify-between items-center pt-4 border-t border-brand-border">
        <button
          onClick={() => navigate(`/plans/${planId}/edit/canvas`)}
          className="px-4 py-2 rounded-lg border border-brand-border text-brand-text-secondary text-btn font-semibold hover:bg-brand-bg"
        >
          Back: Network Design
        </button>

        <button
          onClick={() => void continueToReview()}
          disabled={saving || selectedScenarios.length === 0 || (trafficMode === 'manual' && flows.length === 0)}
          className="px-6 py-2.5 rounded-lg bg-brand-primary text-white text-btn font-semibold hover:opacity-90 flex items-center gap-2 shadow-sm touch-target"
        >
          <span>{saving ? 'Saving…' : 'Next: Review & Submit'}</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
