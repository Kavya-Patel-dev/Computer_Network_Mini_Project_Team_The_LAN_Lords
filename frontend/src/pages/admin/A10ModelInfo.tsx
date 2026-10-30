import React, { useEffect, useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { api } from '../../api/client';
import { PageHeader } from '../../components/common/PageHeader';
import { BrainCircuit, ShieldCheck, Database, HelpCircle, AlertCircle, FileCode } from 'lucide-react';

type ModelMetadata = { status: string; artifact: string; sha256: string; candidate_paths_per_flow: number; inference: string };

export const A10ModelInfo: React.FC = () => {
  const { openOverlay } = useViewport();
  const [metadata, setMetadata] = useState<ModelMetadata | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.get<ModelMetadata>('/admin/model')
      .then((value) => { setMetadata(value); setError(null); })
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not verify model artifact.'));
  }, []);

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-8">
      <PageHeader
        title="AI Routing Agent Architecture & Checkpoint"
        subtitle="Technical specification of the imitation-trained Graph Neural Network routing policy."
        actions={
          <button
            onClick={() => openOverlay('O12')}
            className="px-3.5 py-2 rounded-lg border border-brand-border bg-brand-surface hover:bg-brand-bg text-caption font-semibold flex items-center gap-1.5"
          >
            <HelpCircle className="w-4 h-4 text-brand-primary" />
            <span>Open Model Limitations</span>
          </button>
        }
      />
      {error && <div role="alert" className="p-3 rounded-lg border border-rose-300 text-rose-700">{error}</div>}

      {/* Checkpoint Meta Card */}
      <div className="bg-brand-surface border border-brand-border rounded-xl p-6 space-y-4 shadow-sm">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 border border-emerald-200">
              <BrainCircuit className="w-8 h-8" />
            </div>
            <div>
              <h3 className="text-h2 font-bold text-brand-text-primary">
                Graph Routing Agent v1.0 (Imitation-Trained)
              </h3>
              <p className="text-caption text-brand-text-secondary mt-0.5">{metadata?.inference ?? 'Loading the configured inference metadata…'}</p>
            </div>
          </div>
          <span className="text-[11px] font-mono px-2 py-1 rounded bg-brand-bg border border-brand-border text-brand-text-muted">
            Frozen Day 5 Checkpoint
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-3 border-t border-brand-border text-caption">
          <div>
            <span className="text-brand-text-muted">Pinned Checkpoint SHA-256:</span>
            <p className="font-mono font-bold text-brand-text-primary mt-0.5 truncate">{metadata?.sha256 ? `sha256:${metadata.sha256}` : error ? 'Unavailable' : 'Checking artifact…'}</p>
          </div>
          <div>
            <span className="text-brand-text-muted">Inference Candidate Paths:</span>
            <p className="font-mono font-bold text-brand-text-primary mt-0.5">
              {metadata?.candidate_paths_per_flow ?? '—'} Candidate Paths per Flow
            </p>
          </div>
          <div>
            <span className="text-brand-text-muted">Last Validated:</span>
            <p className="font-mono font-bold text-brand-text-primary mt-0.5">
              {metadata?.status ?? 'Checking'}
            </p>
          </div>
        </div>
      </div>

      {/* Training Data & Evaluation Summary */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-brand-surface border border-brand-border rounded-xl p-5 space-y-3 shadow-sm">
          <h3 className="text-h3 font-bold text-brand-text-primary flex items-center gap-2">
            <Database className="w-5 h-5 text-brand-primary" />
            <span>Dataset & Training Topologies</span>
          </h3>
          <div className="space-y-2 text-caption text-brand-text-secondary">
            <div className="flex justify-between py-1 border-b border-brand-border">
              <span>Training Topologies (Synthetic Mesh & Core-Edge):</span>
              <span className="font-mono font-bold text-brand-text-primary">Day 5 Step 0 BC checkpoint</span>
            </div>
            <div className="flex justify-between py-1 border-b border-brand-border">
              <span>Validation Topologies:</span>
              <span className="font-mono font-bold text-brand-text-primary">Not reported in model metadata</span>
            </div>
            <div className="flex justify-between py-1 border-b border-brand-border">
              <span>Locked Test Suite Topologies:</span>
              <span className="font-mono font-bold text-brand-text-primary">No test data loaded by this screen</span>
            </div>
          </div>
        </div>

        <div className="bg-brand-surface border border-brand-border rounded-xl p-5 space-y-3 shadow-sm">
          <div className="flex items-center justify-between">
            <h3 className="text-h3 font-bold text-brand-text-primary">Evaluation Benchmark</h3>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-brand-bg border border-brand-border text-brand-text-muted">Stored Results</span>
          </div>
          <div className="space-y-2 text-caption text-brand-text-secondary">
            <p>Per-run comparisons are shown on each saved result. This panel does not show aggregate benchmark values unless an evaluation record is available.</p>
          </div>
        </div>
      </div>

      {/* The 4 Inference-Time Safety Fallback Rules */}
      <div className="bg-brand-surface border border-brand-border rounded-xl p-6 space-y-4 shadow-sm">
        <div>
          <h3 className="text-h3 font-bold text-brand-text-primary flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-emerald-600" />
            <span>Deterministic Heuristic Fallback Rules</span>
          </h3>
          <p className="text-caption text-brand-text-secondary mt-1">
            The inference wrapper uses full-graph load-aware Dijkstra (alpha=4.0) for these five fallback reason codes:
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-caption">
          <div className="p-4 bg-brand-bg border border-brand-border rounded-lg space-y-1">
            <span className="font-bold font-mono text-brand-primary">Invalid action</span>
            <p className="text-brand-text-secondary">
              Engaged if the selected action is out of bounds or masked invalid.
            </p>
          </div>

          <div className="p-4 bg-brand-bg border border-brand-border rounded-lg space-y-1">
            <span className="font-bold font-mono text-brand-primary">Failed path</span>
            <p className="text-brand-text-secondary">
              Engaged if the chosen candidate traverses a link or router currently in hardware outage.
            </p>
          </div>

          <div className="p-4 bg-brand-bg border border-brand-border rounded-lg space-y-1">
            <span className="font-bold font-mono text-brand-primary">Non-finite Q</span>
            <p className="text-brand-text-secondary">
              Engaged if any Q-value for a valid action is non-finite.
            </p>
          </div>

          <div className="p-4 bg-brand-bg border border-brand-border rounded-lg space-y-1">
            <span className="font-bold font-mono text-brand-primary">No valid candidate</span>
            <p className="text-brand-text-secondary">
              Engaged if the environment exposes no valid candidate action.
            </p>
          </div>
          <div className="p-4 bg-brand-bg border border-brand-border rounded-lg space-y-1 text-caption">
            <span className="font-bold font-mono text-brand-primary">Overloaded candidate</span>
            <p className="text-brand-text-secondary">Engaged when chosen-path backbone utilization exceeds 1.0 and another valid candidate is below 0.9.</p>
          </div>
        </div>
      </div>
    </div>
  );
};
