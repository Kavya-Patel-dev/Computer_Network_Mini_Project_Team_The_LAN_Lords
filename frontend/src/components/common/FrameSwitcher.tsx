import React from 'react';
import { useViewport } from '../../context/ViewportContext';
import { useTheme } from '../../context/ThemeContext';
import { useLocale } from '../../context/LocaleContext';
import { ViewportMode, UiState } from '../../types/ui';
import { 
  Monitor, 
  Tablet, 
  Smartphone, 
  Sun, 
  Moon, 
  Globe
} from 'lucide-react';

export const FrameSwitcher: React.FC = () => {
  const { mode, setMode, uiState, setUiState, currentPath, navigate } = useViewport();
  const { theme, toggleTheme } = useTheme();
  const { language, setLanguage } = useLocale();

  const allPages = [
    { section: 'Public Pages', items: [
      { path: '/', label: 'Landing' }, { path: '/login', label: 'Login' },
      { path: '/register', label: 'Register' }, { path: '/forgot-password', label: 'Password reset status' },
      { path: '/demo', label: 'Demo availability' }, { path: '/share/invalid-token', label: 'Shared result (example invalid token)' },
      { path: '/403', label: '403 Forbidden' }, { path: '/404', label: '404 Not Found' }, { path: '/500', label: '500 Server Error' },
    ]},
    { section: 'User Workspace', items: [
      { path: '/dashboard', label: 'Dashboard' }, { path: '/plans', label: 'Saved plans (open a real plan for editors)' },
      { path: '/plans/new', label: 'Create plan' }, { path: '/results', label: 'Saved results (open a real run for reports)' },
      { path: '/results/share', label: 'Share-link manager' }, { path: '/notifications', label: 'Notifications' }, { path: '/profile', label: 'Profile and sessions' },
    ]},
    { section: 'Admin Suite', items: [
      { path: '/admin/queue', label: 'Review queue (open a real queued plan)' }, { path: '/admin/plans', label: 'All plans' },
      { path: '/admin/stats', label: 'Analytics' }, { path: '/admin/users', label: 'Users (open a real user)' },
      { path: '/admin/audit', label: 'Audit log' }, { path: '/admin/settings', label: 'Settings status' },
      { path: '/admin/permissions', label: 'Permissions matrix' }, { path: '/admin/model', label: 'Model info' },
    ]}
  ];

  return (
    <header className="sticky top-0 z-50 bg-slate-900 text-slate-100 border-b border-slate-800 px-3 py-2 text-caption shadow-md">
      <div className="max-w-[1720px] mx-auto flex flex-wrap items-center justify-between gap-3">
        {/* Brand & Jump Menu */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 font-bold text-white tracking-tight">
            <span className="w-2.5 h-2.5 rounded-full bg-blue-500 animate-pulse" />
            <span>NetRoute AI</span>
            <span className="px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 text-[10px] font-mono border border-blue-500/30">
              HARNESS
            </span>
          </div>

          {/* Quick Page Jump Selector */}
          <div className="relative">
            <select
              value={currentPath}
              onChange={(e) => navigate(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-slate-200 text-[11px] rounded px-2.5 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500 font-mono"
            >
              {allPages.map((grp) => (
                <optgroup key={grp.section} label={grp.section}>
                  {grp.items.map((it) => (
                    <option key={it.path} value={it.path}>
                      {it.label}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>
        </div>

        {/* Center: Frame Switcher (390, 768, 1440) */}
        <div className="flex items-center gap-1 bg-slate-800/80 p-1 rounded-md border border-slate-700">
          <button
            onClick={() => setMode('desktop')}
            className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[11px] font-medium transition-colors ${
              mode === 'desktop'
                ? 'bg-blue-600 text-white font-semibold'
                : 'text-slate-400 hover:text-white'
            }`}
            title="Desktop Frame (1440px)"
          >
            <Monitor className="w-3.5 h-3.5" />
            <span>Desktop 1440</span>
          </button>

          <button
            onClick={() => setMode('tablet')}
            className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[11px] font-medium transition-colors ${
              mode === 'tablet'
                ? 'bg-blue-600 text-white font-semibold'
                : 'text-slate-400 hover:text-white'
            }`}
            title="Tablet Frame (768px)"
          >
            <Tablet className="w-3.5 h-3.5" />
            <span>Tablet 768</span>
          </button>

          <button
            onClick={() => setMode('mobile')}
            className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[11px] font-medium transition-colors ${
              mode === 'mobile'
                ? 'bg-blue-600 text-white font-semibold'
                : 'text-slate-400 hover:text-white'
            }`}
            title="Mobile Frame (390px)"
          >
            <Smartphone className="w-3.5 h-3.5" />
            <span>Mobile 390</span>
          </button>
        </div>

        {/* Global States Variant Simulator */}
        <div className="flex items-center gap-1 bg-slate-800/80 p-1 rounded-md border border-slate-700">
          <span className="text-[10px] text-slate-400 px-1 font-mono uppercase">State:</span>
          {(['normal', 'loading', 'empty', 'error', 'forbidden'] as UiState[]).map((st) => (
            <button
              key={st}
              onClick={() => setUiState(st)}
              className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase transition-colors ${
                uiState === st
                  ? 'bg-amber-500 text-slate-950 font-bold'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              {st}
            </button>
          ))}
        </div>

        {/* Right side controls: Theme and Language */}
        <div className="flex items-center gap-2">
          {/* Language Switch */}
          <div className="flex items-center gap-1 bg-slate-800 px-1.5 py-1 rounded border border-slate-700 text-[11px]">
            <Globe className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value as any)}
              className="bg-transparent text-slate-200 focus:outline-none cursor-pointer"
            >
              <option value="en" className="bg-slate-900 text-white">EN</option>
              <option value="gu" className="bg-slate-900 text-white">ગુજરાતી</option>
              <option value="hi" className="bg-slate-900 text-white">हिन्दी</option>
            </select>
          </div>

          {/* Theme Toggle */}
          <button
            onClick={toggleTheme}
            className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 transition-colors"
            title="Toggle Light / Dark mode"
          >
            {theme === 'light' ? <Moon className="w-3.5 h-3.5" /> : <Sun className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>
    </header>
  );
};
