import React from 'react';
import { useViewport } from '../../context/ViewportContext';
import { ArrowRight, Info } from 'lucide-react';

export const P07DemoResult: React.FC = () => {
  const { navigate } = useViewport();
  return <div className="min-h-screen bg-brand-bg text-brand-text-primary p-6 flex items-center justify-center">
    <div className="max-w-2xl bg-brand-surface border border-brand-border rounded-2xl p-8 space-y-5">
      <div className="flex items-center gap-2 text-brand-primary"><Info className="w-5 h-5" /><span className="text-overline font-semibold">Live demo unavailable</span></div>
      <h1 className="text-h1 font-bold">Routing simulation results</h1>
      <p className="text-body text-brand-text-secondary">A public demo run is not configured on this backend. Sign in to submit a topology for review and run the saved model-backed simulation. No sample benchmark figures are shown here as live results.</p>
      <button onClick={() => navigate('/register')} className="px-4 py-2 rounded-lg bg-brand-primary text-white text-btn font-semibold flex items-center gap-2">Create account <ArrowRight className="w-4 h-4" /></button>
    </div>
  </div>;
};
