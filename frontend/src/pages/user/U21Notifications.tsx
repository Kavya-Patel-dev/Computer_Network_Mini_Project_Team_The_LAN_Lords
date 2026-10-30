import React, { useEffect, useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { api } from '../../api/client';
import { PageHeader } from '../../components/common/PageHeader';
import { EmptyState } from '../../components/common/EmptyState';
import { NotificationItem } from '../../types/user';
import {
  Bell, 
  CheckCheck, 
  CheckCircle2, 
  AlertCircle, 
  XCircle, 
  Play, 
  Clock, 
  Share2
} from 'lucide-react';

type ApiNotification = { id: string; type: NotificationItem['type']; title: string; message: string; link_to: string; read: boolean; created_at: string };

export const U21Notifications: React.FC = () => {
  const { navigate } = useViewport();
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [filter, setFilter] = useState<'all' | 'unread'>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    try {
      const response = await api.get<{ items: ApiNotification[] }>('/notifications?limit=100');
      setNotifications(response.items.map((n) => ({ id: n.id, type: n.type, title: n.title, message: n.message, linkTo: n.link_to, read: n.read, time: new Date(n.created_at).toLocaleString() })));
      setError(null);
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not load notifications.'); }
    finally { setLoading(false); }
  };
  useEffect(() => { void refresh(); }, []);

  const filteredNotifs = notifications.filter((n) => (filter === 'unread' ? !n.read : true));

  const markAllRead = async () => {
    try {
      await api.post('/notifications/read-all');
      setNotifications((rows) => rows.map((n) => ({ ...n, read: true })));
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not mark notifications read.'); }
  };

  const getIcon = (type: string) => {
    switch (type) {
      case 'plan_approved':
        return <CheckCircle2 className="w-5 h-5 text-emerald-600" />;
      case 'changes_requested':
        return <AlertCircle className="w-5 h-5 text-orange-600" />;
      case 'plan_rejected':
        return <XCircle className="w-5 h-5 text-rose-600" />;
      case 'simulation_completed':
        return <Play className="w-5 h-5 text-brand-primary" />;
      case 'review_pending':
        return <Clock className="w-5 h-5 text-amber-500" />;
      default:
        return <Share2 className="w-5 h-5 text-blue-500" />;
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <PageHeader
        title="Notifications"
        subtitle="Review decision updates, simulation completion alerts, and platform events."
        actions={
          <button
            onClick={markAllRead}
            className="px-3.5 py-2 rounded-lg border border-brand-border bg-brand-surface hover:bg-brand-bg text-brand-text-primary text-caption font-semibold flex items-center gap-1.5"
          >
            <CheckCheck className="w-4 h-4 text-brand-text-muted" />
            <span>Mark All Read</span>
          </button>
        }
      />

      {error && <div role="alert" className="p-3 rounded-lg border border-rose-300 text-rose-700">{error}</div>}
      {loading && <div className="p-4 text-brand-text-muted">Loading notifications…</div>}

      {/* Filter Chips */}
      <div className="flex items-center gap-2 text-caption font-semibold">
        <button
          onClick={() => setFilter('all')}
          className={`px-3 py-1 rounded-full ${
            filter === 'all'
              ? 'bg-brand-primary text-white'
              : 'bg-brand-surface text-brand-text-secondary border border-brand-border'
          }`}
        >
          All ({notifications.length})
        </button>
        <button
          onClick={() => setFilter('unread')}
          className={`px-3 py-1 rounded-full ${
            filter === 'unread'
              ? 'bg-brand-primary text-white'
              : 'bg-brand-surface text-brand-text-secondary border border-brand-border'
          }`}
        >
          Unread ({notifications.filter((n) => !n.read).length})
        </button>
      </div>

      {/* List */}
      {filteredNotifs.length === 0 ? (
        <EmptyState
          icon={<Bell className="w-6 h-6" />}
          title="No unread notifications"
          description="You are completely caught up with all network plan reviews and simulation events."
        />
      ) : (
        <div className="divide-y divide-brand-border bg-brand-surface border border-brand-border rounded-xl overflow-hidden shadow-sm">
          {filteredNotifs.map((n) => (
            <div
              key={n.id}
              onClick={() => {
                void api.post(`/notifications/${encodeURIComponent(n.id)}/read`).then(() => {
                  setNotifications((items) => items.map((item) => item.id === n.id ? { ...item, read: true } : item));
                  navigate(n.linkTo);
                }).catch((err) => setError(err instanceof Error ? err.message : 'Could not open notification.'));
              }}
              className={`p-4 flex items-start gap-3.5 cursor-pointer hover:bg-brand-bg transition-colors ${
                !n.read ? 'bg-blue-50/30 dark:bg-blue-950/20' : ''
              }`}
            >
              <div className="mt-0.5">{getIcon(n.type)}</div>
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <h4 className="text-body font-bold text-brand-text-primary">{n.title}</h4>
                    {!n.read && (
                      <span className="w-2 h-2 rounded-full bg-blue-600 shrink-0" />
                    )}
                  </div>
                  <span className="text-[11px] text-brand-text-muted font-mono">{n.time}</span>
                </div>
                <p className="text-caption text-brand-text-secondary mt-1">{n.message}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
