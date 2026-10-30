import React, { useState } from 'react';
import { Plan } from '../../types/plan';
import { StatusChip } from './StatusChip';
import { 
  Network, 
  MoreVertical, 
  Play, 
  Edit3, 
  Copy, 
  Trash2, 
  Share2, 
  Eye, 
  Send, 
  Undo2 
} from 'lucide-react';
import { useViewport } from '../../context/ViewportContext';
import { useAuth } from '../../context/AuthContext';

interface PlanCardProps {
  plan: Plan;
  onDuplicate?: (plan: Plan) => void;
  className?: string;
}

export const PlanCard: React.FC<PlanCardProps> = ({
  plan,
  onDuplicate,
  className = '',
}) => {
  const { navigate, openOverlay } = useViewport();
  const { currentUser, role } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  const isOwner = currentUser?.email.toLowerCase() === plan.ownerEmail.toLowerCase();
  const isAdmin = role === 'admin';

  const handleCardClick = () => {
    navigate(`/plans/${plan.id}`);
  };

  return (
    <div
      onClick={handleCardClick}
      className={`group bg-brand-surface border border-brand-border hover:border-brand-primary/50 rounded-lg p-5 transition-all shadow-sm hover:shadow cursor-pointer flex flex-col justify-between ${className}`}
    >
      <div>
        {/* Top Header */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-2 flex-wrap">
            <StatusChip status={plan.status} />
            <span className="text-caption font-mono font-semibold px-2 py-0.5 rounded bg-brand-bg border border-brand-border text-brand-text-secondary">
              {plan.version}
            </span>
          </div>

          {/* Action Menu */}
          <div className="relative" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="p-1.5 rounded hover:bg-brand-bg text-brand-text-muted hover:text-brand-text-primary transition-colors focus:outline-none"
              aria-label="Plan actions"
            >
              <MoreVertical className="w-4 h-4" />
            </button>

            {menuOpen && (
              <div className="absolute right-0 top-8 z-30 w-48 bg-brand-surface border border-brand-border rounded-lg shadow-lg py-1 text-body">
                <button
                  onClick={() => {
                    setMenuOpen(false);
                    navigate(`/plans/${plan.id}`);
                  }}
                  className="w-full text-left px-3.5 py-2 hover:bg-brand-bg flex items-center gap-2 text-brand-text-primary"
                >
                  <Eye className="w-4 h-4 text-brand-text-muted" />
                  View Details
                </button>

                {isOwner && (plan.status === 'Draft' || plan.status === 'Changes Requested') && (
                  <button
                    onClick={() => {
                      setMenuOpen(false);
                      navigate(`/plans/${plan.id}/edit/canvas`);
                    }}
                    className="w-full text-left px-3.5 py-2 hover:bg-brand-bg flex items-center gap-2 text-brand-text-primary"
                  >
                    <Edit3 className="w-4 h-4 text-brand-text-muted" />
                    Edit Plan
                  </button>
                )}

                {isOwner && plan.status === 'Draft' && (
                  <button
                    onClick={() => {
                      setMenuOpen(false);
                      openOverlay('O01', { plan });
                    }}
                    className="w-full text-left px-3.5 py-2 hover:bg-brand-bg flex items-center gap-2 text-brand-primary font-medium"
                  >
                    <Send className="w-4 h-4" />
                    Submit for Review
                  </button>
                )}

                {isOwner && plan.status === 'Pending Review' && (
                  <button
                    onClick={() => {
                      setMenuOpen(false);
                      openOverlay('O02', { plan });
                    }}
                    className="w-full text-left px-3.5 py-2 hover:bg-brand-bg flex items-center gap-2 text-amber-700 dark:text-amber-400"
                  >
                    <Undo2 className="w-4 h-4" />
                    Withdraw to Draft
                  </button>
                )}

                {plan.status === 'Approved' && (
                  <button
                    onClick={() => {
                      setMenuOpen(false);
                      navigate(`/plans/${plan.id}/run`);
                    }}
                    className="w-full text-left px-3.5 py-2 hover:bg-brand-bg flex items-center gap-2 text-emerald-600 font-semibold"
                  >
                    <Play className="w-4 h-4" />
                    Run Simulation
                  </button>
                )}

                {plan.status === 'Completed' && (
                  <>
                    <button
                      onClick={() => {
                        setMenuOpen(false);
                        navigate('/results');
                      }}
                      className="w-full text-left px-3.5 py-2 hover:bg-brand-bg flex items-center gap-2 text-brand-primary"
                    >
                      <Eye className="w-4 h-4" />
                      View Results
                    </button>
                    <button
                      onClick={() => {
                        setMenuOpen(false);
                        openOverlay('O10', { plan });
                      }}
                      className="w-full text-left px-3.5 py-2 hover:bg-brand-bg flex items-center gap-2 text-brand-text-primary"
                    >
                      <Share2 className="w-4 h-4 text-brand-text-muted" />
                      Share Link
                    </button>
                  </>
                )}

                <button
                  onClick={() => {
                    setMenuOpen(false);
                    if (onDuplicate) onDuplicate(plan);
                  }}
                  className="w-full text-left px-3.5 py-2 hover:bg-brand-bg flex items-center gap-2 text-brand-text-primary"
                >
                  <Copy className="w-4 h-4 text-brand-text-muted" />
                  Duplicate
                </button>

                {isOwner && plan.status === 'Draft' && (
                  <button
                    onClick={() => {
                      setMenuOpen(false);
                      openOverlay('O03', { plan });
                    }}
                    className="w-full text-left px-3.5 py-2 hover:bg-rose-50 dark:hover:bg-rose-950/40 text-rose-600 flex items-center gap-2"
                  >
                    <Trash2 className="w-4 h-4" />
                    Delete Draft
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Plan Name & Description */}
        <h3 className="text-h3 font-semibold text-brand-text-primary group-hover:text-brand-primary transition-colors mb-1 line-clamp-1">
          {plan.name}
        </h3>
        <p className="text-caption text-brand-text-secondary line-clamp-2 mb-4 min-h-[32px]">
          {plan.description || 'No description provided.'}
        </p>

        {/* Mini Topology Thumbnail Mock */}
        <div className="h-20 w-full bg-brand-bg border border-brand-border rounded-md mb-4 flex items-center justify-center relative overflow-hidden">
          <div className="flex items-center gap-6 opacity-60">
            <div className="w-6 h-6 rounded-full border-2 border-brand-primary flex items-center justify-center font-mono text-[9px] font-bold">
              R1
            </div>
            <div className="w-8 border-t-2 border-dashed border-brand-border" />
            <div className="w-6 h-6 rounded-full border-2 border-brand-primary flex items-center justify-center font-mono text-[9px] font-bold">
              R2
            </div>
            <div className="w-8 border-t-2 border-brand-border" />
            <div className="w-5 h-5 rounded border border-emerald-600 flex items-center justify-center text-[8px]">
              PC
            </div>
          </div>
          <span className="absolute bottom-1 right-1 text-[10px] text-brand-text-muted font-mono bg-brand-surface/90 px-1 rounded">
            {plan.routerCount}R • {plan.hostCount}H
          </span>
        </div>
      </div>

      {/* Footer Info */}
      <div className="pt-3 border-t border-brand-border flex items-center justify-between text-caption text-brand-text-muted">
        <div>
          <span>Updated {plan.updated_at.split(' ')[0]}</span>
          {isAdmin && <span className="block text-brand-text-secondary font-medium">by {plan.owner}</span>}
        </div>

        {plan.status === 'Approved' && (
          <span className="text-emerald-600 font-semibold flex items-center gap-1">
            <Play className="w-3.5 h-3.5 fill-current" /> Ready
          </span>
        )}
      </div>
    </div>
  );
};
