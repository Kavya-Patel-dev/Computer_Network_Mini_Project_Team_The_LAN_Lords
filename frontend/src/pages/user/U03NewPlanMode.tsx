import React, { useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { api } from '../../api/client';
import { Plan } from '../../types/plan';
import { PageHeader } from '../../components/common/PageHeader';
import { 
  Palette,
  Sparkles, 
  Clock, 
  CheckCircle2, 
  ArrowRight 
} from 'lucide-react';

export const U03NewPlanMode: React.FC = () => {
  const { navigate } = useViewport();
  const [planName, setPlanName] = useState('');
  const [description, setDescription] = useState('');
  const [selectedMode, setSelectedMode] = useState<'canvas' | 'generate'>('canvas');
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const modes = [
    {
      id: 'canvas' as const,
      title: 'Draw my network',
      icon: <Palette className="w-8 h-8 text-brand-primary" />,
      desc: 'Interactive drag-and-drop canvas editor with live port linking and topology validation.',
      bestFor: 'Visual architecture planning and custom mesh topologies',
      time: '~10–15 min',
      route: 'canvas',
    },
    {
      id: 'generate' as const,
      title: 'Generate from my needs',
      badge: 'Beta',
      icon: <Sparkles className="w-8 h-8 text-purple-500" />,
      desc: 'Build an editable starter topology from device counts and redundancy needs. The routing AI runs later during simulation.',
      bestFor: 'Rapid benchmarking without manual topology drafting',
      time: '~2 min',
      route: 'generate',
    },
  ];

  const handleContinue = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!planName.trim()) return;
    const targetMode = modes.find((m) => m.id === selectedMode);
    if (!targetMode) return;
    setIsCreating(true);
    setError(null);
    try {
      const plan = await api.post<Plan>('/records', {
        name: planName.trim(),
        description,
        topology: { id: '', name: planName.trim(), nodes: [], links: [] },
        traffic_preset: 'medium',
        flows: [],
        selected_scenarios: ['normal'],
      });
      navigate(`/plans/${encodeURIComponent(plan.id)}/edit/${targetMode.route}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create the draft plan.');
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-8">
      {/* Wizard Stepper Header */}
      <div>
        <PageHeader
          title="Create New Routing Plan"
          subtitle="Configure your network design and multi-scenario evaluation parameters."
        />

        {/* Stepper (Network -> Traffic & Scenarios -> Review) */}
        <div className="flex items-center justify-between max-w-md mx-auto my-6 text-caption">
          <div className="flex items-center gap-2 text-brand-primary font-bold">
            <span className="w-6 h-6 rounded-full bg-brand-primary text-white flex items-center justify-center text-xs">1</span>
            <span>Network Design</span>
          </div>
          <div className="h-0.5 w-12 bg-brand-border" />
          <div className="flex items-center gap-2 text-brand-text-muted font-medium">
            <span className="w-6 h-6 rounded-full bg-brand-surface border border-brand-border flex items-center justify-center text-xs">2</span>
            <span>Traffic & Scenarios</span>
          </div>
          <div className="h-0.5 w-12 bg-brand-border" />
          <div className="flex items-center gap-2 text-brand-text-muted font-medium">
            <span className="w-6 h-6 rounded-full bg-brand-surface border border-brand-border flex items-center justify-center text-xs">3</span>
            <span>Review & Submit</span>
          </div>
        </div>
      </div>

      <form onSubmit={handleContinue} className="space-y-6">
        {error && <div role="alert" className="p-3 rounded-lg border border-rose-300 bg-rose-50 text-rose-800 text-caption">{error}</div>}
        {/* Name and Description Inputs */}
        <div className="bg-brand-surface border border-brand-border rounded-xl p-6 space-y-4 shadow-sm">
          <div>
            <label className="text-label text-brand-text-primary block mb-1">
              Plan Name <span className="text-rose-500">*</span>
            </label>
            <input
              type="text"
              required
              value={planName}
              onChange={(e) => setPlanName(e.target.value)}
              placeholder="e.g. Branch Campus Core Network"
              className="w-full px-3.5 py-2.5 rounded-lg bg-brand-bg border border-brand-border text-body text-brand-text-primary focus:outline-none focus:ring-2 focus:ring-brand-primary"
            />
          </div>

          <div>
            <label className="text-label text-brand-text-primary block mb-1">Description (Optional)</label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="State the purpose, topology expectations, or load profile of this design..."
              className="w-full px-3.5 py-2 rounded-lg bg-brand-bg border border-brand-border text-body text-brand-text-primary focus:outline-none focus:ring-2 focus:ring-brand-primary"
            />
          </div>
        </div>

        {/* Two supported creation modes */}
        <div>
          <label className="text-h3 font-semibold text-brand-text-primary block mb-3">
            Choose Network Creation Mode
          </label>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {modes.map((mode) => (
              <div
                key={mode.id}
                onClick={() => setSelectedMode(mode.id)}
                className={`p-5 rounded-xl border-2 transition-all cursor-pointer flex flex-col justify-between ${
                  selectedMode === mode.id
                    ? 'border-brand-primary bg-brand-primary/5 shadow-md'
                    : 'border-brand-border bg-brand-surface hover:border-brand-primary/40'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <div className="p-2 rounded-lg bg-brand-bg border border-brand-border">
                      {mode.icon}
                    </div>
                    {mode.badge && (
                      <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300 border border-purple-300 dark:border-purple-800">
                        {mode.badge}
                      </span>
                    )}
                  </div>

                  <h3 className="text-h3 font-bold text-brand-text-primary mb-1">{mode.title}</h3>
                  <p className="text-caption text-brand-text-secondary leading-relaxed mb-4">{mode.desc}</p>
                </div>

                <div className="pt-3 border-t border-brand-border flex items-center justify-between text-caption text-brand-text-muted">
                  <span className="font-medium text-brand-text-secondary truncate max-w-[240px]">
                    Best for: {mode.bestFor}
                  </span>
                  <span className="flex items-center gap-1 font-mono shrink-0">
                    <Clock className="w-3.5 h-3.5" />
                    {mode.time}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-3 pt-4 border-t border-brand-border">
          <button
            type="button"
            onClick={() => navigate('/plans')}
            className="px-5 py-2.5 rounded-lg border border-brand-border text-brand-text-secondary hover:bg-brand-bg text-btn font-semibold"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isCreating}
            className="px-6 py-2.5 rounded-lg bg-brand-primary text-white text-btn font-semibold hover:opacity-90 flex items-center gap-2 shadow-sm touch-target disabled:opacity-50"
          >
            <span>{isCreating ? 'Creating draft…' : 'Continue to Step 1'}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </form>
    </div>
  );
};
