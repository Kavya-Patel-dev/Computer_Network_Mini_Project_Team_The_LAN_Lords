import React, { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { PageHeader } from '../../components/common/PageHeader';
import { KpiCard } from '../../components/common/KpiCard';
import { ChartCard } from '../../components/common/ChartCard';
import { 
  BarChart, 
  Bar, 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer 
} from 'recharts';
import { Clock, CheckCircle2, AlertTriangle, Users, Download } from 'lucide-react';

export const A04StatsAnalytics: React.FC = () => {
  const [days, setDays] = useState<'7' | '30' | '90'>('30');
  const [analytics, setAnalytics] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.get(`/dashboard/admin/analytics?days=${days}`)
      .then((data) => { setAnalytics(data); setError(null); })
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load analytics.'));
  }, [days]);
  const decisionsData = analytics?.decisions ?? [];
  const commonTagsData = analytics?.feedback_tags ?? [];
  const reviewTimeTrend = analytics?.review_time_samples ?? [];
  const topSubmitters = analytics?.top_submitters ?? [];

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <PageHeader
        title="Administrative Review Analytics"
        subtitle="Operational metrics on queue turnover, governance throughput, and frequent topology issues."
        actions={
          <div className="flex items-center gap-1.5 bg-brand-surface border border-brand-border p-1 rounded-lg text-caption font-semibold">
            {(['7', '30', '90'] as const).map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={`px-3 py-1 rounded transition-colors ${
                  days === d ? 'bg-brand-primary text-white' : 'text-brand-text-secondary'
                }`}
              >
                Last {d} Days
              </button>
            ))}
          </div>
        }
      />

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="Pending Queue"
          value={analytics?.pending_reviews ?? '—'}
          subtext="Under SLA"
          icon={<Clock className="w-5 h-5 text-amber-500" />}
        />
        <KpiCard
          label="Approved Plans"
          value={analytics?.approved_count ?? '—'}
          unit="plans"
          subtext={`Last ${days} days`}
          icon={<CheckCircle2 className="w-5 h-5 text-emerald-500" />}
        />
        <KpiCard
          label="Average Review SLA"
          value={analytics?.average_review_minutes == null ? '—' : analytics.average_review_minutes.toFixed(1)}
          unit="min"
          subtext={analytics?.average_review_minutes == null ? 'No completed review timings recorded' : `Last ${days} days`}
          icon={<Clock className="w-5 h-5 text-blue-500" />}
        />
        <KpiCard
          label="Rejection Rate"
          value={analytics?.rejection_rate_percent == null ? '—' : analytics.rejection_rate_percent.toFixed(1)}
          unit="%"
          subtext={analytics?.rejection_rate_percent == null ? 'No review decisions recorded' : `Last ${days} days`}
          icon={<AlertTriangle className="w-5 h-5 text-rose-500" />}
        />
      {error && <div role="alert" className="p-3 rounded-lg border border-rose-300 text-rose-700">{error}</div>}
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Decisions per Week (Stacked Bars) */}
        <ChartCard
          title="Review Decisions per Week"
          subtitle="Distribution of approvals, changes requested, and rejections"
          tableData={decisionsData}
        >
          <div className="w-full h-[220px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={decisionsData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--color-border)" />
                <XAxis dataKey="week" tick={{ fill: 'var(--color-text-secondary)', fontSize: 12 }} />
                <YAxis tick={{ fill: 'var(--color-text-secondary)', fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="approved" stackId="a" fill="#16A34A" name="Approved" />
                <Bar dataKey="changes" stackId="a" fill="#EA580C" name="Changes Requested" />
                <Bar dataKey="rejected" stackId="a" fill="#DC2626" name="Rejected" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>

        {/* Most Common Flags / Tags */}
        <ChartCard
          title="Most Frequent Feedback Tags"
          subtitle="Top reasons cited during revision requests"
          tableData={commonTagsData}
        >
          <div className="w-full h-[220px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                layout="vertical"
                data={commonTagsData}
                margin={{ top: 10, right: 20, left: 40, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--color-border)" />
                <XAxis type="number" tick={{ fill: 'var(--color-text-secondary)', fontSize: 12 }} />
                <YAxis dataKey="tag" type="category" tick={{ fill: 'var(--color-text-secondary)', fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#2563EB" radius={[0, 4, 4, 0]} name="Citations" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>
      </div>

      {/* Top Submitters Table */}
      <div className="bg-brand-surface border border-brand-border rounded-xl p-5 space-y-3 shadow-sm">
        <h3 className="text-h3 font-bold text-brand-text-primary">Top Network Plan Operators</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-body border-collapse">
            <thead>
              <tr className="border-b border-brand-border bg-brand-bg/50">
                <th className="py-2.5 px-3 text-overline text-brand-text-muted">Operator</th>
                <th className="py-2.5 px-3 text-overline text-brand-text-muted">Role</th>
                <th className="py-2.5 px-3 text-overline text-brand-text-muted text-right">Plans Created</th>
                <th className="py-2.5 px-3 text-overline text-brand-text-muted text-right">Approvals</th>
                <th className="py-2.5 px-3 text-overline text-brand-text-muted">Approval Rate</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-brand-border text-caption">
              {topSubmitters.map((row: any) => <tr key={row.name}>
                <td className="py-2.5 px-3 font-bold text-brand-text-primary">{row.name}</td>
                <td className="py-2.5 px-3 font-mono text-[11px] uppercase">{row.role}</td>
                <td className="py-2.5 px-3 text-right font-mono tabular-nums">{row.plans}</td>
                <td className="py-2.5 px-3 text-right font-mono tabular-nums text-emerald-600 font-bold">{row.approvals}</td>
                <td className="py-2.5 px-3 font-mono text-emerald-600 font-bold">{row.plans ? `${(100 * row.approvals / row.plans).toFixed(1)}%` : '—'}</td>
              </tr>)}
              {!topSubmitters.length && <tr><td colSpan={5} className="p-4 text-center text-brand-text-muted">No plans were created in this period.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
