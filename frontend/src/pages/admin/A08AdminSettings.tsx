import React, { useState } from 'react';
import { PageHeader } from '../../components/common/PageHeader';
import { Save, Shield, AlertTriangle, Plus, X } from 'lucide-react';

export const A08AdminSettings: React.FC = () => {
  const [minRouters, setMinRouters] = useState(5);
  const [maxRouters, setMaxRouters] = useState(50);
  const [bandwidths, setBandwidths] = useState([100, 200, 500, 1000]);
  const [newBw, setNewBw] = useState('');
  const [slaDueSoon, setSlaDueSoon] = useState(12);
  const [slaOverdue, setSlaOverdue] = useState(24);
  const [shareDefaultDays, setShareDefaultDays] = useState(30);

  const [hasChanges, setHasChanges] = useState(false);

  const handleAddBw = () => {
    if (!newBw) return;
    setBandwidths([...bandwidths, Number(newBw)]);
    setNewBw('');
    setHasChanges(true);
  };

  const handleRemoveBw = (bw: number) => {
    setBandwidths(bandwidths.filter((b) => b !== bw));
    setHasChanges(true);
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-8 pb-24 relative">
      <PageHeader
        title="Simulation Cluster & Platform Settings"
        subtitle="Global boundaries, physical constraints, and SLA rules enforced across all network designs."
      />

      {/* Network Limits */}
      <div className="bg-brand-surface border border-brand-border rounded-xl p-6 space-y-4 shadow-sm">
        <h3 className="text-h3 font-bold text-brand-text-primary">1. Network Size Boundaries</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="text-label text-brand-text-primary block mb-1">Minimum Routers</label>
            <input
              type="number"
              value={minRouters}
              onChange={(e) => {
                setMinRouters(Number(e.target.value));
                setHasChanges(true);
              }}
              className="w-full px-3 py-2 bg-brand-bg border border-brand-border rounded-lg text-body font-mono"
            />
            <span className="text-[11px] text-brand-text-muted mt-0.5 block">Standard constraint: 5 routers</span>
          </div>

          <div>
            <label className="text-label text-brand-text-primary block mb-1">Maximum Routers</label>
            <input
              type="number"
              value={maxRouters}
              onChange={(e) => {
                setMaxRouters(Number(e.target.value));
                setHasChanges(true);
              }}
              className="w-full px-3 py-2 bg-brand-bg border border-brand-border rounded-lg text-body font-mono"
            />
            <span className="text-[11px] text-brand-text-muted mt-0.5 block">Standard constraint: 50 routers</span>
          </div>
        </div>
      </div>

      {/* Allowed Bandwidth Presets */}
      <div className="bg-brand-surface border border-brand-border rounded-xl p-6 space-y-4 shadow-sm">
        <h3 className="text-h3 font-bold text-brand-text-primary">2. Allowed Bandwidth Presets (Mbps)</h3>
        <p className="text-caption text-brand-text-secondary">
          Operators can select these speeds directly on link handles inside the canvas editor.
        </p>

        <div className="flex flex-wrap items-center gap-2">
          {bandwidths.map((bw) => (
            <span
              key={bw}
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-brand-bg border border-brand-border font-mono text-caption font-bold text-brand-text-primary"
            >
              <span>{bw} Mbps</span>
              <button onClick={() => handleRemoveBw(bw)} className="text-brand-text-muted hover:text-rose-600">
                <X className="w-3.5 h-3.5" />
              </button>
            </span>
          ))}

          <div className="flex items-center gap-1">
            <input
              type="number"
              placeholder="Custom Mbps"
              value={newBw}
              onChange={(e) => setNewBw(e.target.value)}
              className="w-28 px-2.5 py-1 text-caption bg-brand-bg border border-brand-border rounded-lg font-mono"
            />
            <button
              onClick={handleAddBw}
              className="p-1.5 rounded-lg bg-brand-primary text-white text-caption font-semibold"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Review SLAs & Share Expiry */}
      <div className="bg-brand-surface border border-brand-border rounded-xl p-6 space-y-4 shadow-sm">
        <h3 className="text-h3 font-bold text-brand-text-primary">3. Review SLA & Share Defaults</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="text-label text-brand-text-primary block mb-1">SLA Due Soon (Hours)</label>
            <input
              type="number"
              value={slaDueSoon}
              onChange={(e) => {
                setSlaDueSoon(Number(e.target.value));
                setHasChanges(true);
              }}
              className="w-full px-3 py-2 bg-brand-bg border border-brand-border rounded-lg text-body font-mono"
            />
          </div>

          <div>
            <label className="text-label text-brand-text-primary block mb-1">SLA Overdue (Hours)</label>
            <input
              type="number"
              value={slaOverdue}
              onChange={(e) => {
                setSlaOverdue(Number(e.target.value));
                setHasChanges(true);
              }}
              className="w-full px-3 py-2 bg-brand-bg border border-brand-border rounded-lg text-body font-mono"
            />
          </div>

          <div>
            <label className="text-label text-brand-text-primary block mb-1">Default Share Expiry (Days)</label>
            <input
              type="number"
              value={shareDefaultDays}
              onChange={(e) => {
                setShareDefaultDays(Number(e.target.value));
                setHasChanges(true);
              }}
              className="w-full px-3 py-2 bg-brand-bg border border-brand-border rounded-lg text-body font-mono"
            />
          </div>
        </div>
      </div>

      {/* Sticky Save Changes Bar */}
      <div className="sticky bottom-4 z-30 p-4 bg-brand-surface/95 backdrop-blur-md border border-brand-border rounded-xl shadow-xl flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          {hasChanges ? (
            <span className="flex items-center gap-1.5 text-caption font-semibold text-amber-600">
              <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
              Unsaved changes pending
            </span>
          ) : (
            <span className="text-caption text-brand-text-muted">Platform settings are not connected to persistent backend storage.</span>
          )}
        </div>

        <button
          disabled
          className="px-6 py-2.5 rounded-lg bg-brand-primary text-white text-btn font-semibold hover:opacity-90 disabled:opacity-40 flex items-center gap-1.5 shadow-sm touch-target"
        >
          <Save className="w-4 h-4" />
          <span>Persistence unavailable</span>
        </button>
      </div>
    </div>
  );
};
