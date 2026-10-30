import React, { ReactNode } from 'react';

interface KpiCardProps {
  label: string;
  value: string | number;
  unit?: string;
  subtext?: string;
  icon?: ReactNode;
  trend?: {
    value: string;
    isPositive: boolean;
  };
  onClick?: () => void;
  className?: string;
}

export const KpiCard: React.FC<KpiCardProps> = ({
  label,
  value,
  unit,
  subtext,
  icon,
  trend,
  onClick,
  className = '',
}) => {
  return (
    <div
      onClick={onClick}
      className={`bg-brand-surface border border-brand-border rounded-lg p-5 flex flex-col justify-between transition-all ${
        onClick ? 'cursor-pointer hover:border-brand-primary/50 hover:shadow-sm' : ''
      } ${className}`}
    >
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="text-overline text-brand-text-muted">{label}</span>
        {icon && <span className="text-brand-text-muted">{icon}</span>}
      </div>

      <div className="flex items-baseline gap-1.5 my-1">
        <span className="text-kpi font-bold text-brand-text-primary tracking-tight">
          {value}
        </span>
        {unit && <span className="text-caption text-brand-text-muted font-medium">{unit}</span>}
      </div>

      {(subtext || trend) && (
        <div className="flex items-center gap-2 mt-1">
          {trend && (
            <span
              className={`text-caption font-semibold px-1.5 py-0.5 rounded ${
                trend.isPositive
                  ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-400'
                  : 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-400'
              }`}
            >
              {trend.value}
            </span>
          )}
          {subtext && <span className="text-caption text-brand-text-muted">{subtext}</span>}
        </div>
      )}
    </div>
  );
};
