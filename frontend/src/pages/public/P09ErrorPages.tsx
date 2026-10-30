import React from 'react';
import { useViewport } from '../../context/ViewportContext';
import { useAuth } from '../../context/AuthContext';
import { ShieldAlert, FileQuestion, ServerCrash, WifiOff, Wrench, ArrowLeft, Home, Copy } from 'lucide-react';

interface ErrorPageProps {
  type: '403' | '404' | '500' | 'offline' | 'maintenance';
}

export const P09ErrorPages: React.FC<ErrorPageProps> = ({ type }) => {
  const { navigate, goBack } = useViewport();
  const { role } = useAuth();

  const homePath = role === 'admin' ? '/admin/queue' : '/dashboard';

  const getDetails = () => {
    switch (type) {
      case '403':
        return {
          icon: <ShieldAlert className="w-12 h-12 text-rose-500" />,
          code: '403',
          title: 'Access Forbidden',
          message:
            'You do not have administrative privileges to access this console endpoint. Permissions are strictly enforced by the backend server.',
          helper:
            'Handoff note: UI hiding is for usability only; every permission is enforced by the backend and each forbidden API call returns 403.',
        };
      case '404':
        return {
          icon: <FileQuestion className="w-12 h-12 text-amber-500" />,
          code: '404',
          title: 'Resource Not Found',
          message: 'The requested plan, simulation run, or route does not exist in the routing engine catalog.',
          helper: 'Please verify the plan identifier or navigation link.',
        };
      case '500':
        return {
          icon: <ServerCrash className="w-12 h-12 text-rose-500" />,
          code: '500',
          title: 'Simulation Core Error',
          message: 'An unexpected discrete-event simulation exception occurred while evaluating routing matrices.',
          helper: 'Code reference: ERR-DISCRETE-SIM-500-D5BC',
        };
      case 'offline':
        return {
          icon: <WifiOff className="w-12 h-12 text-slate-500" />,
          code: 'Offline',
          title: 'Network Disconnected',
          message: 'Your client has lost connectivity with the NetRoute AI synchronization server.',
          helper: 'Canvas edits are saved in browser local storage.',
        };
      case 'maintenance':
        return {
          icon: <Wrench className="w-12 h-12 text-blue-500" />,
          code: '503',
          title: 'Scheduled System Maintenance',
          message: 'Upgrading imitation learning neural checkpoint weights to v1.1. Simulation engines will resume shortly.',
          helper: 'Window: 14:00 - 15:00 UTC, Oct 20 2026',
        };
    }
  };

  const details = getDetails();

  return (
    <div className="min-h-screen bg-brand-bg flex flex-col items-center justify-center p-6 text-center">
      <div className="max-w-md w-full bg-brand-surface border border-brand-border rounded-xl p-8 shadow-xl">
        <div className="flex justify-center mb-4">{details.icon}</div>
        <span className="text-overline text-brand-text-muted font-mono">{details.code} STATUS</span>
        <h1 className="text-h1 font-bold text-brand-text-primary mt-1 mb-3">{details.title}</h1>
        <p className="text-body text-brand-text-secondary leading-relaxed mb-6">{details.message}</p>

        <div className="p-3 bg-brand-bg border border-brand-border rounded-lg text-caption text-brand-text-muted font-mono mb-6 text-left">
          {details.helper}
        </div>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <button
            onClick={goBack}
            className="px-4 py-2 rounded-lg border border-brand-border text-brand-text-primary text-btn font-semibold hover:bg-brand-bg flex items-center justify-center gap-2"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Go Back</span>
          </button>

          <button
            onClick={() => navigate(homePath)}
            className="px-4 py-2 rounded-lg bg-brand-primary text-white text-btn font-semibold hover:opacity-90 flex items-center justify-center gap-2"
          >
            <Home className="w-4 h-4" />
            <span>Go to My Home</span>
          </button>
        </div>
      </div>
    </div>
  );
};
