import React, { ReactNode } from 'react';

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  actionLabel,
  onAction,
  className = '',
}) => {
  return (
    <div
      className={`flex flex-col items-center justify-center p-12 text-center bg-brand-surface border border-dashed border-brand-border rounded-lg ${className}`}
    >
      <div className="w-12 h-12 rounded-full bg-brand-bg flex items-center justify-center text-brand-text-muted mb-4 border border-brand-border shadow-sm">
        {icon}
      </div>
      <h3 className="text-h3 font-semibold text-brand-text-primary mb-1">{title}</h3>
      <p className="text-body text-brand-text-secondary max-w-sm mb-6">{description}</p>
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className="inline-flex items-center justify-center px-4 py-2 rounded-lg bg-brand-primary text-white text-btn font-semibold hover:opacity-90 transition-opacity touch-target shadow-sm"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
};
