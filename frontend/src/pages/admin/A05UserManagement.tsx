import React, { useEffect, useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { useAuth } from '../../context/AuthContext';
import { ApiUser, api, toUserProfile } from '../../api/client';
import { PageHeader } from '../../components/common/PageHeader';
import { Search, UserPlus, MoreVertical, Shield, UserCheck, Lock, Eye } from 'lucide-react';

export const A05UserManagement: React.FC = () => {
  const { navigate, openOverlay } = useViewport();
  const { currentUser } = useAuth();
  const [search, setSearch] = useState('');
  const [users, setUsers] = useState<ReturnType<typeof toUserProfile>[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const query = new URLSearchParams({ limit: '100' });
    if (search.trim()) query.set('q', search.trim());
    setLoading(true);
    api.get<{ items: ApiUser[] }>(`/admin/users?${query.toString()}`)
      .then((data) => { setUsers(data.items.map(toUserProfile)); setError(null); })
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load users.'))
      .finally(() => setLoading(false));
  }, [search]);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <PageHeader
        title="User & Operator Directory"
        subtitle="Manage credentials, platform permissions, and access states."
        actions={
          <button
            onClick={() => openOverlay('O07')}
            className="px-4 py-2 rounded-lg bg-brand-primary text-white text-btn font-semibold hover:opacity-90 flex items-center gap-1.5 shadow-sm"
          >
            <UserPlus className="w-4 h-4 stroke-[2.5]" />
            <span>Invite User</span>
          </button>
        }
      />

      {/* Search */}
      <div className="bg-brand-surface border border-brand-border rounded-lg p-3 max-w-md">
        <div className="relative">
          <Search className="w-4 h-4 text-brand-text-muted absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search users by name or email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-brand-bg border border-brand-border text-body text-brand-text-primary placeholder:text-brand-text-muted focus:outline-none focus:ring-1 focus:ring-brand-primary"
          />
        </div>
      </div>

      {/* Users Table */}
      <div className="overflow-x-auto bg-brand-surface border border-brand-border rounded-xl shadow-sm">
        <table className="w-full text-left text-body border-collapse">
          <thead>
            <tr className="border-b border-brand-border bg-brand-bg/60">
              <th className="py-3 px-4 text-overline text-brand-text-muted">Operator Name</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted">Email</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted">Platform Role</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted">Account Status</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted text-right">Plans Count</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted">Last Active</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-brand-border text-caption">
            {error && <tr><td colSpan={7} className="p-6 text-center text-rose-600">{error}</td></tr>}
            {!error && loading && <tr><td colSpan={7} className="p-6 text-center text-brand-text-muted">Loading users…</td></tr>}
            {!error && !loading && users.length === 0 && <tr><td colSpan={7} className="p-6 text-center text-brand-text-muted">No users found.</td></tr>}
            {!loading && users.map((user) => {
              const isSelf = user.id === currentUser?.id;

              return (
                <tr key={user.id} className="hover:bg-brand-bg/30">
                  <td className="py-3 px-4 font-bold text-body text-brand-text-primary">
                    <div className="flex items-center gap-2">
                      <span>{user.name}</span>
                      {isSelf && (
                        <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-blue-100 text-blue-800">
                          You
                        </span>
                      )}
                    </div>
                  </td>

                  <td className="py-3 px-4 font-mono text-brand-text-secondary">{user.email}</td>

                  <td className="py-3 px-4">
                    <span
                      className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase ${
                        user.role === 'admin'
                          ? 'bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300'
                          : 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300'
                      }`}
                    >
                      {user.role}
                    </span>
                  </td>

                  <td className="py-3 px-4">
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold ${
                        user.status === 'active'
                          ? 'text-emerald-700 bg-emerald-50 dark:bg-emerald-950 dark:text-emerald-300'
                          : 'text-slate-500 bg-slate-100 dark:bg-slate-800'
                      }`}
                    >
                      <span className={`w-1.5 h-1.5 rounded-full ${user.status === 'active' ? 'bg-emerald-500' : 'bg-slate-400'}`} />
                      {user.status === 'active' ? 'Active' : 'Deactivated'}
                    </span>
                  </td>

                  <td className="py-3 px-4 text-right font-mono tabular-nums font-bold text-brand-text-primary">
                    {user.plansCount}
                  </td>

                  <td className="py-3 px-4 text-brand-text-muted">{user.lastActive}</td>

                  <td className="py-3 px-4 text-right">
                    {isSelf ? (
                      <span
                        className="inline-flex items-center gap-1 text-[11px] text-brand-text-muted cursor-not-allowed"
                        title="You cannot change your own role or status."
                      >
                        <Lock className="w-3.5 h-3.5" />
                        <span>Self Protected</span>
                      </span>
                    ) : (
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => navigate(`/admin/users/${user.id}`)}
                          className="px-2 py-1 rounded bg-brand-bg border border-brand-border text-caption font-semibold hover:bg-brand-surface"
                        >
                          View
                        </button>
                      </div>
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
