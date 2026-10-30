import React from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider, useTheme } from './context/ThemeContext';
import { LocaleProvider } from './context/LocaleContext';
import { ViewportProvider, useViewport } from './context/ViewportContext';
import { Topbar } from './components/common/Topbar';
import { Sidebar } from './components/common/Sidebar';
import { ModalContainer } from './components/overlays/ModalContainer';
import { PageSkeleton } from './components/common/SkeletonLoader';

// Public Pages
import { P01Landing } from './pages/public/P01Landing';
import { P02Login } from './pages/public/P02Login';
import { P03Register } from './pages/public/P03Register';
import { P04ForgotPassword } from './pages/public/P04ForgotPassword';
import { P06VerifyEmail } from './pages/public/P06VerifyEmail';
import { P07DemoResult } from './pages/public/P07DemoResult';
import { P08SharedResult } from './pages/public/P08SharedResult';
import { P09ErrorPages } from './pages/public/P09ErrorPages';

// User Pages
import { U01Dashboard } from './pages/user/U01Dashboard';
import { U02MyPlans } from './pages/user/U02MyPlans';
import { U03NewPlanMode } from './pages/user/U03NewPlanMode';
import { U04CanvasEditor } from './pages/user/U04CanvasEditor';
import { U05FormTableEditor } from './pages/user/U05FormTableEditor';
import { U06UploadEditor } from './pages/user/U06UploadEditor';
import { U07GenerateNeeds } from './pages/user/U07GenerateNeeds';
import { U08TrafficScenarios } from './pages/user/U08TrafficScenarios';
import { U09ReviewSubmit } from './pages/user/U09ReviewSubmit';
import { U10PlanDetail } from './pages/user/U10PlanDetail';
import { U11AnalysisReport } from './pages/user/U11AnalysisReport';
import { U12VersionsCompare } from './pages/user/U12VersionsCompare';
import { U13RunSimulation } from './pages/user/U13RunSimulation';
import { U14ResultsOverview } from './pages/user/U14ResultsOverview';
import { U15Heatmap } from './pages/user/U15Heatmap';
import { U16Explainability } from './pages/user/U16Explainability';
import { U17FailureTimeline } from './pages/user/U17FailureTimeline';
import { U18WhatIf } from './pages/user/U18WhatIf';
import { U19ShareLinks } from './pages/user/U19ShareLinks';
import { U20ResultsList } from './pages/user/U20ResultsList';
import { U21Notifications } from './pages/user/U21Notifications';
import { U22ProfileSettings } from './pages/user/U22ProfileSettings';

// Admin Pages
import { A01ReviewQueue } from './pages/admin/A01ReviewQueue';
import { A02ReviewScreen } from './pages/admin/A02ReviewScreen';
import { A03AllPlans } from './pages/admin/A03AllPlans';
import { A04StatsAnalytics } from './pages/admin/A04StatsAnalytics';
import { A05UserManagement } from './pages/admin/A05UserManagement';
import { A06UserDetail } from './pages/admin/A06UserDetail';
import { A07AuditLog } from './pages/admin/A07AuditLog';
import { A08AdminSettings } from './pages/admin/A08AdminSettings';
import { A09PermissionsMatrix } from './pages/admin/A09PermissionsMatrix';
import { A10ModelInfo } from './pages/admin/A10ModelInfo';

const AppContent: React.FC = () => {
  const { currentPath, mode, uiState } = useViewport();
  const { role, currentUser, isLoading } = useAuth();

  // If global state override is 'forbidden', render 403
  if (uiState === 'forbidden') {
    return <P09ErrorPages type="403" />;
  }

  // Route Dispatcher
  const renderCurrentPage = () => {
    // Public routes without global app shell
    if (currentPath === '/') return <P01Landing />;
    if (currentPath === '/login') return <P02Login />;
    if (currentPath === '/register') return <P03Register />;
    if (currentPath === '/forgot-password') return <P04ForgotPassword />;
    if (currentPath === '/verify-email') return <P06VerifyEmail />;
    if (currentPath === '/demo') return <P07DemoResult />;
    if (currentPath.startsWith('/share')) return <P08SharedResult />;
    if (currentPath === '/403') return <P09ErrorPages type="403" />;
    if (currentPath === '/404') return <P09ErrorPages type="404" />;
    if (currentPath === '/500') return <P09ErrorPages type="500" />;

    const publicPaths = ['/', '/login', '/register', '/forgot-password', '/verify-email', '/demo', '/403', '/404', '/500'];
    const isSharePath = currentPath.startsWith('/share');
    if (!publicPaths.includes(currentPath) && !isSharePath && !currentUser) return <P02Login />;

    // Protected Admin Routes (Guard check)
    if (currentPath.startsWith('/admin')) {
      if (!currentUser) return <P02Login />;
      if (role !== 'admin') return <P09ErrorPages type="403" />;
    }

    if (currentPath === '/admin/queue') return <A01ReviewQueue />;
    if (currentPath.startsWith('/admin/review')) return <A02ReviewScreen />;
    if (currentPath === '/admin/plans') return <A03AllPlans />;
    if (currentPath === '/admin/stats') return <A04StatsAnalytics />;
    if (currentPath.startsWith('/admin/users/') && currentPath !== '/admin/users') return <A06UserDetail />;
    if (currentPath === '/admin/users') return <A05UserManagement />;
    if (currentPath === '/admin/audit') return <A07AuditLog />;
    if (currentPath === '/admin/settings') return <A08AdminSettings />;
    if (currentPath === '/admin/permissions') return <A09PermissionsMatrix />;
    if (currentPath === '/admin/model') return <A10ModelInfo />;

    // User Routes
    if (currentPath === '/dashboard') return <U01Dashboard />;
    if (currentPath === '/plans') return <U02MyPlans />;
    if (currentPath === '/plans/new') return <U03NewPlanMode />;
    if (currentPath.includes('/edit/canvas')) return <U04CanvasEditor />;
    if (currentPath.includes('/edit/form')) return <U05FormTableEditor />;
    if (currentPath.includes('/edit/upload')) return <U06UploadEditor />;
    if (currentPath.includes('/edit/generate')) return <U07GenerateNeeds />;
    if (currentPath.includes('/edit/traffic')) return <U08TrafficScenarios />;
    if (currentPath.includes('/edit/review')) return <U09ReviewSubmit />;
    if (currentPath.endsWith('/report')) return <U11AnalysisReport />;
    if (currentPath.endsWith('/versions')) return <U12VersionsCompare />;
    if (currentPath.endsWith('/run')) return <U13RunSimulation />;
    if (currentPath.startsWith('/plans/')) return <U10PlanDetail />;

    if (currentPath.includes('/heatmap')) return <U15Heatmap />;
    if (currentPath.includes('/explain')) return <U16Explainability />;
    if (currentPath.includes('/failure')) return <U17FailureTimeline />;
    if (currentPath.includes('/what-if')) return <U18WhatIf />;
    if (currentPath.includes('/share')) return <U19ShareLinks />;
    if (currentPath.startsWith('/results/') && currentPath !== '/results') return <U14ResultsOverview />;
    if (currentPath === '/results') return <U20ResultsList />;

    if (currentPath === '/notifications') return <U21Notifications />;
    if (currentPath === '/profile') return <U22ProfileSettings />;

    return <P09ErrorPages type="404" />;
  };

  const isPublicPage =
    currentPath === '/' ||
    currentPath === '/login' ||
    currentPath === '/register' ||
    currentPath === '/forgot-password' ||
    currentPath === '/verify-email' ||
    currentPath === '/demo' ||
    currentPath.startsWith('/share') ||
    currentPath === '/403' ||
    currentPath === '/404' ||
    currentPath === '/500';

  if (isLoading && !isPublicPage) return <PageSkeleton />;

  return (
    <div className="min-h-screen bg-brand-bg text-brand-text-primary flex flex-col">
      {isPublicPage ? (
        renderCurrentPage()
      ) : (
        <div className="flex min-h-screen bg-brand-bg text-brand-text-primary">
          {/* Sidebar */}
          <Sidebar />

          {/* Main Area */}
          <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
            <Topbar pageTitle="NetRoute AI" />
            <main className={`flex-1 ${currentPath.includes('/edit/canvas') ? 'p-0 overflow-hidden' : 'pb-16 md:pb-6'}`}>
              {renderCurrentPage()}
            </main>
          </div>
        </div>
      )}

      {/* Modal / Overlay Dialogs Container */}
      <ModalContainer />
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <ThemeProvider>
      <LocaleProvider>
        <AuthProvider>
          <ViewportProvider>
            <AppContent />
          </ViewportProvider>
        </AuthProvider>
      </LocaleProvider>
    </ThemeProvider>
  );
};

export default App;
