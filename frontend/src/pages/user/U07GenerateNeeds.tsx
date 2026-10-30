import React, { useEffect, useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { api } from '../../api/client';
import { Plan } from '../../types/plan';
import { NodeType } from '../../types/network';
import { CISCO_HARDWARE_CATALOG } from '../../mock/ciscoHardware';
import { DepartmentSpec, generateTopology, Redundancy } from '../../utils/topologyGenerator';
import { PageHeader } from '../../components/common/PageHeader';
import { AlertTriangle, Network, Sparkles, Plus, Trash2 } from 'lucide-react';

const makeDepartment = (index: number): DepartmentSpec => ({
  name: 'Department ' + (index + 1), pc: 8, laptop: 0, ip_phone: 0,
  printer: 0, tablet: 0, smartphone: 0, iot: 0,
});
const endpointFields: Array<{ key: keyof Omit<DepartmentSpec, 'name'>; label: string }> = [
  { key: 'pc', label: 'PCs' }, { key: 'laptop', label: 'Laptops' },
  { key: 'ip_phone', label: 'IP phones' }, { key: 'printer', label: 'Printers' },
  { key: 'tablet', label: 'Tablets' }, { key: 'smartphone', label: 'Phones' },
  { key: 'iot', label: 'IoT devices' },
];
const inputClass = 'mt-1 w-full px-3 py-2 bg-brand-bg border border-brand-border rounded-lg';

export const U07GenerateNeeds: React.FC = () => {
  const { navigate, currentPath } = useViewport();
  const planId = currentPath.split('/')[2] || '';
  const [name, setName] = useState('Generated Network');
  const [description, setDescription] = useState('');
  const [departments, setDepartments] = useState<DepartmentSpec[]>(Array.from({ length: 4 }, (_, index) => makeDepartment(index)));
  const [routerCount, setRouterCount] = useState(6);
  const [routerModel, setRouterModel] = useState<NodeType>('cisco_2911');
  const [servers, setServers] = useState(2);
  const [backboneBandwidthMbps, setBackboneBandwidthMbps] = useState(1000);
  const [accessBandwidthMbps, setAccessBandwidthMbps] = useState(100);
  const [trafficPreset, setTrafficPreset] = useState<'latency_focused' | 'light' | 'medium' | 'heavy'>('medium');
  const [redundancy, setRedundancy] = useState<Redundancy>('backup');
  const [busy, setBusy] = useState(false);
  const [loadingPlan, setLoadingPlan] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!planId) {
      setError('Draft plan identifier is missing. Start from New Plan so the generated topology is saved to that draft.');
      setLoadingPlan(false);
      return;
    }
    api.get<Plan>('/records/' + encodeURIComponent(planId))
      .then((plan) => {
        setName(plan.name);
        setDescription(plan.description || '');
        if (plan.trafficPreset === 'latency_focused' || plan.trafficPreset === 'light' || plan.trafficPreset === 'medium' || plan.trafficPreset === 'heavy') setTrafficPreset(plan.trafficPreset);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load the draft plan.'))
      .finally(() => setLoadingPlan(false));
  }, [planId]);

  const resizeDepartments = (count: number) => {
    const nextCount = Math.max(1, Math.min(20, Math.floor(count) || 1));
    setDepartments((current) => Array.from({ length: nextCount }, (_, index) => current[index] || makeDepartment(index)));
  };
  const updateDepartment = (index: number, patch: Partial<DepartmentSpec>) => {
    setDepartments((current) => current.map((department, row) => row === index ? { ...department, ...patch } : department));
  };
  const totalEndpointCount = departments.reduce((sum, department) =>
    sum + endpointFields.reduce((subtotal, field) => subtotal + Number(department[field.key] || 0), 0), 0) + servers;

  const createPlan = async () => {
    setBusy(true);
    setError(null);
    try {
      if (!planId) throw new Error('Draft plan identifier is missing.');
      const topology = generateTopology({
        name: name.trim() || 'Generated Network', routerCount, routerModel, departments, servers,
        redundancy, backboneBandwidthMbps, accessBandwidthMbps,
      });
      const plan = await api.patch<Plan>('/records/' + encodeURIComponent(planId), {
        name: name.trim() || 'Generated Network',
        description: description || 'Generated topology with ' + departments.length + ' departments. Edit the saved graph before submission.',
        topology: { ...topology, id: planId }, traffic_preset: trafficPreset,
      });
      navigate('/plans/' + encodeURIComponent(plan.id) + '/edit/canvas');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the generated draft.');
    } finally { setBusy(false); }
  };

  const routerModels = CISCO_HARDWARE_CATALOG.filter((item) => item.category === 'routers');
  return <div className="p-6 max-w-5xl mx-auto space-y-6">
    <PageHeader title="Topology Generator" subtitle="Choose departments, device mix, Cisco models, redundancy, and link capacity for one editable network." />
    {error && <div role="alert" className="p-3 rounded-lg border border-rose-300 bg-rose-50 text-rose-800 text-caption">{error}</div>}
    <section className="bg-brand-surface border border-brand-border rounded-xl p-5 space-y-5">
      <label className="block text-caption font-semibold">Plan name<input value={name} onChange={(event) => setName(event.target.value)} className={inputClass} /></label>
      <label className="block text-caption font-semibold">Description<textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={2} className={inputClass} placeholder="Optional purpose or network notes" /></label>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <label className="block text-caption font-semibold">Number of departments<input type="number" min={1} max={20} value={departments.length} onChange={(event) => resizeDepartments(Number(event.target.value))} className={inputClass} /></label>
        <label className="block text-caption font-semibold">Router count (5-50)<input type="number" min={5} max={50} value={routerCount} onChange={(event) => setRouterCount(Math.max(5, Math.min(50, Number(event.target.value) || 5)))} className={inputClass} /></label>
        <label className="block text-caption font-semibold">Router model<select value={routerModel} onChange={(event) => setRouterModel(event.target.value as NodeType)} className={inputClass}>{routerModels.map((model) => <option key={model.type} value={model.type}>{model.name}</option>)}</select></label>
        <label className="block text-caption font-semibold">Shared application servers<input type="number" min={0} max={50} value={servers} onChange={(event) => setServers(Math.max(0, Math.min(50, Number(event.target.value) || 0)))} className={inputClass} /></label>
        <label className="block text-caption font-semibold">Backbone capacity (Mbps)<input type="number" min={1} value={backboneBandwidthMbps} onChange={(event) => setBackboneBandwidthMbps(Math.max(1, Number(event.target.value) || 1))} className={inputClass} /></label>
        <label className="block text-caption font-semibold">Access capacity (Mbps)<input type="number" min={1} value={accessBandwidthMbps} onChange={(event) => setAccessBandwidthMbps(Math.max(1, Number(event.target.value) || 1))} className={inputClass} /></label>
        <label className="block text-caption font-semibold">Traffic preset<select value={trafficPreset} onChange={(event) => setTrafficPreset(event.target.value as typeof trafficPreset)} className={inputClass}><option value="latency_focused">Low latency (0.025 intensity)</option><option value="light">Light (0.05)</option><option value="medium">Medium (0.10)</option><option value="heavy">Heavy (0.20)</option></select><span className="mt-1 block text-xs font-normal text-brand-text-muted">Lower intensity reduces offered traffic; it does not change the AI model.</span></label>
        <label className="block text-caption font-semibold">Backbone layout<select value={redundancy} onChange={(event) => setRedundancy(event.target.value as Redundancy)} className={inputClass}><option value="none">Star</option><option value="backup">Ring with backup links</option><option value="full">Full mesh</option></select></label>
      </div>

      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div><h2 className="font-bold text-body text-brand-text-primary">Department device mix</h2><p className="text-caption text-brand-text-muted">Set a name and count for each device type. Up to 20 departments and 500 endpoints.</p></div>
          <button type="button" onClick={() => resizeDepartments(departments.length + 1)} disabled={departments.length >= 20} className="px-3 py-2 rounded-lg border border-brand-border text-caption font-semibold disabled:opacity-50"><Plus className="inline w-4 h-4 mr-1" />Add department</button>
        </div>
        {departments.map((department, index) => <section key={index} className="rounded-xl border border-brand-border p-4 space-y-3">
          <div className="flex items-center gap-2">
            <label className="flex-1 text-caption font-semibold">Department {index + 1} name<input value={department.name} onChange={(event) => updateDepartment(index, { name: event.target.value })} className={inputClass} /></label>
            <button type="button" onClick={() => resizeDepartments(departments.length - 1)} disabled={departments.length <= 1} aria-label={'Remove department ' + (index + 1)} className="mt-5 p-2 rounded-lg border border-rose-200 text-rose-600 disabled:opacity-40"><Trash2 className="w-4 h-4" /></button>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
            {endpointFields.map((field) => <label key={field.key} className="text-xs font-semibold text-brand-text-secondary">{field.label}<input type="number" min={0} max={100} value={department[field.key]} onChange={(event) => updateDepartment(index, { [field.key]: Math.max(0, Math.min(100, Number(event.target.value) || 0)) })} className={inputClass} /></label>)}
          </div>
        </section>)}
      </div>

      <div className="p-3 rounded-lg bg-brand-bg border border-brand-border text-caption text-brand-text-secondary flex gap-2"><Network className="w-4 h-4 shrink-0 text-brand-primary" /><span>Generation replaces the topology in the existing draft and creates one editable graph. Department devices attach to routers; servers attach to the backbone. Manual flows are preserved, so review their endpoints if you change the device mix. The trained model runs during an approved simulation.</span></div>
      <div className="flex flex-wrap justify-between items-center gap-3 border-t border-brand-border pt-4">
        <span className="text-caption text-brand-text-muted">{routerCount} routers · {departments.length} departments · {totalEndpointCount} endpoint devices · {redundancy === 'full' ? 'full mesh' : redundancy === 'backup' ? 'redundant ring' : 'star'}</span>
        <button onClick={() => void createPlan()} disabled={busy || loadingPlan || !planId} className="px-4 py-2 rounded-lg bg-brand-primary text-white text-btn font-semibold disabled:opacity-50"><Sparkles className="inline w-4 h-4 mr-2" />{loadingPlan ? 'Loading draft…' : busy ? 'Saving topology…' : 'Generate topology'}</button>
      </div>
    </section>
    <div className="p-3 rounded-lg border border-amber-300 bg-amber-50 text-amber-900 text-caption flex gap-2"><AlertTriangle className="w-4 h-4 shrink-0" /><span>Simulation requires 5-50 connected infrastructure devices and at least two endpoint devices. Ensure every endpoint has an access link before submission.</span></div>
  </div>;
};
