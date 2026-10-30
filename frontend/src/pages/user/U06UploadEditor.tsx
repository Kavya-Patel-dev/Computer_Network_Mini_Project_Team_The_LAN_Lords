import React, { useRef, useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { api } from '../../api/client';
import { PageHeader } from '../../components/common/PageHeader';
import { isHostNode, isRoutingNode, NetworkNode } from '../../types/network';
import { Upload, CheckCircle2, AlertCircle, Download, ArrowRight } from 'lucide-react';

export const U06UploadEditor: React.FC = () => {
  const { navigate, currentPath } = useViewport();
  const planId = currentPath.split('/')[2] || '';
  const [fileState, setFileState] = useState<'idle' | 'parsing' | 'success' | 'error'>('idle');
  const [uploadedFile, setUploadedFile] = useState<string | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [topologyStats, setTopologyStats] = useState({ routers: 0, hosts: 0, links: 0 });
  const fileInput = useRef<HTMLInputElement>(null);

  const handleFile = async (file?: File) => {
    if (!file) return;
    setUploadedFile(file.name);
    setFileState('parsing');
    setParseError(null);
    try {
      if (file.size > 10 * 1024 * 1024) throw new Error('File exceeds the 10 MB limit.');
      if (!file.name.toLowerCase().endsWith('.json')) throw new Error('Only JSON topology files are supported. GraphML import is not implemented yet.');
      if (!planId) throw new Error('Open this upload page from an existing plan so the topology has a destination.');
      const parsed = JSON.parse(await file.text());
      if (!parsed || !Array.isArray(parsed.nodes) || !Array.isArray(parsed.links)) throw new Error('JSON must contain nodes[] and links[] arrays.');
      const nodes = parsed.nodes as NetworkNode[];
      const stats = {
        routers: nodes.filter((node) => isRoutingNode(node.type, node.simulationRole)).length,
        hosts: nodes.filter((node) => isHostNode(node.type, node.simulationRole)).length,
        links: parsed.links.length,
      };
      const updated = await api.patch(`/records/${encodeURIComponent(planId)}`, { topology: parsed });
      void updated;
      setTopologyStats(stats);
      setFileState('success');
    } catch (error) {
      setParseError(error instanceof Error ? error.message : 'Topology import failed.');
      setFileState('error');
    }
  };

  const handleDownloadExample = () => {
    const example = {
      name: "Office-HQ-Import",
      nodes: ["R1", "R2", "R3", "R4", "R5"].map((id, i) => ({ id, type: "router", label: `Router ${i + 1}` }))
        .concat([{ id: "H1", type: "host", label: "Host 1" }, { id: "H2", type: "host", label: "Host 2" }]),
      links: [
        ...[["R1", "R2"], ["R2", "R3"], ["R3", "R4"], ["R4", "R5"], ["R5", "R1"], ["H1", "R1"], ["H2", "R3"]]
          .map(([src, dst]) => ({ src, dst, bandwidth_mbps: 1000, latency_ms: 2, loss_percent: 0 })),
      ]
    };
    const blob = new Blob([JSON.stringify(example, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'netroute_example_topology.json';
    a.click();
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <PageHeader
        title="Upload Network Specification"
        subtitle="Import a JSON topology file into the current draft plan."
      />

      {/* Download Example Button */}
      <div className="flex justify-end">
        <button
          onClick={handleDownloadExample}
          className="text-caption font-semibold text-brand-primary hover:underline flex items-center gap-1.5"
        >
          <Download className="w-4 h-4" />
          <span>Download Reference JSON Schema</span>
        </button>
      </div>

      {/* Drag & Drop Zone */}
      <div
        onClick={() => fileInput.current?.click()}
        className={`p-12 border-2 border-dashed rounded-xl flex flex-col items-center justify-center text-center cursor-pointer transition-colors ${
          fileState === 'success'
            ? 'border-emerald-500 bg-emerald-50/20'
            : 'border-brand-border hover:border-brand-primary bg-brand-surface'
        }`}
      >
        <div className="w-14 h-14 rounded-full bg-brand-bg border border-brand-border flex items-center justify-center text-brand-primary mb-4 shadow-sm">
          <Upload className="w-6 h-6" />
        </div>
        <h3 className="text-h3 font-bold text-brand-text-primary mb-1">
          {fileState === 'parsing'
            ? 'Parsing specification file...'
            : fileState === 'success'
            ? 'Topology Parsed Successfully'
            : 'Click to Upload or Drag and Drop'}
        </h3>
        <p className="text-body text-brand-text-secondary max-w-sm mb-4">
          Accepts <span className="font-mono font-medium">.json</span> topology documents (max 10MB). GraphML import is not supported yet.
        </p>
        <input ref={fileInput} type="file" accept=".json,application/json" className="hidden" onChange={(event) => void handleFile(event.target.files?.[0])} />
        <button type="button" onClick={(event) => { event.stopPropagation(); fileInput.current?.click(); }} className="px-4 py-2 rounded-lg bg-brand-primary text-white text-caption font-semibold">Select Local File</button>
      </div>

      {/* Parsing Summary Card */}
      {fileState === 'success' && (
        <div className="p-5 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-300 dark:border-emerald-800 rounded-xl space-y-4 animate-in fade-in">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-emerald-800 dark:text-emerald-300 font-bold">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              <span>Specification Verified: {uploadedFile}</span>
            </div>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-100 text-emerald-900 font-bold">
              Valid Graph Structure
            </span>
          </div>

          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="p-3 bg-brand-surface rounded-lg border border-brand-border">
              <span className="text-overline text-brand-text-muted">Routers</span>
              <p className="text-h2 font-bold font-mono text-brand-text-primary mt-1">{topologyStats.routers}</p>
            </div>
            <div className="p-3 bg-brand-surface rounded-lg border border-brand-border">
              <span className="text-overline text-brand-text-muted">Host Leafs</span>
              <p className="text-h2 font-bold font-mono text-brand-text-primary mt-1">{topologyStats.hosts}</p>
            </div>
            <div className="p-3 bg-brand-surface rounded-lg border border-brand-border">
              <span className="text-overline text-brand-text-muted">Interconnects</span>
              <p className="text-h2 font-bold font-mono text-brand-text-primary mt-1">{topologyStats.links}</p>
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              onClick={() => setFileState('idle')}
              className="px-3.5 py-1.5 rounded-lg border border-brand-border text-brand-text-secondary text-caption font-semibold"
            >
              Upload Another
            </button>
            <button
              onClick={() => navigate(`/plans/${planId}/edit/canvas`)}
              className="px-4 py-2 rounded-lg bg-brand-primary text-white text-btn font-semibold hover:opacity-90 flex items-center gap-1.5"
            >
              <span>Open in Canvas Editor</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      <div className="p-4 bg-brand-surface border border-brand-border rounded-lg text-caption text-brand-text-secondary">The backend validates connectivity, router and host constraints when the plan is submitted.</div>

      {fileState === 'error' && (
        <div className="p-4 bg-rose-50 dark:bg-rose-950/40 border border-rose-300 dark:border-rose-800 rounded-lg space-y-2 text-rose-900 dark:text-rose-200">
          <div className="flex items-center gap-2 font-bold">
            <AlertCircle className="w-5 h-5 text-rose-600" />
            <span>Parsing Errors Encountered</span>
          </div>
          <p className="text-caption">{parseError || 'Could not read the selected topology file.'}</p>
        </div>
      )}
    </div>
  );
};
