import React, { useEffect, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../context/ThemeContext';
import { useLocale } from '../../context/LocaleContext';
import { useViewport } from '../../context/ViewportContext';
import { 
  Search, 
  Bell, 
  Sun, 
  Moon, 
  User, 
  LogOut, 
  ArrowLeft, 
  MoreVertical, 
  ShieldCheck, 
  UserCheck, 
  Globe 
} from 'lucide-react';
import { api } from '../../api/client';
import { NotificationItem } from '../../types/user';

interface TopbarProps {
  pageTitle?: string;
  onSearch?: (query: string) => void;
}

export const Topbar: React.FC<TopbarProps> = ({ pageTitle, onSearch }) => {
  const { currentUser, role, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { language, setLanguage, t } = useLocale();
  const { mode, navigate, goBack } = useViewport();
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const [notifMenuOpen, setNotifMenuOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);

  const loadNotifications = async () => {
    try {
      const result = await api.get<{ items: Array<{ id: string; type: NotificationItem['type']; title: string; message: string; link_to: string; read: boolean; created_at: string }>; unread_count: number }>('/notifications?limit=5');
      setNotifications(result.items.map((item) => ({ id: item.id, type: item.type, title: item.title, message: item.message, linkTo: item.link_to, read: item.read, time: item.created_at })));
      setUnreadCount(result.unread_count);
    } catch {
      setNotifications([]);
      setUnreadCount(0);
    }
  };

  useEffect(() => { void loadNotifications(); }, [currentUser?.id]);

  // Mobile Top Bar
  if (mode === 'mobile') {
    return (
      <header className="sticky top-0 z-40 bg-brand-surface border-b border-brand-border px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={goBack}
            className="p-1 rounded hover:bg-brand-bg text-brand-text-secondary touch-target flex items-center justify-center focus:outline-none"
            aria-label="Go back"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h2 className="text-h3 font-semibold text-brand-text-primary truncate max-w-[200px]">
            {pageTitle || 'NetRoute AI'}
          </h2>
        </div>

        <div className="flex items-center gap-2">
          {/* Unread notification icon */}
          <button
            onClick={() => navigate('/notifications')}
            className="relative p-2 text-brand-text-secondary hover:text-brand-text-primary rounded"
            aria-label="Notifications"
          >
            <Bell className="w-5 h-5" />
            {unreadCount > 0 && (
              <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-rose-500" />
            )}
          </button>

          {/* Role badge */}
          <span
            className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${
              role === 'admin'
                ? 'bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300'
                : 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300'
            }`}
          >
            {role === 'admin' ? 'Admin' : 'User'}
          </span>
        </div>
      </header>
    );
  }

  // Desktop & Tablet Top Bar
  return (
    <header className="sticky top-0 z-40 bg-brand-surface border-b border-brand-border px-6 py-3.5 flex items-center justify-between">
      {/* Search Input */}
      <div className="flex-1 max-w-md">
        <div className="relative">
          <Search className="w-4 h-4 text-brand-text-muted absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search plans, topologies, runs, or IP addresses..."
            onChange={(e) => onSearch && onSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-1.5 rounded-lg bg-brand-bg border border-brand-border text-body text-brand-text-primary placeholder:text-brand-text-muted focus:outline-none focus:ring-2 focus:ring-brand-primary/40 focus:border-brand-primary"
          />
        </div>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-4">
        {/* Language Switch */}
        <div className="flex items-center gap-1.5 text-caption text-brand-text-secondary">
          <Globe className="w-4 h-4 text-brand-text-muted" />
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value as any)}
            className="bg-transparent text-brand-text-secondary font-medium focus:outline-none cursor-pointer"
          >
            <option value="en">English (EN)</option>
            <option value="gu">ગુજરાતી (GU)</option>
            <option value="hi">हिन्दी (HI)</option>
          </select>
        </div>

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="p-2 rounded-lg text-brand-text-secondary hover:text-brand-text-primary hover:bg-brand-bg transition-colors"
          title="Toggle color theme"
          aria-label="Toggle color theme"
        >
          {theme === 'light' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
        </button>

        {/* Notification Bell with Dropdown */}
        <div className="relative">
          <button
            onClick={() => setNotifMenuOpen(!notifMenuOpen)}
            className="relative p-2 rounded-lg text-brand-text-secondary hover:text-brand-text-primary hover:bg-brand-bg transition-colors"
            aria-label="View notifications"
          >
            <Bell className="w-4 h-4" />
            {unreadCount > 0 && (
              <span className="absolute top-1.5 right-1.5 min-w-[16px] h-4 rounded-full bg-rose-600 text-[10px] font-bold text-white flex items-center justify-center px-1">
                {unreadCount}
              </span>
            )}
          </button>

          {notifMenuOpen && (
            <div className="absolute right-0 top-10 z-50 w-80 bg-brand-surface border border-brand-border rounded-lg shadow-xl py-2">
              <div className="px-4 py-2 border-b border-brand-border flex items-center justify-between">
                <span className="text-overline text-brand-text-muted">Notifications</span>
                <button
                  onClick={() => {
                    setNotifMenuOpen(false);
                    navigate('/notifications');
                  }}
                  className="text-caption text-brand-primary hover:underline font-medium"
                >
                  View all
                </button>
              </div>
              <div className="divide-y divide-brand-border max-h-64 overflow-y-auto">
                {notifications.slice(0, 3).map((n) => (
                  <div
                    key={n.id}
                    onClick={() => {
                      if (!n.read) void api.post(`/notifications/${encodeURIComponent(n.id)}/read`).then(loadNotifications).catch(() => undefined);
                      setNotifMenuOpen(false);
                      navigate(n.linkTo);
                    }}
                    className="p-3 hover:bg-brand-bg cursor-pointer transition-colors"
                  >
                    <p className="text-caption font-semibold text-brand-text-primary">{n.title}</p>
                    <p className="text-caption text-brand-text-secondary line-clamp-1">{n.message}</p>
                    <span className="text-[11px] text-brand-text-muted mt-1 block">{n.time}</span>
                  </div>
                ))}
                {notifications.length === 0 && <p className="p-3 text-caption text-brand-text-muted">No notifications yet.</p>}
              </div>
            </div>
          )}
        </div>

        {/* Role Badge */}
        <div
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-caption font-semibold border ${
            role === 'admin'
              ? 'bg-purple-50 text-purple-800 border-purple-200 dark:bg-purple-950/40 dark:text-purple-300 dark:border-purple-800'
              : 'bg-blue-50 text-blue-800 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800'
          }`}
        >
          {role === 'admin' ? <ShieldCheck className="w-3.5 h-3.5" /> : <UserCheck className="w-3.5 h-3.5" />}
          <span>{role === 'admin' ? 'Admin Role' : 'User Role'}</span>
        </div>

        {/* Avatar Menu */}
        <div className="relative">
          <button
            onClick={() => setProfileMenuOpen(!profileMenuOpen)}
            className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-brand-bg transition-colors focus:outline-none"
          >
            <div className="w-8 h-8 rounded-full bg-brand-primary text-white font-bold text-caption flex items-center justify-center">
              {currentUser?.name.charAt(0) || 'U'}
            </div>
            <span className="text-body font-medium text-brand-text-primary hidden lg:inline">
              {currentUser?.name || 'Guest'}
            </span>
          </button>

          {profileMenuOpen && (
            <div className="absolute right-0 top-12 z-50 w-52 bg-brand-surface border border-brand-border rounded-lg shadow-xl py-1 text-body">
              <div className="px-4 py-2 border-b border-brand-border">
                <p className="font-semibold text-brand-text-primary">{currentUser?.name}</p>
                <p className="text-caption text-brand-text-muted truncate">{currentUser?.email}</p>
              </div>
              <button
                onClick={() => {
                  setProfileMenuOpen(false);
                  navigate('/profile');
                }}
                className="w-full text-left px-4 py-2 hover:bg-brand-bg flex items-center gap-2 text-brand-text-primary"
              >
                <User className="w-4 h-4 text-brand-text-muted" />
                Profile & Settings
              </button>
              <button
                onClick={() => {
                  setProfileMenuOpen(false);
                  void logout().catch(() => undefined);
                  navigate('/login');
                }}
                className="w-full text-left px-4 py-2 hover:bg-brand-bg flex items-center gap-2 text-rose-600"
              >
                <LogOut className="w-4 h-4" />
                Log out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
