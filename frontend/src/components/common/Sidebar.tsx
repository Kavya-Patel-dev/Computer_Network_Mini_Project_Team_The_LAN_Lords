import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useViewport } from '../../context/ViewportContext';
import { useLocale } from '../../context/LocaleContext';
import {
  LayoutDashboard,
  Layers,
  PlusCircle,
  BarChart3,
  Bell,
  User,
  ClipboardList,
  Users,
  History,
  Settings,
  ShieldAlert,
  BrainCircuit,
  ChevronLeft,
  ChevronRight,
  MoreHorizontal,
  Plus,
  Home,
  X
} from 'lucide-react';

export const Sidebar: React.FC = () => {
  const { role } = useAuth();
  const { mode, currentPath, navigate } = useViewport();
  const { t } = useLocale();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileMoreOpen, setMobileMoreOpen] = useState(false);

  // User navigation
  const userNav = [
    { path: '/dashboard', label: t('dashboard'), icon: <LayoutDashboard className="w-5 h-5" /> },
    { path: '/plans', label: t('myPlans'), icon: <Layers className="w-5 h-5" /> },
    { path: '/plans/new', label: t('newPlan'), icon: <PlusCircle className="w-5 h-5 text-brand-primary" /> },
    { path: '/results', label: t('results'), icon: <BarChart3 className="w-5 h-5" /> },
    { path: '/notifications', label: t('notifications'), icon: <Bell className="w-5 h-5" /> },
    { path: '/profile', label: t('profile'), icon: <User className="w-5 h-5" /> },
  ];

  // Admin navigation
  const adminNav = [
    { path: '/admin/queue', label: t('reviewQueue'), icon: <ClipboardList className="w-5 h-5 text-amber-500" /> },
    { path: '/admin/plans', label: t('allPlans'), icon: <Layers className="w-5 h-5" /> },
    { path: '/results', label: t('results'), icon: <BarChart3 className="w-5 h-5" /> },
    { path: '/admin/stats', label: t('stats'), icon: <BarChart3 className="w-5 h-5" /> },
    { path: '/admin/users', label: t('users'), icon: <Users className="w-5 h-5" /> },
    { path: '/admin/audit', label: t('auditLog'), icon: <History className="w-5 h-5" /> },
    { path: '/admin/settings', label: t('settings'), icon: <Settings className="w-5 h-5" /> },
    { path: '/admin/permissions', label: t('permissions'), icon: <ShieldAlert className="w-5 h-5" /> },
    { path: '/admin/model', label: t('modelInfo'), icon: <BrainCircuit className="w-5 h-5 text-emerald-500" /> },
    { path: '/notifications', label: t('notifications'), icon: <Bell className="w-5 h-5" /> },
    { path: '/profile', label: t('profile'), icon: <User className="w-5 h-5" /> },
  ];

  const navItems = role === 'admin' ? adminNav : userNav;

  // Mobile Bottom Tab Bar (Section 5)
  if (mode === 'mobile') {
    return (
      <>
        {/* Mobile FAB for primary action */}
        {role !== 'admin' && (
          <button
            onClick={() => navigate('/plans/new')}
            className="fixed right-5 bottom-20 z-40 w-14 h-14 rounded-full bg-brand-primary text-white shadow-xl flex items-center justify-center hover:opacity-95 active:scale-95 transition-all touch-target"
            aria-label="Create new plan"
          >
            <Plus className="w-6 h-6 stroke-[2.5]" />
          </button>
        )}

        {/* Bottom Tab Bar */}
        <nav className="fixed bottom-0 left-0 right-0 z-40 bg-brand-surface border-t border-brand-border px-2 py-1.5 flex items-center justify-around shadow-lg">
          {role === 'admin' ? (
            <>
              <button
                onClick={() => navigate('/admin/queue')}
                className={`flex flex-col items-center py-1 px-3 text-[11px] font-medium transition-colors ${
                  currentPath.startsWith('/admin/queue') ? 'text-brand-primary font-bold' : 'text-brand-text-muted'
                }`}
              >
                <ClipboardList className="w-5 h-5" />
                <span>Queue</span>
              </button>
              <button
                onClick={() => navigate('/admin/plans')}
                className={`flex flex-col items-center py-1 px-3 text-[11px] font-medium transition-colors ${
                  currentPath === '/admin/plans' ? 'text-brand-primary font-bold' : 'text-brand-text-muted'
                }`}
              >
                <Layers className="w-5 h-5" />
                <span>Plans</span>
              </button>
              <button
                onClick={() => navigate('/admin/stats')}
                className={`flex flex-col items-center py-1 px-3 text-[11px] font-medium transition-colors ${
                  currentPath === '/admin/stats' ? 'text-brand-primary font-bold' : 'text-brand-text-muted'
                }`}
              >
                <BarChart3 className="w-5 h-5" />
                <span>Stats</span>
              </button>
              <button
                onClick={() => navigate('/admin/users')}
                className={`flex flex-col items-center py-1 px-3 text-[11px] font-medium transition-colors ${
                  currentPath.startsWith('/admin/users') ? 'text-brand-primary font-bold' : 'text-brand-text-muted'
                }`}
              >
                <Users className="w-5 h-5" />
                <span>Users</span>
              </button>
              <button
                onClick={() => setMobileMoreOpen(true)}
                className="flex flex-col items-center py-1 px-3 text-[11px] font-medium text-brand-text-muted hover:text-brand-text-primary"
              >
                <MoreHorizontal className="w-5 h-5" />
                <span>More</span>
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => navigate('/dashboard')}
                className={`flex flex-col items-center py-1 px-3 text-[11px] font-medium transition-colors ${
                  currentPath === '/dashboard' ? 'text-brand-primary font-bold' : 'text-brand-text-muted'
                }`}
              >
                <Home className="w-5 h-5" />
                <span>Home</span>
              </button>
              <button
                onClick={() => navigate('/plans')}
                className={`flex flex-col items-center py-1 px-3 text-[11px] font-medium transition-colors ${
                  currentPath === '/plans' ? 'text-brand-primary font-bold' : 'text-brand-text-muted'
                }`}
              >
                <Layers className="w-5 h-5" />
                <span>Plans</span>
              </button>
              <button
                onClick={() => navigate('/plans/new')}
                className="flex flex-col items-center py-1 px-3 text-[11px] font-bold text-brand-primary"
              >
                <PlusCircle className="w-6 h-6" />
                <span>New</span>
              </button>
              <button
                onClick={() => navigate('/results')}
                className={`flex flex-col items-center py-1 px-3 text-[11px] font-medium transition-colors ${
                  currentPath.startsWith('/results') ? 'text-brand-primary font-bold' : 'text-brand-text-muted'
                }`}
              >
                <BarChart3 className="w-5 h-5" />
                <span>Results</span>
              </button>
              <button
                onClick={() => navigate('/profile')}
                className={`flex flex-col items-center py-1 px-3 text-[11px] font-medium transition-colors ${
                  currentPath === '/profile' ? 'text-brand-primary font-bold' : 'text-brand-text-muted'
                }`}
              >
                <User className="w-5 h-5" />
                <span>Profile</span>
              </button>
            </>
          )}
        </nav>

        {/* Mobile Admin "More" Bottom Sheet */}
        {mobileMoreOpen && (
          <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex flex-col justify-end">
            <div className="bg-brand-surface border-t border-brand-border rounded-t-2xl p-5 max-h-[75vh] overflow-y-auto space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-brand-border">
                <span className="text-overline text-brand-text-muted">Admin Administration</span>
                <button
                  onClick={() => setMobileMoreOpen(false)}
                  className="p-1 rounded-full text-brand-text-muted hover:text-brand-text-primary"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="grid grid-cols-2 gap-2 text-body">
                {adminNav.slice(2).map((item) => (
                  <button
                    key={item.path}
                    onClick={() => {
                      setMobileMoreOpen(false);
                      navigate(item.path);
                    }}
                    className="p-3 bg-brand-bg border border-brand-border rounded-lg flex items-center gap-2.5 text-brand-text-primary text-caption font-semibold"
                  >
                    {item.icon}
                    <span>{item.label}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </>
    );
  }

  // Tablet 768: Icon-only sidebar
  if (mode === 'tablet') {
    return (
      <aside className="w-16 bg-brand-surface border-r border-brand-border min-h-screen p-2 flex flex-col items-center justify-between shrink-0">
        <div className="w-full flex flex-col items-center space-y-3 pt-2">
          <div className="w-10 h-10 rounded-lg bg-brand-primary text-white flex items-center justify-center font-bold text-h3 shadow-sm mb-4">
            NR
          </div>
          {navItems.map((item) => {
            const isActive = currentPath === item.path || currentPath.startsWith(item.path + '/');
            return (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                className={`w-11 h-11 rounded-lg flex items-center justify-center transition-colors touch-target ${
                  isActive
                    ? 'bg-brand-primary text-white font-semibold'
                    : 'text-brand-text-secondary hover:bg-brand-bg hover:text-brand-text-primary'
                }`}
                title={item.label}
              >
                {item.icon}
              </button>
            );
          })}
        </div>
      </aside>
    );
  }

  // Desktop 1440: Collapsible left sidebar (240px)
  return (
    <aside
      className={`bg-brand-surface border-r border-brand-border min-h-screen transition-all flex flex-col justify-between shrink-0 ${
        collapsed ? 'w-16' : 'w-60'
      }`}
    >
      <div className="p-4">
        {/* Brand Logo & Name */}
        <div className="flex items-center justify-between mb-6 pb-3 border-b border-brand-border">
          {!collapsed && (
            <div
              onClick={() => navigate(role === 'admin' ? '/admin/queue' : '/dashboard')}
              className="flex items-center gap-2.5 cursor-pointer"
            >
              <div className="w-8 h-8 rounded-lg bg-brand-primary text-white flex items-center justify-center font-bold text-h3 shadow-sm">
                NR
              </div>
              <div>
                <span className="font-bold text-h3 text-brand-text-primary tracking-tight block">
                  NetRoute AI
                </span>
                <span className="text-[10px] text-brand-text-muted font-mono uppercase tracking-wider block">
                  {role === 'admin' ? 'Admin Console' : 'Simulation Studio'}
                </span>
              </div>
            </div>
          )}

          {collapsed && (
            <div className="mx-auto w-8 h-8 rounded-lg bg-brand-primary text-white flex items-center justify-center font-bold text-h3 shadow-sm">
              NR
            </div>
          )}

          <button
            onClick={() => setCollapsed(!collapsed)}
            className="p-1 rounded text-brand-text-muted hover:text-brand-text-primary hover:bg-brand-bg transition-colors"
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>

        {/* Navigation List */}
        <nav className="space-y-1">
          {navItems.map((item) => {
            const isActive = currentPath === item.path || (item.path !== '/' && currentPath.startsWith(item.path + '/'));
            return (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-body transition-colors ${
                  isActive
                    ? 'bg-brand-primary text-white font-semibold shadow-sm'
                    : 'text-brand-text-secondary hover:bg-brand-bg hover:text-brand-text-primary'
                } ${collapsed ? 'justify-center px-0' : ''}`}
                title={collapsed ? item.label : undefined}
              >
                <span className="shrink-0">{item.icon}</span>
                {!collapsed && <span className="truncate">{item.label}</span>}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Footer persistent notice */}
      {!collapsed && (
        <div className="p-4 border-t border-brand-border">
          <div className="bg-brand-bg p-3 rounded-lg border border-brand-border">
            <span className="text-overline text-brand-text-muted block mb-1">Notice</span>
            <p className="text-[11px] text-brand-text-secondary leading-snug">
              Simulations model 5–50 router networks. Packet loss & latency evaluated honestly.
            </p>
          </div>
        </div>
      )}
    </aside>
  );
};
