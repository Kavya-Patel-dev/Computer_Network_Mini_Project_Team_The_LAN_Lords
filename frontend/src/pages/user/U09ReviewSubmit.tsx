import React, { useEffect, useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api/client';
import { Plan } from '../../types/plan';
import { isHostNode, isRoutingNode } from '../../types/network';
import { PageHeader } from '../../components/common/PageHeader';
import { 
  CheckCircle2, 
  Layers, 
  Activity, 
  Cpu, 
  Clock, 
  Send, 
  Edit3, 
  AlertTriangle, 
  ShieldAlert 
} from 'lucide-react';

export const U09ReviewSubmit: React.FC = () => {
  const { navigate, currentPath } = useViewport();
  const { currentUser } = useAuth();
  const planId = currentPath.split('/')[2] || '';
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!planId) return;
    api.get<Plan>(`/records/${encodeURIComponent(planId)}`).then(setPlan)
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load saved plan.'));
  }, [planId]);

  const saveForReview = async () => {
    if (!planId) return;
    setSubmitting(true);
    setError(null);
    try {
      const submitted = await api.post<Plan>(`/records/${encodeURIComponent(planId)}/submit`);
      navigate(`/plans/${encodeURIComponent(submitted.id)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The plan could not be submitted.');
    } finally {
      setSubmitting(false);
    }
  };

  const isAdminOwned = currentUser?.role === 'admin';
  const nodes = plan?.topology?.nodes || [];
  const routers = nodes.filter((node) => isRoutingNode(node.type, node.simulationRole)).length;
  const hosts = nodes.filter((node) => isHostNode(node.type, node.simulationRole)).length;

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-8">
      {error && <div role="alert" className="p-3 rounded-lg border border-rose-300 bg-rose-50 text-rose-800 text-caption">{error}</div>}
      {/* Header & Stepper */}
      <div>
        <PageHeader
          title="Review & Submit Plan"
          subtitle="Confirm configuration specifications before submitting for administrator inspection."
        />

        <div className="flex items-center justify-between max-w-md mx-auto my-6 text-caption">
          <div className="flex items-center gap-2 text-emerald-600 font-medium">
            <span className="w-6 h-6 rounded-full bg-emerald-100 text-emerald-800 flex items-center justify-center text-xs">✓</span>
            <span>Network Design</span>
          </div>
          <div className="h-0.5 w-12 bg-emerald-500" />
          <div className="flex items-center gap-2 text-emerald-600 font-medium">
            <span className="w-6 h-6 rounded-full bg-emerald-100 text-emerald-800 flex items-center justify-center text-xs">✓</span>
            <span>Traffic & Scenarios</span>
          </div>
          <div className="h-0.5 w-12 bg-emerald-500" />
          <div className="flex items-center gap-2 text-brand-primary font-bold">
            <span className="w-6 h-6 rounded-full bg-brand-primary text-white flex items-center justify-center text-xs">3</span>
            <span>Review & Submit</span>
          </div>
        </div>
      </div>

      {/* Admin Notice if Admin Owned */}
      {isAdminOwned && (
        <div className="p-4 bg-purple-50 dark:bg-purple-950/40 border border-purple-200 dark:border-purple-800 rounded-lg flex items-center gap-3 text-purple-900 dark:text-purple-200 text-caption font-medium">
          <ShieldAlert className="w-5 h-5 text-purple-600 shrink-0" />
          <span>
            <strong>Admin plan policy:</strong> A different active administrator must review this submission. The submitting administrator cannot review their own plan.
          </span>
        </div>
      )}

      {/* 3 Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Card 1: Network */}
        <div className="bg-brand-surface border border-brand-border rounded-xl p-5 flex flex-col justify-between shadow-sm">
          <div>
            <div className="flex items-center justify-between mb-3 pb-2 border-b border-brand-border">
              <span className="text-overline text-brand-text-muted">Step 1 Summary</span>
              <button
                onClick={() => navigate(`/plans/${planId}/edit/canvas`)}
                className="text-caption font-semibold text-brand-primary hover:underline flex items-center gap-1"
              >
                <Edit3 className="w-3.5 h-3.5" /> Edit
              </button>
            </div>
            <h3 className="text-h3 font-bold text-brand-text-primary mb-2">Topology Structure</h3>
            <div className="space-y-1.5 text-caption text-brand-text-secondary">
              <p>• <strong>{routers} Routers</strong></p>
              <p>• <strong>{hosts} Hosts</strong></p>
              <p>• <strong>{plan?.topology?.links?.length || 0} Links</strong></p>
              <p>• <strong>Plan:</strong> {plan?.name || 'Loading saved draft…'}</p>
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-brand-border flex items-center gap-1.5 text-caption text-emerald-600 font-semibold">
            <CheckCircle2 className="w-4 h-4" />
            <span>Topology validation runs when this plan is submitted.</span>
          </div>
        </div>

        {/* Card 2: Traffic */}
        <div className="bg-brand-surface border border-brand-border rounded-xl p-5 flex flex-col justify-between shadow-sm">
          <div>
            <div className="flex items-center justify-between mb-3 pb-2 border-b border-brand-border">
              <span className="text-overline text-brand-text-muted">Step 2 Summary</span>
              <button
                onClick={() => navigate(`/plans/${planId}/edit/traffic`)}
                className="text-caption font-semibold text-brand-primary hover:underline flex items-center gap-1"
              >
                <Edit3 className="w-3.5 h-3.5" /> Edit
              </button>
            </div>
            <h3 className="text-h3 font-bold text-brand-text-primary mb-2">Traffic Profile</h3>
            <div className="space-y-1.5 text-caption text-brand-text-secondary">
              <p>• <strong>Traffic profile:</strong> {plan?.trafficPreset || 'Loading…'}</p>
              <p>• <strong>Manual flows:</strong> {plan?.flows?.length || 0}</p>
              <p>• <strong>Model:</strong> {plan?.trafficPreset === 'manual' ? 'Configured flows' : 'Built-in traffic generator'}</p>
              <p>• <strong>Unit:</strong> Demand and link capacity in Mbps</p>
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-brand-border flex items-center gap-1.5 text-caption text-brand-text-muted">
            <span>Settings read from the saved plan.</span>
          </div>
        </div>

        {/* Card 3: Scenarios */}
        <div className="bg-brand-surface border border-brand-border rounded-xl p-5 flex flex-col justify-between shadow-sm">
          <div>
            <div className="flex items-center justify-between mb-3 pb-2 border-b border-brand-border">
              <span className="text-overline text-brand-text-muted">Scenarios</span>
              <button
                onClick={() => navigate(`/plans/${planId}/edit/traffic`)}
                className="text-caption font-semibold text-brand-primary hover:underline flex items-center gap-1"
              >
                <Edit3 className="w-3.5 h-3.5" /> Edit
              </button>
            </div>
            <h3 className="text-h3 font-bold text-brand-text-primary mb-2">{plan?.selectedScenarios?.length || 0} Selected Conditions</h3>
            <div className="space-y-1.5 text-caption text-brand-text-secondary">
              {(plan?.selectedScenarios || []).map((scenario) => <p key={scenario}>• {scenario.replace(/_/g, ' ')}</p>)}
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-brand-border flex items-center gap-1.5 text-caption text-brand-text-muted font-mono">
            <Clock className="w-4 h-4 text-brand-primary" />
            <span>Runtime depends on topology and selected scenarios.</span>
          </div>
        </div>
      </div>

      {/* Model diagnostics availability */}
      <div className="bg-brand-surface border border-brand-border rounded-xl p-6 space-y-3 shadow-sm">
        <h3 className="text-h3 font-bold text-brand-text-primary flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-brand-primary" />
          <span>Submission validation</span>
        </h3>
        <p className="text-caption text-brand-text-secondary">The backend validates router count, connectivity, host leaf constraints, units, and manual flows. It does not claim uncomputed bridge, path-diversity, bottleneck, or port-limit analysis.</p>
      </div>

      {/* Submit Action Bar */}
      <div className="flex items-center justify-between pt-4 border-t border-brand-border">
        <button
          onClick={() => navigate('/plans')}
          className="px-4 py-2.5 rounded-lg border border-brand-border bg-brand-surface text-brand-text-secondary text-btn font-semibold hover:bg-brand-bg"
        >
          Save Draft
        </button>

        <button
          onClick={() => void saveForReview()}
          disabled={!plan || submitting || plan.selectedScenarios.length === 0}
          className="px-6 py-2.5 rounded-lg bg-brand-primary text-white text-btn font-semibold hover:opacity-90 flex items-center gap-2 shadow-md touch-target"
        >
          <Send className="w-4 h-4" />
          <span>{submitting ? 'Submitting…' : 'Submit for Administrator Review'}</span>
        </button>
      </div>
    </div>
  );
};
