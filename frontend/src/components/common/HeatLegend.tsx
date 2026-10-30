import React from 'react';

export const HeatLegend: React.FC<{ className?: string }> = ({ className = '' }) => {
  return (
    <div className={`flex flex-wrap items-center gap-3 p-2 bg-brand-surface border border-brand-border rounded-lg text-caption text-brand-text-secondary ${className}`}>
      <span className="text-overline text-brand-text-muted mr-1">Link Load:</span>
      <div className="flex items-center gap-1.5" title="Under 50% capacity">
        <span className="w-3 h-3 rounded-sm bg-[#16A34A] flex items-center justify-center text-[8px] text-white font-bold">●</span>
        <span>&lt;50%</span>
      </div>
      <div className="flex items-center gap-1.5" title="50% to 80% capacity">
        <span className="w-3 h-3 rounded-sm bg-[#EAB308] flex items-center justify-center text-[8px] text-slate-900 font-bold">▲</span>
        <span>50–80%</span>
      </div>
      <div className="flex items-center gap-1.5" title="80% to 100% capacity (Near Congestion)">
        <span className="w-3 h-3 rounded-sm bg-[#EA580C] flex items-center justify-center text-[8px] text-white font-bold">■</span>
        <span>80–100%</span>
      </div>
      <div className="flex items-center gap-1.5" title="Over 100% capacity (Saturated)">
        <span className="w-3 h-3 rounded-sm bg-[#DC2626] flex items-center justify-center text-[8px] text-white font-bold">◆</span>
        <span>&gt;100%</span>
      </div>
      <div className="flex items-center gap-1.5" title="Failed Link">
        <span className="w-4 h-1 border-b-2 border-dashed border-[#94A3B8]" />
        <span>Failed</span>
      </div>
    </div>
  );
};
