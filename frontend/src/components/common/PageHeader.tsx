import React, { ReactNode } from 'react';
import { ChevronRight } from 'lucide-react';
import { BreadcrumbItem } from '../../types/ui';
import { useViewport } from '../../context/ViewportContext';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  breadcrumbs?: BreadcrumbItem[];
  actions?: ReactNode;
  badge?: ReactNode;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  subtitle,
  breadcrumbs,
  actions,
  badge,
}) => {
  const { navigate, mode } = useViewport();

  return (
    <div className="mb-6">
      {/* Breadcrumb - visible on desktop and tablet */}
      {breadcrumbs && breadcrumbs.length > 0 && mode !== 'mobile' && (
        <nav className="flex items-center gap-1.5 text-caption text-brand-text-muted mb-2">
          {breadcrumbs.map((bc, idx) => (
            <React.Fragment key={idx}>
              {idx > 0 && <ChevronRight className="w-3.5 h-3.5" />}
              {bc.href ? (
                <button
                  onClick={() => navigate(bc.href!)}
                  className="hover:text-brand-primary hover:underline transition-colors focus:outline-none"
                >
                  {bc.label}
                </button>
              ) : (
                <span className="text-brand-text-secondary font-medium">{bc.label}</span>
              )}
            </React.Fragment>
          ))}
        </nav>
      )}

      {/* Main Title Row */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-h1 font-bold text-brand-text-primary tracking-tight">
              {title}
            </h1>
            {badge && <div>{badge}</div>}
          </div>
          {subtitle && (
            <p className="text-body-l text-brand-text-secondary mt-1 max-w-3xl">
              {subtitle}
            </p>
          )}
        </div>

        {/* Action area */}
        {actions && (
          <div className="flex items-center gap-2.5 flex-wrap sm:flex-nowrap">
            {actions}
          </div>
        )}
      </div>
    </div>
  );
};
