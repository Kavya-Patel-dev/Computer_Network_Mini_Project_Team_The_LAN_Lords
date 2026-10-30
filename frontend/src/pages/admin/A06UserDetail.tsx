import React, { useEffect, useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { ApiUser, api, toUserProfile } from '../../api/client';
import { Plan } from '../../types/plan';
import { PageHeader } from '../../components/common/PageHeader';
import { StatusChip } from '../../components/common/StatusChip';
import { ArrowLeft, LogOut } from 'lucide-react';

type AuditEvent = { id: string; time: string; actor: string; action: string; target: string; result: string; details: Record<string, unknown> };
type AdminUserDetail = { user: ApiUser; plans: Plan[] };

export const A06UserDetail: React.FC = () => {
  const { navigate, currentPath } = useViewport();
  const userId = currentPath.split('/')[3] || '';
  const [user, setUser] = useState<ReturnType<typeof toUserProfile> | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'plans' | 'activity' | 'sessions'>('plans');

  const refresh = async () => {
    if (!userId) return;
    setLoading(true);
    try {
      const [detail, audit] = await Promise.all([
        api.get<AdminUserDetail>(`/admin/users/${encodeURIComponent(userId)}`),
        api.get<{ items: AuditEvent[] }>(`/admin/audit?user_id=${encodeURIComponent(userId)}&limit=100`),
      ]);
      setUser(toUserProfile({ ...detail.user, plansCount: detail.plans.length }));
      setPlans(detail.plans);
      setEvents(audit.items);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load this account.');
    } finally { setLoading(false); }
  };

  useEffect(() => { void refresh(); }, [userId]);

  const changeRole = async () => {
    if (!user) return;
    const role = user.role === 'user' ? 'admin' : 'user';
    try {
      const updated = await api.patch<ApiUser>(`/admin/users/${encodeURIComponent(user.id)}`, { role });
      setUser(toUserProfile({ ...updated, plansCount: user.plansCount }));
      setNotice(`Account role changed to ${role}.`);
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not update the account role.'); }
  };

  const revokeSessions = async () => {
    if (!user) return;
    try {
      const result = await api.post<{ revoked_sessions: number }>(`/admin/users/${encodeURIComponent(user.id)}/sessions/revoke`);
      setNotice(`${result.revoked_sessions} session(s) revoked.`);
      await refresh();
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not revoke sessions.'); }
  };

  if (loading && !user) return <div className="p-6 text-brand-text-muted">Loading account…</div>;
  if (error && !user) return <div role="alert" className="p-6 text-rose-600">{error}</div>;
  if (!user) return <div className="p-6 text-brand-text-muted">Account not found.</div>;

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <PageHeader
        title={`Operator Profile: ${user.name}`}
        subtitle={`Registered on ${user.createdAt} • Role: ${user.role.toUpperCase()}`}
        actions={
          <button
            onClick={() => navigate('/admin/users')}
            className="px-3.5 py-1.5 rounded-lg border border-brand-border bg-brand-surface hover:bg-brand-bg text-caption font-semibold flex items-center gap-1.5"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Directory</span>
          </button>
        }
      />
      {(error || notice) && <div role={error ? 'alert' : 'status'} className={`p-3 rounded-lg border text-caption ${error ? 'border-rose-300 text-rose-700' : 'border-emerald-300 text-emerald-700'}`}>{error || notice}</div>}

      {/* Summary Card */}
      <div className="p-6 bg-brand-surface border border-brand-border rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-sm">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-brand-primary text-white font-bold text-h2 flex items-center justify-center">
              {user.name.charAt(0)}
            </div>
            <div>
              <h3 className="text-h2 font-bold text-brand-text-primary">{user.name}</h3>
              <p className="font-mono text-caption text-brand-text-secondary">{user.email}</p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => void changeRole()}
            className="px-3.5 py-2 rounded-lg border border-brand-border bg-brand-bg hover:bg-brand-surface text-caption font-semibold"
          >
            Change Role ({user.role === 'user' ? 'make admin' : 'make user'})
          </button>
          <button
            onClick={() => void revokeSessions()}
            className="px-3.5 py-2 rounded-lg border border-rose-300 dark:border-rose-800 text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 text-caption font-semibold flex items-center gap-1"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Sign Out All Sessions</span>
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-brand-border text-body font-semibold">
        <button
          onClick={() => setActiveTab('plans')}
          className={`pb-3 px-4 border-b-2 transition-colors ${
            activeTab === 'plans'
              ? 'border-brand-primary text-brand-primary'
              : 'border-transparent text-brand-text-secondary hover:text-brand-text-primary'
          }`}
        >
          Owned Plans ({plans.length})
        </button>
        <button
          onClick={() => setActiveTab('activity')}
          className={`pb-3 px-4 border-b-2 transition-colors ${
            activeTab === 'activity'
              ? 'border-brand-primary text-brand-primary'
              : 'border-transparent text-brand-text-secondary hover:text-brand-text-primary'
          }`}
        >
          Activity Stream
        </button>
      </div>

      {/* Plans List */}
      {activeTab === 'plans' && (
        <div className="space-y-3">
          {plans.map((plan) => (
            <div
              key={plan.id}
              onClick={() => navigate(`/plans/${plan.id}`)}
              className="p-4 bg-brand-surface border border-brand-border hover:border-brand-primary/50 rounded-lg flex items-center justify-between cursor-pointer transition-colors"
            >
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-bold text-brand-text-primary">{plan.name}</span>
                  <StatusChip status={plan.status} />
                </div>
                <p className="text-caption text-brand-text-muted mt-0.5 font-mono">
                  {plan.routerCount} Routers • {plan.hostCount} Hosts • Updated {plan.updated_at}
                </p>
              </div>
              <span className="text-caption font-semibold text-brand-primary">View Plan →</span>
            </div>
          ))}
        </div>
      )}

      {/* Activity */}
      {activeTab === 'activity' && (
        <div className="p-5 bg-brand-surface border border-brand-border rounded-xl space-y-3 text-caption text-brand-text-secondary">
          {events.length ? events.map((event) => <p key={event.id}>• {new Date(event.time).toLocaleString()} · {event.action} · {event.target} · {event.result}</p>) : <p>No recorded activity for this account.</p>}
        </div>
      )}
      {activeTab === 'sessions' && (
        <div className="p-5 bg-brand-surface border border-brand-border rounded-xl space-y-3 text-caption text-brand-text-secondary">
          <p>{user.sessionsCount ?? 0} active session(s) currently stored for this account.</p>
          <p>Session identifiers and credentials are never shown in the admin console.</p>
          <button onClick={() => void revokeSessions()} className="px-3 py-2 rounded-lg border border-rose-300 text-rose-700 font-semibold">Revoke all sessions</button>
        </div>
      )}
    </div>
  );
};
