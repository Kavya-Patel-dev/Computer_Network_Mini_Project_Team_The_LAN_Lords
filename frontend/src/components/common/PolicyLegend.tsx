import React from 'react';

export const PolicyLegend: React.FC<{ className?: string }> = ({ className = '' }) => {
  return (
    <div className={`flex flex-wrap items-center gap-4 text-caption text-brand-text-secondary ${className}`}>
      <div className="flex items-center gap-2">
        <span className="w-3.5 h-3.5 rounded-sm bg-[#64748B]" />
        <span className="font-medium text-brand-text-primary">Static Dijkstra</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="w-3.5 h-3.5 rounded-sm bg-[#2563EB]" />
        <span className="font-medium text-brand-text-primary">Load-aware Dijkstra</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="w-3.5 h-3.5 rounded-sm bg-[#16A34A]" />
        <span className="font-medium text-brand-text-primary">AI agent</span>
      </div>
    </div>
  );
};
