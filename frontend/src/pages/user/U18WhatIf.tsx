import React from 'react';
import { useViewport } from '../../context/ViewportContext';
import { PageHeader } from '../../components/common/PageHeader';
import { AlertCircle } from 'lucide-react';

export const U18WhatIf: React.FC = () => {
  const { navigate, currentPath } = useViewport();
  const resultId = currentPath.split('/')[2] || '';
  return <div className="p-6 max-w-4xl mx-auto space-y-5">
    <PageHeader title="What-If Topology Experimenter" subtitle="Counterfactual runs require a saved topology and a dedicated simulation endpoint." actions={<button onClick={() => navigate(`/results/${encodeURIComponent(resultId)}`)} className="px-3 py-2 border border-brand-border rounded-lg">Back to results</button>} />
    <div className="p-4 rounded-lg border border-amber-300 bg-amber-50 text-amber-900 text-caption flex gap-2"><AlertCircle className="w-4 h-4 shrink-0" /><span>This feature is not connected to a what-if API. No counterfactual result, topology change, or draft plan has been created.</span></div>
    <div className="p-5 bg-brand-surface border border-brand-border rounded-xl space-y-2"><h2 className="font-semibold">Current backend support</h2><p className="text-caption text-brand-text-secondary">The simulation API evaluates approved saved plans. It does not yet accept temporary topology patches or persist a derived draft. The previous hardcoded comparison has been removed to avoid presenting sample values as live model output.</p></div>
    <button onClick={() => navigate('/plans')} className="px-4 py-2 rounded-lg bg-brand-primary text-white text-caption font-semibold">Open saved plans</button>
  </div>;
};
