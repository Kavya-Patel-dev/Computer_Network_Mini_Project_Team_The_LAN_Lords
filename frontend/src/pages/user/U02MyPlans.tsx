import React, { useEffect, useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { api } from '../../api/client';
import { Plan, PlanStatus } from '../../types/plan';
import { PageHeader } from '../../components/common/PageHeader';
import { PlanCard } from '../../components/common/PlanCard';
import { StatusChip } from '../../components/common/StatusChip';
import { EmptyState } from '../../components/common/EmptyState';
import { PageSkeleton } from '../../components/common/SkeletonLoader';
import { ErrorBanner } from '../../components/common/ErrorBanner';
import { 
  Plus, 
  Search, 
  LayoutGrid, 
  List, 
  Filter, 
  MoreVertical, 
  ArrowUpDown, 
  Layers 
} from 'lucide-react';

export const U02MyPlans: React.FC = () => {
  const { navigate } = useViewport();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [sortBy, setSortBy] = useState<'updated' | 'name' | 'status'>('updated');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  const loadPlans = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const response = await api.get<{ items: Plan[] }>('/records?limit=100');
      setPlans(response.items);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : 'Could not load plans.');
    } finally {
      setLoading(false);
    }
  };

  const duplicatePlan = async (plan: Plan) => {
    try {
      const copy = await api.post<Plan>('/records', {
        name: `${plan.name} copy`,
        description: plan.description || '',
        topology: plan.topology,
        traffic_preset: plan.trafficPreset,
        flows: plan.flows,
        selected_scenarios: plan.selectedScenarios,
      });
      await loadPlans();
      navigate(`/plans/${encodeURIComponent(copy.id)}/edit/form`);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : 'Could not duplicate this plan.');
    }
  };

  useEffect(() => { void loadPlans(); }, []);
  useEffect(() => {
    const refreshPlans = () => { void loadPlans(); };
    window.addEventListener('lanlords:plans-changed', refreshPlans);
    return () => window.removeEventListener('lanlords:plans-changed', refreshPlans);
  }, []);

  if (loading) return <PageSkeleton />;
  if (loadError) {
    return (
      <div className="p-6">
        <ErrorBanner
          message={loadError}
          onRetry={() => void loadPlans()}
        />
      </div>
    );
  }

  const filteredPlans = plans.filter((p) => {
    const matchesSearch =
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (p.description || '').toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || p.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <PageHeader
        title="My Plans"
        subtitle="Manage, edit, and track status of your defined network topologies."
        actions={
          <button
            onClick={() => navigate('/plans/new')}
            className="px-4 py-2 rounded-lg bg-brand-primary text-white text-btn font-semibold hover:opacity-90 flex items-center gap-1.5 shadow-sm touch-target"
          >
            <Plus className="w-4 h-4 stroke-[2.5]" />
            <span>New Plan</span>
          </button>
        }
      />

      {/* Filter and Search Bar */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 bg-brand-surface border border-brand-border rounded-lg p-3">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-brand-text-muted absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search plans by name or description..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-brand-bg border border-brand-border text-body text-brand-text-primary placeholder:text-brand-text-muted focus:outline-none focus:ring-1 focus:ring-brand-primary"
          />
        </div>

        {/* Status Chips Filter */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 md:pb-0 text-caption">
          {['all', 'Draft', 'Pending Review', 'Changes Requested', 'Approved', 'Completed'].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1 rounded-full whitespace-nowrap font-medium transition-colors ${
                statusFilter === st
                  ? 'bg-brand-primary text-white font-semibold'
                  : 'bg-brand-bg text-brand-text-secondary hover:text-brand-text-primary border border-brand-border'
              }`}
            >
              {st === 'all' ? 'All Plans' : st}
            </button>
          ))}
        </div>

        {/* View Toggle & Sort */}
        <div className="flex items-center gap-2 shrink-0">
          <div className="flex items-center gap-1 bg-brand-bg border border-brand-border rounded-lg p-1 text-caption">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-1.5 rounded ${viewMode === 'grid' ? 'bg-brand-surface text-brand-primary shadow-sm' : 'text-brand-text-muted'}`}
              title="Grid View"
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-1.5 rounded ${viewMode === 'list' ? 'bg-brand-surface text-brand-primary shadow-sm' : 'text-brand-text-muted'}`}
              title="List Table View"
            >
              <List className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Plan Cards Grid or Table */}
      {filteredPlans.length === 0 ? (
        <EmptyState
          icon={<Layers className="w-6 h-6" />}
          title={searchQuery ? 'No matching plans found' : 'No plans yet'}
          description={
            searchQuery
              ? 'Try adjusting your search terms or filter criteria.'
              : 'Start by drawing your network canvas or choosing an automated generator.'
          }
          actionLabel="Create a Plan"
          onAction={() => navigate('/plans/new')}
        />
      ) : viewMode === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredPlans.map((plan) => (
            <PlanCard key={plan.id} plan={plan} onDuplicate={(source) => void duplicatePlan(source)} />
          ))}
        </div>
      ) : (
        /* Table View */
        <div className="overflow-x-auto bg-brand-surface border border-brand-border rounded-lg shadow-sm">
          <table className="w-full text-left text-body border-collapse">
            <thead>
              <tr className="border-b border-brand-border bg-brand-bg/60">
                <th className="py-3 px-4 text-overline text-brand-text-muted">Plan Name</th>
                <th className="py-3 px-4 text-overline text-brand-text-muted">Status</th>
                <th className="py-3 px-4 text-overline text-brand-text-muted">Version</th>
                <th className="py-3 px-4 text-overline text-brand-text-muted text-right">Routers</th>
                <th className="py-3 px-4 text-overline text-brand-text-muted text-right">Hosts</th>
                <th className="py-3 px-4 text-overline text-brand-text-muted">Updated</th>
                <th className="py-3 px-4 text-overline text-brand-text-muted text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-brand-border">
              {filteredPlans.map((plan) => (
                <tr
                  key={plan.id}
                  onClick={() => navigate(`/plans/${plan.id}`)}
                  className="hover:bg-brand-bg/40 cursor-pointer transition-colors"
                >
                  <td className="py-3 px-4 font-semibold text-brand-text-primary">
                    {plan.name}
                  </td>
                  <td className="py-3 px-4">
                    <StatusChip status={plan.status} />
                  </td>
                  <td className="py-3 px-4 font-mono text-caption text-brand-text-secondary">
                    {plan.version}
                  </td>
                  <td className="py-3 px-4 text-right font-mono text-brand-text-secondary tabular-nums">
                    {plan.routerCount}
                  </td>
                  <td className="py-3 px-4 text-right font-mono text-brand-text-secondary tabular-nums">
                    {plan.hostCount}
                  </td>
                  <td className="py-3 px-4 text-caption text-brand-text-muted">
                    {plan.updated_at.split(' ')[0]}
                  </td>
                  <td className="py-3 px-4 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate(`/plans/${plan.id}`);
                      }}
                      className="px-2.5 py-1 rounded bg-brand-bg border border-brand-border text-caption font-semibold text-brand-primary hover:bg-brand-surface"
                    >
                      Open
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
