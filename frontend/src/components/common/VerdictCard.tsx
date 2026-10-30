import React from 'react';
import { Info, HelpCircle, CheckCircle, AlertTriangle, MinusCircle } from 'lucide-react';
import { useViewport } from '../../context/ViewportContext';

interface VerdictCardProps {
  type: 'better' | 'equal' | 'worse';
  customText?: string;
  scenarioName?: string;
  onHowToReadClick?: () => void;
  className?: string;
}

export const VerdictCard: React.FC<VerdictCardProps> = ({
  type,
  customText,
  scenarioName = 'Normal',
  onHowToReadClick,
  className = '',
}) => {
  const { openOverlay } = useViewport();

  const handleHowToRead = () => {
    if (onHowToReadClick) {
      onHowToReadClick();
    } else {
      openOverlay('O12');
    }
  };

  const getVerdictContent = () => {
    switch (type) {
      case 'better':
        return {
          icon: <CheckCircle className="w-6 h-6 text-emerald-600 dark:text-emerald-400 shrink-0" />,
          title: 'Simulation Verdict',
          text:
            customText ||
            'AI cut packet loss by 62% compared with static routing and is within 8% of load-aware Dijkstra.',
          borderColor: 'border-emerald-300 dark:border-emerald-800',
          bgColor: 'bg-emerald-50/70 dark:bg-emerald-950/20',
          badgeText: 'Substantial Improvement',
          badgeClass: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/60 dark:text-emerald-300',
        };
      case 'equal':
        return {
          icon: <MinusCircle className="w-6 h-6 text-slate-500 shrink-0" />,
          title: 'Simulation Verdict',
          text:
            customText ||
            'All three strategies perform almost the same because the network has few alternative paths.',
          borderColor: 'border-slate-300 dark:border-slate-700',
          bgColor: 'bg-slate-50 dark:bg-slate-900/40',
          badgeText: 'Topology Constraint',
          badgeClass: 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
        };
      case 'worse':
        return {
          icon: <AlertTriangle className="w-6 h-6 text-amber-600 dark:text-amber-400 shrink-0" />,
          title: 'Simulation Verdict',
          text:
            customText ||
            'AI performed slightly worse than load-aware Dijkstra in this scenario (2.4% vs 2.2% packet loss). Link saturation forced safe heuristic fallback during rerouting.',
          borderColor: 'border-amber-300 dark:border-amber-800',
          bgColor: 'bg-amber-50/70 dark:bg-amber-950/20',
          badgeText: 'Load-aware Outperformed AI',
          badgeClass: 'bg-amber-100 text-amber-800 dark:bg-amber-900/60 dark:text-amber-300',
        };
    }
  };

  const content = getVerdictContent();

  return (
    <div
      className={`border rounded-lg p-5 ${content.bgColor} ${content.borderColor} ${className} transition-all`}
    >
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
        <div className="flex items-start gap-3.5">
          {content.icon}
          <div>
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <span className="text-overline text-brand-text-muted">{content.title}</span>
              <span className={`text-caption font-semibold px-2 py-0.5 rounded-full ${content.badgeClass}`}>
                {content.badgeText}
              </span>
              <span className="inline-flex items-center gap-1 text-[11px] font-medium text-brand-text-muted bg-brand-surface/80 px-2 py-0.5 rounded border border-brand-border">
                <Info className="w-3 h-3" />
                Simulation result • {scenarioName} scenario
              </span>
            </div>
            <p className="text-body-l font-medium text-brand-text-primary leading-relaxed mt-1">
              {content.text}
            </p>
          </div>
        </div>

        <button
          onClick={handleHowToRead}
          className="inline-flex items-center gap-1.5 text-caption font-semibold text-brand-primary hover:underline shrink-0 focus:outline-none"
        >
          <HelpCircle className="w-4 h-4" />
          How to read this
        </button>
      </div>
    </div>
  );
};
