import React, { useEffect, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api/client';
import { useTheme } from '../../context/ThemeContext';
import { useLocale } from '../../context/LocaleContext';
import { useViewport } from '../../context/ViewportContext';
import { PageHeader } from '../../components/common/PageHeader';
import { 
  User, 
  Shield, 
  Sliders, 
  Bell, 
  Trash2, 
  CheckCircle2, 
  Lock 
} from 'lucide-react';

export const U22ProfileSettings: React.FC = () => {
  const { currentUser, role, refreshUser } = useAuth();
  const { theme, setTheme } = useTheme();
  const { language, setLanguage } = useLocale();
  const { openOverlay } = useViewport();

  const [activeTab, setActiveTab] = useState<'account' | 'security' | 'preferences' | 'notifications' | 'danger'>('account');
  const [name, setName] = useState(currentUser?.name || '');
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [sessions, setSessions] = useState<{ id: string; created_at: string; last_seen_at: string; current: boolean }[]>([]);

  useEffect(() => { if (currentUser) setName(currentUser.name); }, [currentUser?.id, currentUser?.name]);
  const loadSessions = async () => {
    try { setSessions((await api.get<{ items: typeof sessions }>('/users/me/sessions')).items); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not load sessions.'); }
  };
  useEffect(() => { if (activeTab === 'security') void loadSessions(); }, [activeTab]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await api.patch('/users/me', { name });
      await refreshUser();
      setSavedSuccess(true);
    } catch (err) { setError(err instanceof Error ? err.message : 'Profile update failed.'); setSavedSuccess(false); }
  };

  const updatePassword = async () => {
    if (newPassword !== confirmPassword) { setError('New password and confirmation do not match.'); return; }
    try {
      await api.post('/users/me/password', { current_password: currentPassword, new_password: newPassword });
      setCurrentPassword(''); setNewPassword(''); setConfirmPassword(''); setError(null); setSavedSuccess(true);
      await loadSessions();
    } catch (err) { setError(err instanceof Error ? err.message : 'Password update failed.'); }
  };

  const revokeOtherSessions = async () => {
    try {
      const result = await api.post<{ revoked_sessions: number }>('/users/me/sessions/revoke-others');
      setError(null);
      setSavedSuccess(result.revoked_sessions > 0);
      await loadSessions();
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not revoke other sessions.'); }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <PageHeader
        title="Profile & Preferences"
        subtitle="Manage personal account credentials, security sessions, and simulation defaults."
      />

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-brand-border overflow-x-auto text-body font-semibold">
        {[
          { id: 'account', label: 'Account', icon: <User className="w-4 h-4" /> },
          { id: 'security', label: 'Security & Sessions', icon: <Shield className="w-4 h-4" /> },
          { id: 'preferences', label: 'Preferences', icon: <Sliders className="w-4 h-4" /> },
          { id: 'notifications', label: 'Notifications', icon: <Bell className="w-4 h-4" /> },
          { id: 'danger', label: 'Danger Zone', icon: <Trash2 className="w-4 h-4 text-rose-500" /> },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id as any)}
            className={`pb-3 px-3.5 whitespace-nowrap border-b-2 flex items-center gap-2 transition-colors ${
              activeTab === t.id
                ? 'border-brand-primary text-brand-primary'
                : 'border-transparent text-brand-text-secondary hover:text-brand-text-primary'
            }`}
          >
            {t.icon}
            <span>{t.label}</span>
          </button>
        ))}
      </div>

      {savedSuccess && (
        <div className="p-3 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-800 rounded-lg flex items-center gap-2 text-emerald-800 dark:text-emerald-200 text-caption font-semibold">
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          <span>Profile configuration saved successfully.</span>
        </div>
      )}
      {error && <div role="alert" className="p-3 rounded-lg border border-rose-300 text-rose-700 text-caption">{error}</div>}

      {/* Tab 1: Account */}
      {activeTab === 'account' && (
        <form onSubmit={handleSave} className="bg-brand-surface border border-brand-border rounded-xl p-6 space-y-4 shadow-sm">
          <div>
            <label className="text-label text-brand-text-primary block mb-1">Full Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 bg-brand-bg border border-brand-border rounded-lg text-body"
            />
          </div>

          <div>
            <label className="text-label text-brand-text-primary block mb-1">Email Address</label>
            <input
              type="email"
              readOnly
              value={currentUser?.email || ''}
              className="w-full px-3 py-2 bg-brand-bg border border-brand-border rounded-lg text-body text-brand-text-muted cursor-not-allowed font-mono"
            />
          </div>

          <div>
            <label className="text-label text-brand-text-primary block mb-1">Platform Role</label>
            <span
              className={`inline-block px-3 py-1 rounded-full text-caption font-bold uppercase ${
                role === 'admin'
                  ? 'bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300 border border-purple-200'
                  : 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300 border border-blue-200'
              }`}
            >
              {role === 'admin' ? 'Administrator' : 'Standard User'}
            </span>
          </div>

          <div className="pt-4 border-t border-brand-border flex justify-end">
            <button
              type="submit"
              className="px-5 py-2 rounded-lg bg-brand-primary text-white text-btn font-semibold hover:opacity-90"
            >
              Save Changes
            </button>
          </div>
        </form>
      )}

      {/* Tab 2: Security */}
      {activeTab === 'security' && (
        <div className="space-y-6">
          <div className="bg-brand-surface border border-brand-border rounded-xl p-6 space-y-4 shadow-sm">
            <h3 className="text-h3 font-bold text-brand-text-primary">Change Password</h3>
            <div className="space-y-3 max-w-md">
              <input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} placeholder="Current password" className="w-full px-3 py-2 bg-brand-bg border border-brand-border rounded-lg text-body" />
              <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="New password" className="w-full px-3 py-2 bg-brand-bg border border-brand-border rounded-lg text-body" />
              <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} placeholder="Confirm new password" className="w-full px-3 py-2 bg-brand-bg border border-brand-border rounded-lg text-body" />
              <button
                type="button"
                onClick={() => void updatePassword()}
                className="px-4 py-2 rounded-lg bg-brand-primary text-white text-caption font-semibold"
              >
                Update Password
              </button>
            </div>
          </div>

          <div className="bg-brand-surface border border-brand-border rounded-xl p-6 space-y-4 shadow-sm">
            <h3 className="text-h3 font-bold text-brand-text-primary">Active Sessions</h3>
            <div className="space-y-3 text-caption">
              {sessions.map((session) => <div key={session.id} className="p-3 bg-brand-bg border border-brand-border rounded-lg flex items-center justify-between"><div><p className="font-semibold text-brand-text-primary">{session.current ? 'Current session' : 'Other signed-in session'}</p><p className="text-brand-text-muted font-mono">Created {new Date(session.created_at).toLocaleString()} · Last seen {new Date(session.last_seen_at).toLocaleString()}</p></div>{session.current && <span className="text-emerald-600 font-bold">This Device</span>}</div>)}
              {!sessions.length && <p className="text-brand-text-muted">No session details are available.</p>}
              <button onClick={() => void revokeOtherSessions()} disabled={!sessions.some((session) => !session.current)} className="text-rose-600 font-semibold hover:underline disabled:opacity-50">Sign out other sessions</button>
            </div>
          </div>
        </div>
      )}

      {/* Tab 3: Preferences */}
      {activeTab === 'preferences' && (
        <div className="bg-brand-surface border border-brand-border rounded-xl p-6 space-y-6 shadow-sm">
          <div>
            <label className="text-label text-brand-text-primary block mb-2">Display Theme</label>
            <div className="flex gap-3">
              {[
                { id: 'light', label: 'Light' },
                { id: 'dark', label: 'Dark' },
              ].map((th) => (
                <button
                  key={th.id}
                  onClick={() => setTheme(th.id as any)}
                  className={`px-4 py-2 rounded-lg border font-semibold text-caption transition-colors ${
                    theme === th.id
                      ? 'bg-brand-primary text-white border-brand-primary'
                      : 'bg-brand-bg text-brand-text-secondary border-brand-border'
                  }`}
                >
                  {th.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-label text-brand-text-primary block mb-2">Interface Language</label>
            <div className="flex gap-3">
              {[
                { id: 'en', label: 'English (EN)' },
                { id: 'gu', label: 'ગુજરાતી (GU)' },
                { id: 'hi', label: 'हिन्दी (HI)' },
              ].map((lng) => (
                <button
                  key={lng.id}
                  onClick={() => setLanguage(lng.id as any)}
                  className={`px-4 py-2 rounded-lg border font-semibold text-caption transition-colors ${
                    language === lng.id
                      ? 'bg-brand-primary text-white border-brand-primary'
                      : 'bg-brand-bg text-brand-text-secondary border-brand-border'
                  }`}
                >
                  {lng.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Tab 4: Notifications */}
      {activeTab === 'notifications' && (
        <div className="bg-brand-surface border border-brand-border rounded-xl p-6 space-y-4 shadow-sm">
          <h3 className="text-h3 font-bold text-brand-text-primary">Event Delivery Settings</h3>
          <div className="space-y-3 text-caption text-brand-text-secondary">
            <label className="flex items-center justify-between p-2.5 bg-brand-bg rounded border border-brand-border cursor-pointer">
              <span>Notify me when plan review decision is posted</span>
              <input type="checkbox" defaultChecked className="rounded text-brand-primary" />
            </label>
            <label className="flex items-center justify-between p-2.5 bg-brand-bg rounded border border-brand-border cursor-pointer">
              <span>Notify me when multi-scenario simulation completes</span>
              <input type="checkbox" defaultChecked className="rounded text-brand-primary" />
            </label>
            <label className="flex items-center justify-between p-2.5 bg-brand-bg rounded border border-brand-border cursor-pointer">
              <span>Notify me before shared token links expire</span>
              <input type="checkbox" defaultChecked className="rounded text-brand-primary" />
            </label>
          </div>
        </div>
      )}

      {/* Tab 5: Danger Zone */}
      {activeTab === 'danger' && (
        <div className="bg-rose-50/40 dark:bg-rose-950/20 border border-rose-300 dark:border-rose-800 rounded-xl p-6 space-y-4 shadow-sm">
          <h3 className="text-h3 font-bold text-rose-600">Danger Zone</h3>
          <p className="text-body text-rose-900 dark:text-rose-200">
            Deleting your account will irreversibly remove your saved topologies, simulation run telemetry, and shared links.
          </p>
          <button
            onClick={() => openOverlay('O15')}
            className="px-4 py-2 rounded-lg bg-rose-600 text-white text-caption font-semibold hover:bg-rose-700"
          >
            Permanently Delete Account
          </button>
        </div>
      )}
    </div>
  );
};
