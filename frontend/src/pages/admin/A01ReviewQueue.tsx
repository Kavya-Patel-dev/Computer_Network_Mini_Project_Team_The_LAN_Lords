import React, { useEffect, useMemo, useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api/client';
import { Plan } from '../../types/plan';
import { PageHeader } from '../../components/common/PageHeader';
import { KpiCard } from '../../components/common/KpiCard';
import { StatusChip } from '../../components/common/StatusChip';
import { EmptyState } from '../../components/common/EmptyState';
import { 
  ClipboardList, 
  Search, 
  Clock, 
  Lock, 
  AlertTriangle, 
  ArrowRight, 
  ShieldCheck, 
} from 'lucide-react';

export const A01ReviewQueue: React.FC = () => {
  const { navigate } = useViewport();
  const { currentUser } = useAuth();

  const [search, setSearch] = useState('');
  const [slaFilter, setSlaFilter] = useState('all');
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<{ items: Plan[] }>('/records?limit=100')
      .then((data) => { setPlans(data.items); setError(null); })
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load review queue.'))
      .finally(() => setLoading(false));
  }, []);

  const queuePlans = useMemo(() => plans.filter((p) => {
    if (p.status !== 'Pending Review' && p.status !== 'Changes Requested') return false;
    const matchesSearch = `${p.name} ${p.owner} ${p.ownerEmail}`.toLowerCase().includes(search.toLowerCase());
    const hours = p.submitted_at ? Math.max(0, (Date.now() - new Date(p.submitted_at).getTime()) / 3_600_000) : null;
    const matchesSla = slaFilter === 'all' || (hours !== null && (
      slaFilter === 'ontime' ? hours < 18 : slaFilter === 'duesoon' ? hours >= 18 && hours < 24 : hours >= 24
    ));
    return matchesSearch && matchesSla;
  }), [plans, search, slaFilter]);
  const pendingPlans = queuePlans.filter((p) => p.status === 'Pending Review');
  const oldestHours = queuePlans.reduce((oldest, p) => {
    const hours = p.submitted_at ? (Date.now() - new Date(p.submitted_at).getTime()) / 3_600_000 : 0;
    return Math.max(oldest, hours);
  }, 0);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <PageHeader
        title="Administrator Review Queue"
        subtitle="Validate physical connectivity, interface capacities, and traffic bounds prior to simulation granting."
      />

      {/* KPI Strip */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="Pending Review"
          value={pendingPlans.length}
          subtext="Awaiting inspection"
          icon={<Clock className="w-5 h-5 text-amber-500" />}
        />
        <KpiCard
          label="Oldest Waiting"
          value={oldestHours ? `${Math.floor(oldestHours)}h ${Math.floor((oldestHours % 1) * 60)}m` : '—'}
          subtext="SLA limit: 24h"
          icon={<AlertTriangle className="w-5 h-5 text-amber-500" />}
        />
        <KpiCard
          label="Avg. Review Time"
          value="—"
          subtext="Historical review duration is not recorded"
          icon={<ClipboardList className="w-5 h-5 text-emerald-500" />}
        />
        <KpiCard
          label="Re-submissions"
          value={queuePlans.filter((p) => p.version !== 'v1').length}
          subtext="Version v2 or v3"
          icon={<ShieldCheck className="w-5 h-5 text-brand-primary" />}
        />
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 bg-brand-surface border border-brand-border rounded-lg p-3">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-brand-text-muted absolute left-3 top-1/2 -translate-y-1/2" />
            <input
            type="text"
            placeholder="Search queue by plan name or submitter..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-brand-bg border border-brand-border text-body text-brand-text-primary placeholder:text-brand-text-muted focus:outline-none focus:ring-1 focus:ring-brand-primary"
          />
        </div>

        <div className="flex items-center gap-2 text-caption">
          <span className="text-overline text-brand-text-muted">SLA Status:</span>
          {['all', 'ontime', 'duesoon', 'overdue'].map((s) => (
            <button
              key={s}
              onClick={() => setSlaFilter(s)}
              className={`px-3 py-1 rounded-full font-medium transition-colors ${
                slaFilter === s
                  ? 'bg-brand-primary text-white font-semibold'
                  : 'bg-brand-bg text-brand-text-secondary border border-brand-border'
              }`}
            >
              {s === 'all' ? 'All SLA' : s === 'ontime' ? 'On Time' : s === 'duesoon' ? 'Due Soon' : 'Overdue'}
            </button>
          ))}
        </div>
      </div>

      {/* Queue Table */}
      <div className="overflow-x-auto bg-brand-surface border border-brand-border rounded-xl shadow-sm">
        <table className="w-full text-left text-body border-collapse">
          <thead>
            <tr className="border-b border-brand-border bg-brand-bg/60">
              <th className="py-3 px-4 text-overline text-brand-text-muted">Plan Name</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted">Submitter</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted">Version</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted text-right">Topology Size</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted">Submitted</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted">SLA Status</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted text-right">Review Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-brand-border text-caption">
            {error && <tr><td colSpan={7} className="p-6 text-center text-rose-600">{error}</td></tr>}
            {!error && loading && <tr><td colSpan={7} className="p-6 text-center text-brand-text-muted">Loading review queue…</td></tr>}
            {!error && !loading && queuePlans.length === 0 && <tr><td colSpan={7} className="p-6 text-center text-brand-text-muted">No plans match the selected filters.</td></tr>}
            {!loading && queuePlans.map((plan) => {
              const isOwnPlan =
                currentUser?.email.toLowerCase() === plan.ownerEmail.toLowerCase();
              const hours = plan.submitted_at ? Math.max(0, (Date.now() - new Date(plan.submitted_at).getTime()) / 3_600_000) : null;
              const slaLabel = hours === null ? 'Unknown' : hours >= 24 ? 'Overdue' : hours >= 18 ? 'Due Soon' : 'On Time';
              const slaStyle = slaLabel === 'Overdue' ? 'bg-rose-100 text-rose-800' : slaLabel === 'Due Soon' ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800';

              return (
                <tr
                  key={plan.id}
                  className={`hover:bg-brand-bg/30 transition-colors ${
                    isOwnPlan ? 'bg-amber-50/20 dark:bg-amber-950/10' : ''
                  }`}
                >
                  <td className="py-3 px-4">
                    <div className="font-bold text-body text-brand-text-primary">{plan.name}</div>
                    <span className="text-[11px] text-brand-text-muted">{plan.id}</span>
                  </td>

                  <td className="py-3 px-4 font-medium text-brand-text-primary">
                    {plan.owner}
                    {isOwnPlan && (
                      <span className="ml-1.5 text-[10px] font-bold px-1.5 py-0.2 rounded bg-amber-100 text-amber-800">
                        You
                      </span>
                    )}
                  </td>

                  <td className="py-3 px-4 font-mono font-bold">{plan.version}</td>

                  <td className="py-3 px-4 text-right font-mono tabular-nums text-brand-text-secondary">
                    {plan.routerCount}R • {plan.hostCount}H
                  </td>

                  <td className="py-3 px-4 text-brand-text-muted">{plan.submitted_at ? new Date(plan.submitted_at).toLocaleString() : '—'}</td>

                  <td className="py-3 px-4">
                    <span className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full ${slaStyle}`}>
                      <span className="w-1.5 h-1.5 rounded-full bg-current" />
                      {slaLabel}
                    </span>
                  </td>

                  <td className="py-3 px-4 text-right">
                    {isOwnPlan ? (
                      <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400 font-semibold text-[11px] cursor-not-allowed">
                        <Lock className="w-3.5 h-3.5" />
                        <span>Needs Another Admin</span>
                      </div>
                    ) : (
                      <button
                        onClick={() => navigate(`/admin/review/${plan.id}`)}
                        className="px-3.5 py-1.5 rounded-lg bg-brand-primary text-white text-caption font-semibold hover:opacity-90 flex items-center gap-1 ml-auto"
                      >
                        <span>Review</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
