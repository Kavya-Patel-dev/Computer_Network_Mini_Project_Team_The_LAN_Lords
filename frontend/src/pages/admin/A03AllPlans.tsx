import React, { useEffect, useMemo, useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { api } from '../../api/client';
import { Plan } from '../../types/plan';
import { PageHeader } from '../../components/common/PageHeader';
import { StatusChip } from '../../components/common/StatusChip';
import { Search, Download, Plus, Eye } from 'lucide-react';

export const A03AllPlans: React.FC = () => {
  const { navigate } = useViewport();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams({ limit: '100' });
    if (search.trim()) params.set('search', search.trim());
    if (statusFilter !== 'all') params.set('status', statusFilter);
    setLoading(true);
    api.get<{ items: Plan[] }>(`/records?${params.toString()}`)
      .then((data) => { setPlans(data.items); setError(null); })
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load plans.'))
      .finally(() => setLoading(false));
  }, [search, statusFilter]);

  const filtered = useMemo(() => plans, [plans]);
  const exportCsv = () => {
    const rows = [['name', 'owner', 'email', 'status', 'version', 'routers', 'hosts', 'updated_at'], ...filtered.map((p) => [p.name, p.owner, p.ownerEmail, p.status, p.version, String(p.routerCount), String(p.hostCount), p.updated_at])];
    const csv = rows.map((row) => row.map((cell) => `"${cell.replace(/"/g, '""')}"`).join(',')).join('\r\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'plans.csv';
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <PageHeader
        title="All System Plans"
        subtitle="Global inventory of all network architectures across all operators."
        actions={
          <div className="flex items-center gap-2">
            <button
            onClick={exportCsv}
              className="px-3.5 py-2 rounded-lg border border-brand-border bg-brand-surface hover:bg-brand-bg text-caption font-semibold flex items-center gap-1.5"
            >
              <Download className="w-4 h-4 text-brand-text-muted" />
              <span>Export CSV</span>
            </button>
            <button
              onClick={() => navigate('/plans/new')}
              className="px-4 py-2 rounded-lg bg-brand-primary text-white text-btn font-semibold hover:opacity-90 flex items-center gap-1.5 shadow-sm"
            >
              <Plus className="w-4 h-4 stroke-[2.5]" />
              <span>New Admin Plan</span>
            </button>
          </div>
        }
      />

      {/* Filter and Search Bar */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 bg-brand-surface border border-brand-border rounded-lg p-3">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-brand-text-muted absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by plan name or owner..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-brand-bg border border-brand-border text-body text-brand-text-primary placeholder:text-brand-text-muted focus:outline-none focus:ring-1 focus:ring-brand-primary"
          />
        </div>

        <div className="flex items-center gap-1.5 overflow-x-auto text-caption">
          {['all', 'Draft', 'Pending Review', 'Changes Requested', 'Approved', 'Rejected'].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1 rounded-full whitespace-nowrap font-medium transition-colors ${
                statusFilter === st
                  ? 'bg-brand-primary text-white font-semibold'
                  : 'bg-brand-bg text-brand-text-secondary hover:text-brand-text-primary border border-brand-border'
              }`}
            >
              {st === 'all' ? 'All Statuses' : st}
            </button>
          ))}
        </div>
      </div>

      {/* Global Plans Table */}
      <div className="overflow-x-auto bg-brand-surface border border-brand-border rounded-xl shadow-sm">
        <table className="w-full text-left text-body border-collapse">
          <thead>
            <tr className="border-b border-brand-border bg-brand-bg/60">
              <th className="py-3 px-4 text-overline text-brand-text-muted">Plan Name</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted">Owner</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted">Status</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted">Version</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted text-right">Routers</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted text-right">Hosts</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted">Last Updated</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-brand-border text-caption">
            {error && <tr><td colSpan={8} className="p-6 text-center text-rose-600">{error}</td></tr>}
            {!error && loading && <tr><td colSpan={8} className="p-6 text-center text-brand-text-muted">Loading plans…</td></tr>}
            {!error && !loading && filtered.length === 0 && <tr><td colSpan={8} className="p-6 text-center text-brand-text-muted">No plans match the selected filters.</td></tr>}
            {!loading && filtered.map((plan) => (
              <tr
                key={plan.id}
                onClick={() => navigate(`/plans/${plan.id}`)}
                className="hover:bg-brand-bg/30 cursor-pointer transition-colors"
              >
                <td className="py-3 px-4 font-bold text-body text-brand-text-primary">{plan.name}</td>
                <td className="py-3 px-4 font-medium text-brand-text-secondary">{plan.owner}</td>
                <td className="py-3 px-4">
                  <StatusChip status={plan.status} />
                </td>
                <td className="py-3 px-4 font-mono">{plan.version}</td>
                <td className="py-3 px-4 text-right font-mono tabular-nums">{plan.routerCount}</td>
                <td className="py-3 px-4 text-right font-mono tabular-nums">{plan.hostCount}</td>
                <td className="py-3 px-4 text-brand-text-muted">{new Date(plan.updated_at).toLocaleDateString()}</td>
                <td className="py-3 px-4 text-right">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      navigate(`/plans/${plan.id}`);
                    }}
                    className="p-1 text-brand-text-muted hover:text-brand-primary"
                    title="View plan"
                  >
                    <Eye className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
