import React, { useEffect, useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api/client';
import { Plan } from '../../types/plan';
import { isRoutingNode } from '../../types/network';
import { TopologyDiagram } from '../../components/canvas/TopologyDiagram';
import { PageHeader } from '../../components/common/PageHeader';
import { 
  ShieldCheck, 
  AlertTriangle, 
  CheckCircle2, 
  XCircle, 
  Lock, 
  Pin, 
  ArrowLeft, 
  Send 
} from 'lucide-react';

export const A02ReviewScreen: React.FC = () => {
  const { navigate, openOverlay, closeOverlay, currentPath } = useViewport();
  const { currentUser } = useAuth();
  const planId = currentPath.split('/')[3] || '';
  const [plan, setPlan] = useState<Plan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [checklist, setChecklist] = useState({
    plausible: true,
    capacities: true,
    traffic: true,
  });

  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [comment, setComment] = useState('');
  const [activeTab, setActiveTab] = useState<'topology' | 'analysis'>('topology');

  useEffect(() => {
    if (!planId) return;
    api.get<Plan>(`/records/${encodeURIComponent(planId)}`)
      .then((row) => { setPlan(row); setError(null); })
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load this plan.'))
      .finally(() => setLoading(false));
  }, [planId]);

  const isOwnPlan = !!plan && currentUser?.email.toLowerCase() === plan.ownerEmail.toLowerCase();
  const submitReview = async (decision: 'approved' | 'changes_requested' | 'rejected', note: string, tags: string[] = []) => {
    if (!plan) return;
    const cleanNote = note.trim() || (decision === 'approved' ? 'Approved' : '');
    if (!cleanNote) throw new Error('A feedback note is required for this decision.');
    await api.post(`/records/${encodeURIComponent(plan.id)}/review`, { decision, comment: cleanNote, tags });
    closeOverlay();
    navigate('/admin/queue');
  };

  const tags = [
    'Bandwidth too low',
    'No redundancy',
    'Invalid topology',
    'Unrealistic traffic',
    'Bottleneck detected',
    'Other',
  ];

  const toggleTag = (t: string) => {
    setSelectedTags((prev) =>
      prev.includes(t) ? prev.filter((item) => item !== t) : [...prev, t]
    );
  };

  if (loading) return <div className="p-6 text-brand-text-muted">Loading plan for review…</div>;
  if (error || !plan) return <div role="alert" className="p-6 text-rose-600">{error || 'Plan not found.'}</div>;

  const routers = plan.topology.nodes.filter((node) => isRoutingNode(node.type, node.simulationRole));
  const simulationLinks = plan.topology.links.filter((link) => link.simulationIncluded !== false);
  const leafHosts = plan.topology.nodes.filter((node) => !routers.includes(node)).every((node) => simulationLinks.filter((link) => link.src === node.id || link.dst === node.id).length === 1);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <PageHeader
        title={`Reviewing: ${plan.name} (${plan.version})`}
        subtitle={`Submitted by ${plan.owner} • ${plan.routerCount} Routers, ${plan.hostCount} Hosts`}
        actions={
          <button
            onClick={() => navigate('/admin/queue')}
            className="px-3.5 py-1.5 rounded-lg border border-brand-border bg-brand-surface hover:bg-brand-bg text-caption font-semibold flex items-center gap-1.5"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Queue</span>
          </button>
        }
      />
      {notice && <div role="status" className="p-3 rounded-lg border border-emerald-300 text-emerald-700">{notice}</div>}
      {error && <div role="alert" className="p-3 rounded-lg border border-rose-300 text-rose-700">{error}</div>}

      {/* Split Layout: Left 60%, Right 40% */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left 60%: Interactive Diagram & Structural Inspection */}
        <div className="lg:col-span-7 space-y-4">
          <div className="bg-brand-surface border border-brand-border rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-brand-border">
              <span className="text-overline text-brand-text-muted">Network Topology Canvas</span>
              <span className="text-caption text-brand-text-secondary">Click any element to drop an inspection pin</span>
            </div>

            <div className="h-[min(70vh,740px)] min-h-[560px]">
              <TopologyDiagram
                topology={plan.topology}
                interactive={true}
              />
            </div>
          </div>

          <div className="p-4 bg-brand-surface border border-brand-border rounded-xl text-caption space-y-2">
            <h4 className="font-bold text-body text-brand-text-primary">Submitted Topology Summary</h4>
            <div className="grid grid-cols-2 gap-2 text-brand-text-secondary">
              <p>• Routers: {routers.length}</p>
              <p>• Links: {plan.topology.links.length}</p>
              <p>• Hosts are leaves: {leafHosts ? 'Yes' : 'No'}</p>
              <p>• Selected scenarios: {plan.selectedScenarios.join(', ') || 'None'}</p>
            </div>
          </div>
        </div>

        {/* Right 40%: Review Decision Panel or Blocked Self-Review State */}
        <div className="lg:col-span-5">
          {isOwnPlan ? (
            /* Blocked Self-Review State */
            <div className="p-8 bg-amber-50 dark:bg-amber-950/40 border-2 border-amber-400 dark:border-amber-800 rounded-xl text-center space-y-4 shadow-lg animate-in fade-in">
              <div className="w-14 h-14 rounded-full bg-amber-100 text-amber-800 mx-auto flex items-center justify-center">
                <Lock className="w-7 h-7" />
              </div>
              <h3 className="text-h2 font-bold text-amber-900 dark:text-amber-100">
                Self-Review Blocked
              </h3>
              <p className="text-body text-amber-800 dark:text-amber-200 leading-relaxed">
                You cannot review or approve your own plan. Another active administrator must review this submission.
              </p>
              <div className="pt-2">
                <button
                  onClick={() => navigate('/admin/queue')}
                  className="px-4 py-2 rounded-lg bg-amber-700 text-white text-caption font-semibold hover:bg-amber-800"
                >
                  Return to Queue
                </button>
              </div>
            </div>
          ) : (
            /* Active Review Decision Panel */
            <div className="bg-brand-surface border border-brand-border rounded-xl p-6 space-y-5 shadow-sm">
              <div className="pb-3 border-b border-brand-border">
                <h3 className="text-h3 font-bold text-brand-text-primary">Administrator Checklist</h3>
                <p className="text-caption text-brand-text-muted mt-0.5">
                  Confirm physical viability before permitting 5-scenario evaluation.
                </p>
              </div>

              {/* Checklist */}
              <div className="space-y-2 text-caption">
                <label className="flex items-center gap-2.5 p-2 bg-brand-bg rounded border border-brand-border cursor-pointer">
                  <input
                    type="checkbox"
                    checked={checklist.plausible}
                    onChange={(e) => setChecklist({ ...checklist, plausible: e.target.checked })}
                    className="rounded text-brand-primary"
                  />
                  <span className="font-medium text-brand-text-primary">Topology Plausible & Connected</span>
                </label>
                <label className="flex items-center gap-2.5 p-2 bg-brand-bg rounded border border-brand-border cursor-pointer">
                  <input
                    type="checkbox"
                    checked={checklist.capacities}
                    onChange={(e) => setChecklist({ ...checklist, capacities: e.target.checked })}
                    className="rounded text-brand-primary"
                  />
                  <span className="font-medium text-brand-text-primary">Link Capacities Sensible (&gt;0 Mbps)</span>
                </label>
                <label className="flex items-center gap-2.5 p-2 bg-brand-bg rounded border border-brand-border cursor-pointer">
                  <input
                    type="checkbox"
                    checked={checklist.traffic}
                    onChange={(e) => setChecklist({ ...checklist, traffic: e.target.checked })}
                    className="rounded text-brand-primary"
                  />
                  <span className="font-medium text-brand-text-primary">Synthetic Traffic Demand Reasonable</span>
                </label>
              </div>

              {/* Structured Tags */}
              <div>
                <label className="text-label text-brand-text-primary block mb-2">Structured Review Tags</label>
                <div className="flex flex-wrap gap-1.5">
                  {tags.map((t) => (
                    <button
                      key={t}
                      onClick={() => toggleTag(t)}
                      className={`px-2.5 py-1 rounded-full text-caption font-medium border transition-colors ${
                        selectedTags.includes(t)
                          ? 'bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-950 dark:text-amber-200'
                          : 'bg-brand-bg text-brand-text-secondary border-brand-border hover:border-brand-primary'
                      }`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>

              {/* Review Comment Box */}
              <div>
                <label className="text-label text-brand-text-primary block mb-1">
                  Reviewer Feedback Note <span className="text-caption text-brand-text-muted">(Required for revisions or rejection)</span>
                </label>
                <textarea
                  rows={3}
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="State requirements or approval justification..."
                  className="w-full p-2.5 bg-brand-bg border border-brand-border rounded-lg text-body"
                />
              </div>

              {/* Action Buttons: Approve, Request Changes, Reject */}
              <div className="pt-3 border-t border-brand-border space-y-2">
                <button
                  onClick={() => openOverlay('O04', { note: comment, onConfirm: (note: string) => submitReview('approved', note) })}
                  className="w-full py-2.5 rounded-lg bg-emerald-600 text-white text-btn font-semibold hover:bg-emerald-700 flex items-center justify-center gap-2 shadow-sm touch-target"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Approve Plan for Simulation</span>
                </button>

                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => openOverlay('O05', { note: comment, tags: selectedTags, onConfirm: (note: string, tags: string[]) => submitReview('changes_requested', note, tags) })}
                    className="py-2 rounded-lg bg-orange-600 text-white text-caption font-semibold hover:bg-orange-700 flex items-center justify-center gap-1.5"
                  >
                    <AlertTriangle className="w-4 h-4" />
                    <span>Request Changes</span>
                  </button>
                  <button
                    onClick={() => openOverlay('O06', { note: comment, tags: selectedTags, onConfirm: (note: string) => submitReview('rejected', note, selectedTags) })}
                    className="py-2 rounded-lg bg-rose-600 text-white text-caption font-semibold hover:bg-rose-700 flex items-center justify-center gap-1.5"
                  >
                    <XCircle className="w-4 h-4" />
                    <span>Reject Plan</span>
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
