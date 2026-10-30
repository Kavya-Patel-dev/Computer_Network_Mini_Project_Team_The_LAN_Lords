import React, { useEffect, useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { api } from '../../api/client';
import { Plan } from '../../types/plan';
import { Topology } from '../../types/network';
import { TopologyDiagram } from '../../components/canvas/TopologyDiagram';
import { PageHeader } from '../../components/common/PageHeader';
import { Plus, Trash2, ArrowRight, Eye, Table, Link2, CircleDot, Monitor, Server } from 'lucide-react';

export const U05FormTableEditor: React.FC = () => {
  const { navigate, currentPath } = useViewport();
  const planId = currentPath.split('/')[2] || '';
  const [topology, setTopology] = useState<Topology | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'nodes' | 'links' | 'preview'>('nodes');
  const [showBulkAdd, setShowBulkAdd] = useState(false);
  const [bulkCount, setBulkCount] = useState(4);
  const [bulkType, setBulkType] = useState<'router' | 'pc' | 'server'>('pc');

  useEffect(() => {
    if (!planId) return;
    api.get<Plan>(`/records/${encodeURIComponent(planId)}`)
      .then((plan) => setTopology(plan.topology))
      .catch((error) => setMessage(error instanceof Error ? error.message : 'Could not load the saved topology.'));
  }, [planId]);

  const saveTopology = async (): Promise<boolean> => {
    if (!planId || !topology) return false;
    setSaving(true);
    setMessage(null);
    try {
      await api.patch<Plan>(`/records/${encodeURIComponent(planId)}`, { topology });
      setMessage('Topology saved to the backend.');
      window.dispatchEvent(new Event('lanlords:plans-changed'));
      return true;
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Could not save this topology.');
      return false;
    } finally { setSaving(false); }
  };

  const handleBulkAdd = () => {
    if (!topology) return;
    const newNodes = [...topology.nodes];
    const prefix = bulkType === 'router' ? 'R' : bulkType === 'pc' ? 'PC' : 'S';
    const startIdx = newNodes.filter((n) => n.type === bulkType).length + 1;

    for (let i = 0; i < bulkCount; i++) {
      const id = `${prefix}${startIdx + i}`;
      newNodes.push({
        id,
        type: bulkType,
        label: `${id} Bulk Host`,
        x: 200 + i * 40,
        y: 300,
      });
    }
    setTopology({ ...topology, nodes: newNodes });
    setShowBulkAdd(false);
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <PageHeader
        title="Form & Table Editor"
        subtitle="Manage network elements, interface connections, and link parameters in structured tables."
        actions={
          <div className="flex items-center gap-2">
            <button onClick={() => void saveTopology()} disabled={!topology || saving} className="px-3.5 py-2 rounded-lg border border-brand-border bg-brand-surface text-caption font-semibold disabled:opacity-50">{saving ? 'Saving…' : 'Save topology'}</button>
            <button
              onClick={() => setShowBulkAdd(true)}
              className="px-3.5 py-2 rounded-lg border border-brand-border bg-brand-surface hover:bg-brand-bg text-caption font-semibold flex items-center gap-1.5"
            >
              <Plus className="w-4 h-4 text-brand-primary" />
              <span>Add Several Devices</span>
            </button>
            <button
              onClick={async () => { if (await saveTopology()) navigate(`/plans/${encodeURIComponent(planId)}/edit/traffic`); }}
              disabled={!topology || saving}
              className="px-4 py-2 rounded-lg bg-brand-primary text-white text-btn font-semibold hover:opacity-90 flex items-center gap-1.5 shadow-sm"
            >
              <span>Next: Traffic & Scenarios</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        }
      />
      {message && <p role="status" className="text-caption text-brand-text-secondary">{message}</p>}
      {!topology && !message && <p className="text-caption text-brand-text-muted">Loading the saved topology…</p>}
      {topology && <>

      {/* Tabs */}
      <div className="flex border-b border-brand-border text-body font-semibold">
        <button
          onClick={() => setActiveTab('nodes')}
          className={`pb-3 px-4 border-b-2 flex items-center gap-2 transition-colors ${
            activeTab === 'nodes'
              ? 'border-brand-primary text-brand-primary'
              : 'border-transparent text-brand-text-secondary hover:text-brand-text-primary'
          }`}
        >
          <CircleDot className="w-4 h-4" />
          <span>Nodes ({topology.nodes.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('links')}
          className={`pb-3 px-4 border-b-2 flex items-center gap-2 transition-colors ${
            activeTab === 'links'
              ? 'border-brand-primary text-brand-primary'
              : 'border-transparent text-brand-text-secondary hover:text-brand-text-primary'
          }`}
        >
          <Link2 className="w-4 h-4" />
          <span>Links ({topology.links.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('preview')}
          className={`pb-3 px-4 border-b-2 flex items-center gap-2 transition-colors ${
            activeTab === 'preview'
              ? 'border-brand-primary text-brand-primary'
              : 'border-transparent text-brand-text-secondary hover:text-brand-text-primary'
          }`}
        >
          <Eye className="w-4 h-4" />
          <span>Diagram Preview</span>
        </button>
      </div>

      {/* Tab Content: Nodes Table */}
      {activeTab === 'nodes' && (
        <div className="overflow-x-auto bg-brand-surface border border-brand-border rounded-lg shadow-sm">
          <table className="w-full text-left text-body border-collapse">
            <thead>
              <tr className="border-b border-brand-border bg-brand-bg/60">
                <th className="py-3 px-4 text-overline text-brand-text-muted">Node ID</th>
                <th className="py-3 px-4 text-overline text-brand-text-muted">Type</th>
                <th className="py-3 px-4 text-overline text-brand-text-muted">Label</th>
                <th className="py-3 px-4 text-overline text-brand-text-muted text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-brand-border">
              {topology.nodes.map((node) => (
                <tr key={node.id} className="hover:bg-brand-bg/30">
                  <td className="py-2.5 px-4 font-mono font-bold text-brand-text-primary">{node.id}</td>
                  <td className="py-2.5 px-4">
                    <span className="text-[11px] font-mono uppercase px-2 py-0.5 rounded bg-brand-bg border border-brand-border">
                      {node.type}
                    </span>
                  </td>
                  <td className="py-2.5 px-4">
                    <input
                      type="text"
                      value={node.label}
                      onChange={(e) => {
                        const updated = topology.nodes.map((n) =>
                          n.id === node.id ? { ...n, label: e.target.value } : n
                        );
                        setTopology({ ...topology, nodes: updated });
                      }}
                      className="px-2 py-1 rounded bg-brand-bg border border-brand-border text-body w-full max-w-xs"
                    />
                  </td>
                  <td className="py-2.5 px-4 text-right">
                    <button
                      onClick={() => {
                        setTopology({
                          ...topology,
                          nodes: topology.nodes.filter((n) => n.id !== node.id),
                          links: topology.links.filter((l) => l.src !== node.id && l.dst !== node.id),
                        });
                      }}
                      className="p-1.5 text-brand-text-muted hover:text-rose-600 rounded"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab Content: Links Table */}
      {activeTab === 'links' && (
        <div className="overflow-x-auto bg-brand-surface border border-brand-border rounded-lg shadow-sm">
          <table className="w-full text-left text-body border-collapse">
            <thead>
              <tr className="border-b border-brand-border bg-brand-bg/60">
                <th className="py-3 px-4 text-overline text-brand-text-muted">Source</th>
                <th className="py-3 px-4 text-overline text-brand-text-muted">Destination</th>
                <th className="py-3 px-4 text-overline text-brand-text-muted">Bandwidth (Mbps)</th>
                <th className="py-3 px-4 text-overline text-brand-text-muted">Latency (ms)</th>
                <th className="py-3 px-4 text-overline text-brand-text-muted">Loss (%)</th>
                <th className="py-3 px-4 text-overline text-brand-text-muted text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-brand-border">
              {topology.links.map((link) => (
                <tr key={link.id} className="hover:bg-brand-bg/30">
                  <td className="py-2.5 px-4 font-mono font-bold">{link.src}</td>
                  <td className="py-2.5 px-4 font-mono font-bold">{link.dst}</td>
                  <td className="py-2.5 px-4">
                    <input
                      type="number"
                      value={link.bandwidth_mbps}
                      onChange={(e) => {
                        const updated = topology.links.map((l) =>
                          l.id === link.id ? { ...l, bandwidth_mbps: Number(e.target.value) } : l
                        );
                        setTopology({ ...topology, links: updated });
                      }}
                      className="w-24 px-2 py-1 rounded bg-brand-bg border border-brand-border font-mono text-caption"
                    />
                  </td>
                  <td className="py-2.5 px-4">
                    <input
                      type="number"
                      value={link.latency_ms}
                      onChange={(e) => {
                        const updated = topology.links.map((l) =>
                          l.id === link.id ? { ...l, latency_ms: Number(e.target.value) } : l
                        );
                        setTopology({ ...topology, links: updated });
                      }}
                      className="w-20 px-2 py-1 rounded bg-brand-bg border border-brand-border font-mono text-caption"
                    />
                  </td>
                  <td className="py-2.5 px-4">
                    <input
                      type="number"
                      value={link.loss_percent}
                      onChange={(e) => {
                        const updated = topology.links.map((l) =>
                          l.id === link.id ? { ...l, loss_percent: Number(e.target.value) } : l
                        );
                        setTopology({ ...topology, links: updated });
                      }}
                      className="w-20 px-2 py-1 rounded bg-brand-bg border border-brand-border font-mono text-caption"
                    />
                  </td>
                  <td className="py-2.5 px-4 text-right">
                    <button
                      onClick={() => {
                        setTopology({
                          ...topology,
                          links: topology.links.filter((l) => l.id !== link.id),
                        });
                      }}
                      className="p-1.5 text-brand-text-muted hover:text-rose-600 rounded"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab Content: Preview */}
      {activeTab === 'preview' && (
        <div className="bg-brand-surface border border-brand-border rounded-lg p-4">
          <TopologyDiagram topology={topology} interactive={false} />
        </div>
      )}

      {/* Add Several Modal */}
      {showBulkAdd && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-brand-surface border border-brand-border rounded-xl p-6 max-w-sm w-full space-y-4 shadow-xl">
            <h3 className="text-h3 font-bold text-brand-text-primary">Add Several Devices</h3>
            <div>
              <label className="text-label text-brand-text-primary block mb-1">Device Type</label>
              <select
                value={bulkType}
                onChange={(e) => setBulkType(e.target.value as any)}
                className="w-full px-3 py-2 bg-brand-bg border border-brand-border rounded-lg text-body"
              >
                <option value="pc">PC Host</option>
                <option value="server">Server</option>
                <option value="router">Router</option>
              </select>
            </div>
            <div>
              <label className="text-label text-brand-text-primary block mb-1">Quantity</label>
              <input
                type="number"
                min={1}
                max={20}
                value={bulkCount}
                onChange={(e) => setBulkCount(Number(e.target.value))}
                className="w-full px-3 py-2 bg-brand-bg border border-brand-border rounded-lg text-body font-mono"
              />
            </div>
            <div className="flex justify-end gap-2 pt-3 border-t border-brand-border">
              <button
                onClick={() => setShowBulkAdd(false)}
                className="px-3.5 py-1.5 rounded-lg text-caption font-semibold text-brand-text-secondary"
              >
                Cancel
              </button>
              <button
                onClick={handleBulkAdd}
                className="px-4 py-1.5 rounded-lg bg-brand-primary text-white text-caption font-semibold"
              >
                Add Devices
              </button>
            </div>
          </div>
        </div>
      )}
      </>}
    </div>
  );
};
