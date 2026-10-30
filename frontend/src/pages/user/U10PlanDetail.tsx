import React, { useEffect, useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api/client';
import { Plan } from '../../types/plan';
import { isHostNode, isRoutingNode } from '../../types/network';
import { PageHeader } from '../../components/common/PageHeader';
import { StatusChip } from '../../components/common/StatusChip';
import { TopologyDiagram } from '../../components/canvas/TopologyDiagram';
import { U11AnalysisReport } from './U11AnalysisReport';
import { U12VersionsCompare } from './U12VersionsCompare';
import { 
  Play, 
  Edit3, 
  Share2, 
  FileText, 
  Clock, 
  History, 
  ShieldAlert, 
  Copy, 
  Trash2, 
  AlertTriangle 
} from 'lucide-react';

export const U10PlanDetail: React.FC = () => {
  const { navigate, currentPath } = useViewport();
  const { currentUser, role } = useAuth();
  const planId = currentPath.split('/')[2] || '';
  const [plan, setPlan] = useState<Plan | null>(null);
  const [runs, setRuns] = useState<{ id: string; planId: string; date: string; scenariosCount: number; lossAi: string | null; lossStatic: string | null }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'analysis' | 'review' | 'simulation' | 'versions' | 'activity'>('overview');

  useEffect(() => {
    if (!planId) return;
    Promise.all([
      api.get<Plan>(`/records/${encodeURIComponent(planId)}`),
      api.get<{ items: { id: string; planId: string; date: string; scenariosCount: number; lossAi: string | null; lossStatic: string | null }[] }>(`/results?plan_id=${encodeURIComponent(planId)}&limit=100`),
    ]).then(([loadedPlan, resultPage]) => {
      setPlan(loadedPlan);
      setRuns(resultPage.items.filter((run) => run.planId === loadedPlan.id));
      setError(null);
    }).catch((err) => setError(err instanceof Error ? err.message : 'Could not load this plan.'))
      .finally(() => setLoading(false));
  }, [planId]);

  if (loading) return <div className="p-6 text-brand-text-muted">Loading plan…</div>;
  if (error || !plan) return <div role="alert" className="p-6 text-rose-600">{error || 'Plan not found.'}</div>;

  const isOwner = currentUser?.email.toLowerCase() === plan.ownerEmail.toLowerCase();
  const isAdmin = role === 'admin';
  const topologyNodes = plan.topology?.nodes || [];
  const topologyLinks = plan.topology?.links || [];
  const routerCount = topologyNodes.filter((node) => isRoutingNode(node.type, node.simulationRole)).length;
  const hostCount = topologyNodes.filter((node) => isHostNode(node.type, node.simulationRole)).length;
  const serverCount = topologyNodes.filter((node) => node.type === 'server').length;
  const maxCapacity = topologyLinks.length ? Math.max(...topologyLinks.map((link) => link.bandwidth_mbps || 0)) : 0;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Admin Read-Only Notice */}
      {isAdmin && !isOwner && (
        <div className="p-3 bg-purple-50 dark:bg-purple-950/40 border border-purple-200 dark:border-purple-800 rounded-lg flex items-center gap-2 text-purple-900 dark:text-purple-200 text-caption font-medium">
          <ShieldAlert className="w-4 h-4 text-purple-600 shrink-0" />
          <span>Viewing as admin. You cannot edit another operator's plan.</span>
        </div>
      )}

      {/* Header */}
      <PageHeader
        title={plan.name}
        subtitle={plan.description}
        badge={
          <div className="flex items-center gap-2">
            <StatusChip status={plan.status} />
            <span className="font-mono text-caption px-2 py-0.5 rounded bg-brand-surface border border-brand-border text-brand-text-secondary font-bold">
              {plan.version}
            </span>
          </div>
        }
        actions={
          <div className="flex items-center gap-2">
            {plan.status === 'Approved' && (
              <button
                onClick={() => navigate(`/plans/${plan.id}/run`)}
                className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-btn font-semibold hover:bg-emerald-700 flex items-center gap-2 shadow-sm"
              >
                <Play className="w-4 h-4 fill-current" />
                <span>Run Simulation</span>
              </button>
            )}

            {plan.status === 'Completed' && (
              <>
                <button
                  onClick={() => runs[0] && navigate(`/results/${runs[0].id}`)}
                  className="px-4 py-2 rounded-lg bg-brand-primary text-white text-btn font-semibold hover:opacity-90 flex items-center gap-2 shadow-sm"
                >
                  <FileText className="w-4 h-4" />
                  <span>View Results</span>
                </button>
                <button
                  onClick={() => runs[0] && navigate(`/results/${runs[0].id}/share`)}
                  className="px-3.5 py-2 rounded-lg border border-brand-border bg-brand-surface hover:bg-brand-bg text-brand-text-primary text-caption font-semibold flex items-center gap-1.5"
                >
                  <Share2 className="w-4 h-4" />
                  <span>Share</span>
                </button>
              </>
            )}

            {isOwner && (plan.status === 'Draft' || plan.status === 'Changes Requested') && (
              <button
                onClick={() => navigate(`/plans/${plan.id}/edit/canvas`)}
                className="px-4 py-2 rounded-lg bg-brand-primary text-white text-btn font-semibold hover:opacity-90 flex items-center gap-2"
              >
                <Edit3 className="w-4 h-4" />
                <span>Edit Plan</span>
              </button>
            )}
          </div>
        }
      />

      <section className="p-4 rounded-xl border border-brand-border bg-brand-surface flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="text-caption text-brand-text-secondary">
          {plan.status === 'Draft' || plan.status === 'Changes Requested' ? (
            <><strong className="text-brand-text-primary">Next: finish the topology and traffic, then submit for administrator review.</strong><br />Simulation unlocks only after an administrator approves a valid 5–50 router network.</>
          ) : plan.status === 'Pending Review' ? (
            <><strong className="text-brand-text-primary">Waiting for administrator review.</strong><br />After approval, return here and choose Run Simulation. The model runs only during that simulation.</>
          ) : plan.status === 'Approved' ? (
            <><strong className="text-brand-text-primary">Approved and ready to simulate.</strong><br />The run compares Static Dijkstra, Load-aware Dijkstra, and the trained AI policy with its safety fallback.</>
          ) : plan.status === 'Completed' ? (
            <><strong className="text-brand-text-primary">Simulation results are available.</strong><br />Open Analysis Report for the latest run or Simulation Runs to compare saved runs.</>
          ) : (
            <><strong className="text-brand-text-primary">Plan status: {plan.status}.</strong><br />See Review & Comments for the administrator's decision and next steps.</>
          )}
        </div>
        <div className="flex gap-2 shrink-0">
          {(plan.status === 'Draft' || plan.status === 'Changes Requested') && isOwner && <button onClick={() => navigate(`/plans/${plan.id}/edit/canvas`)} className="px-3 py-2 rounded-lg bg-brand-primary text-white text-caption font-semibold">Continue setup</button>}
          {plan.status === 'Pending Review' && <button onClick={() => setActiveTab('review')} className="px-3 py-2 rounded-lg border border-brand-border text-caption font-semibold">View review status</button>}
          {plan.status === 'Approved' && <button onClick={() => navigate(`/plans/${plan.id}/run`)} className="px-3 py-2 rounded-lg bg-emerald-600 text-white text-caption font-semibold">Run Simulation</button>}
          {runs[0] && <button onClick={() => navigate(`/results/${runs[0].id}`)} className="px-3 py-2 rounded-lg border border-brand-border text-caption font-semibold">Latest results</button>}
        </div>
      </section>

      {/* Navigation Tabs (Scrollable on mobile) */}
      <div className="flex items-center gap-2 border-b border-brand-border overflow-x-auto text-body font-semibold">
        {[
          { id: 'overview', label: 'Overview' },
          { id: 'analysis', label: 'Analysis Report' },
          { id: 'review', label: 'Review & Comments' },
          { id: 'simulation', label: 'Simulation Runs' },
          { id: 'versions', label: 'Versions & Diff' },
          { id: 'activity', label: 'Activity Log' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`pb-3 px-3.5 whitespace-nowrap border-b-2 transition-colors ${
              activeTab === tab.id
                ? 'border-brand-primary text-brand-primary'
                : 'border-transparent text-brand-text-secondary hover:text-brand-text-primary'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab 1: Overview */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <TopologyDiagram topology={plan.topology} interactive={true} />
            </div>

            <div className="space-y-4">
              <div className="p-5 bg-brand-surface border border-brand-border rounded-xl space-y-3">
                <span className="text-overline text-brand-text-muted">Topology Inventory</span>
                <div className="space-y-2 text-caption">
                  <div className="flex justify-between py-1 border-b border-brand-border">
                    <span className="text-brand-text-secondary">Core Routers:</span>
                    <span className="font-mono font-bold text-brand-text-primary">{routerCount}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-brand-border">
                    <span className="text-brand-text-secondary">End Workstations:</span>
                    <span className="font-mono font-bold text-brand-text-primary">{hostCount}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-brand-border">
                    <span className="text-brand-text-secondary">Application Servers:</span>
                    <span className="font-mono font-bold text-brand-text-primary">{serverCount}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-brand-border">
                    <span className="text-brand-text-secondary">Max Link Trunk:</span>
                    <span className="font-mono font-bold text-brand-text-primary">{maxCapacity || '—'} Mbps</span>
                  </div>
                </div>
              </div>

              <div className="p-5 bg-brand-surface border border-brand-border rounded-xl space-y-3">
                <span className="text-overline text-brand-text-muted">Approved Parameters</span>
                <div className="space-y-1.5 text-caption text-brand-text-secondary">
                  <p>• <strong>Traffic:</strong> {plan.trafficPreset}</p>
                  <p>• <strong>Selected scenarios:</strong> {plan.selectedScenarios.map((scenario) => scenario.replace(/_/g, ' ')).join(', ') || 'none'}</p>
                  <p>• <strong>Review:</strong> {plan.review ? `${plan.review.decision.replace(/_/g, ' ')} by ${plan.review.admin} on ${new Date(plan.review.date).toLocaleString()}` : 'No review recorded'}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Analysis Report (Embeds U11) */}
      {activeTab === 'analysis' && <U11AnalysisReport />}

      {/* Tab 3: Review & Comments */}
      {activeTab === 'review' && (
        <div className="space-y-6 max-w-4xl">
          <div className="p-4 rounded-lg border border-blue-200 bg-blue-50 text-blue-900 text-caption">
            <strong>How review works:</strong> the plan owner submits from Review & Submit. An administrator reviews it in the Admin Review Queue and leaves the decision and comment here. Only an Approved plan can run a simulation. Administrators cannot approve their own plans.
          </div>
          {/* Timeline of Decisions */}
          <div className="bg-brand-surface border border-brand-border rounded-xl p-6 space-y-4">
            <h3 className="text-h3 font-bold text-brand-text-primary">Review Decision Timeline</h3>
            <p className="text-caption text-brand-text-secondary">You submit a completed draft for an administrator to review. The administrator's decision and feedback comment appear here. This is review feedback, not a live chat; if changes are requested, edit the plan and submit it again. Simulation becomes available only after approval.</p>
            <div className="space-y-4 border-l-2 border-brand-border pl-4 text-caption">
              {plan.review ? <div><span className="font-mono text-[11px] text-brand-text-muted">{new Date(plan.review.date).toLocaleString()}</span><p className="font-bold text-brand-text-primary text-body">{plan.review.decision.replace(/_/g, ' ')} by {plan.review.admin}</p><p className="text-brand-text-secondary mt-0.5">{plan.review.comment}</p>{plan.review.tags?.length > 0 && <p className="text-brand-text-muted mt-1">Review tags: {plan.review.tags.join(', ')}</p>}</div> : <p className="text-brand-text-muted">No administrator decision has been recorded. Current plan status: {plan.status}.</p>}
            </div>
            {(plan.status === 'Draft' || plan.status === 'Changes Requested') && isOwner && <button onClick={() => navigate(`/plans/${plan.id}/edit/review`)} className="px-3 py-2 rounded-lg bg-brand-primary text-white text-caption font-semibold">Continue to submit for review</button>}
            {plan.status === 'Pending Review' && <p className="text-caption font-semibold text-amber-700">Waiting for an administrator. You can continue to view the saved topology, but simulation is locked.</p>}
            {plan.status === 'Approved' && <button onClick={() => navigate(`/plans/${plan.id}/run`)} className="px-3 py-2 rounded-lg bg-emerald-600 text-white text-caption font-semibold">Run approved simulation</button>}
          </div>
        </div>
      )}

      {/* Tab 4: Simulation Runs */}
      {activeTab === 'simulation' && (
        <div className="space-y-4">
          {runs.length ? runs.map((run) => <div key={run.id} className="p-4 bg-brand-surface border border-brand-border rounded-lg flex items-center justify-between"><div><div className="font-bold text-body text-brand-text-primary">Run {run.id}</div><p className="text-caption text-brand-text-muted mt-0.5">{new Date(run.date).toLocaleString()} · {run.scenariosCount} scenario(s) · AI {run.lossAi ?? '—'} vs static {run.lossStatic ?? '—'}</p></div><button onClick={() => navigate(`/results/${run.id}`)} className="px-3.5 py-1.5 rounded-lg bg-brand-primary text-white text-caption font-semibold hover:opacity-90">Open Results & AI Decisions</button></div>) : <div className="p-4 bg-brand-surface border border-brand-border rounded-lg text-caption text-brand-text-muted space-y-3"><p>No simulation runs have been saved for this plan.</p>{plan.status === 'Approved' ? <button onClick={() => navigate(`/plans/${plan.id}/run`)} className="px-3 py-2 rounded-lg bg-emerald-600 text-white font-semibold">Run Simulation</button> : <p>Current status is {plan.status}. Complete setup, submit for review, and wait for approval before running the model.</p>}</div>}
        </div>
      )}

      {/* Tab 5: Versions (Embeds U12) */}
      {activeTab === 'versions' && <U12VersionsCompare />}

      {/* Tab 6: Activity */}
      {activeTab === 'activity' && (
        <div className="bg-brand-surface border border-brand-border rounded-xl p-5 space-y-3">
          <h3 className="text-h3 font-semibold text-brand-text-primary mb-3">Plan Event Stream</h3>
          <div className="space-y-2 text-caption">
            {plan.versions?.map((version, index) => <div key={`${version.version}-${index}`} className="p-2.5 bg-brand-bg border border-brand-border rounded flex justify-between"><span>{version.summary} · {version.author} · {version.status}</span><span className="font-mono text-brand-text-muted">{new Date(version.date).toLocaleString()}</span></div>)}
            {!plan.versions?.length && <p className="text-brand-text-muted">No version activity is recorded.</p>}
          </div>
        </div>
      )}
    </div>
  );
};
