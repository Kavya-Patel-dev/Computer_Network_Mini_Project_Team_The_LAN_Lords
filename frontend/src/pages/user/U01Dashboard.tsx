import React, { useEffect, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useViewport } from '../../context/ViewportContext';
import { api } from '../../api/client';
import { Plan } from '../../types/plan';
import { PageHeader } from '../../components/common/PageHeader';
import { KpiCard } from '../../components/common/KpiCard';
import { PlanCard } from '../../components/common/PlanCard';
import { EmptyState } from '../../components/common/EmptyState';
import { PageSkeleton } from '../../components/common/SkeletonLoader';
import { ErrorBanner } from '../../components/common/ErrorBanner';
import { Layers, Clock, CheckCircle2, BarChart3, Plus, Activity } from 'lucide-react';

type RecentRun = { id: string; planName: string; date: string; verdictText: string };
type Dashboard = { plan_count: number; run_count: number; plan_counts: Record<string, number>; plans: Plan[]; recent_runs: RecentRun[] };

export const U01Dashboard: React.FC = () => {
  const { currentUser } = useAuth();
  const { navigate } = useViewport();
  const [data, setData] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try { setData(await api.get<Dashboard>('/dashboard/user')); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not load dashboard data.'); }
    finally { setLoading(false); }
  };

  useEffect(() => { void load(); }, []);
  if (loading) return <PageSkeleton />;
  if (error) return <div className="p-6"><ErrorBanner message={error} onRetry={() => void load()} /></div>;
  if (!data) return null;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <PageHeader title={'Hello, ' + (currentUser?.name.split(' ')[0] || 'User')} subtitle="Your saved routing plans and completed model evaluations." actions={
        <button onClick={() => navigate('/plans/new')} className="px-4 py-2 rounded-lg bg-brand-primary text-white text-btn font-semibold flex items-center gap-2"><Plus className="w-4 h-4" />New Plan</button>
      } />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard label="Total Plans" value={data.plan_count} subtext="Saved in your account" icon={<Layers className="w-5 h-5 text-brand-primary" />} />
        <KpiCard label="Pending Review" value={data.plan_counts['Pending Review'] || 0} subtext="Awaiting admin decision" icon={<Clock className="w-5 h-5 text-amber-500" />} />
        <KpiCard label="Approved" value={data.plan_counts.Approved || 0} subtext="Eligible to simulate" icon={<CheckCircle2 className="w-5 h-5 text-emerald-500" />} />
        <KpiCard label="Simulation Runs" value={data.run_count} subtext="Persisted real evaluations" icon={<BarChart3 className="w-5 h-5 text-blue-500" />} />
      </div>

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div><h2 className="text-h2 font-bold text-brand-text-primary">Recent Plans</h2><p className="text-caption text-brand-text-secondary">Loaded from your account.</p></div>
          <button onClick={() => navigate('/plans')} className="text-caption font-semibold text-brand-primary hover:underline">View all plans</button>
        </div>
        {data.plans.length === 0
          ? <EmptyState icon={<Layers className="w-6 h-6" />} title="No plans yet" description="Create a plan to save a topology and configure its traffic." actionLabel="Create a Plan" onAction={() => navigate('/plans/new')} />
          : <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">{data.plans.slice(0, 3).map((plan) => <PlanCard key={plan.id} plan={plan} />)}</div>}
      </section>

      <section className="bg-brand-surface border border-brand-border rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2"><Activity className="w-5 h-5 text-brand-primary" /><h2 className="text-h3 font-bold text-brand-text-primary">Recent Simulation Runs</h2></div>
        {data.recent_runs.length === 0
          ? <p className="text-caption text-brand-text-muted">No completed runs have been saved.</p>
          : <div className="divide-y divide-brand-border">{data.recent_runs.map((run) => <button key={run.id} onClick={() => navigate('/results/' + run.id)} className="w-full py-3 text-left flex items-start justify-between gap-4 hover:bg-brand-bg/50"><span><strong className="block text-body text-brand-text-primary">{run.planName}</strong><span className="text-caption text-brand-text-secondary">{run.verdictText}</span></span><time className="text-caption text-brand-text-muted">{new Date(run.date).toLocaleString()}</time></button>)}</div>}
      </section>
    </div>
  );
};

