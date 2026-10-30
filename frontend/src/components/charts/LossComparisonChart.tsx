import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { PolicyLegend } from '../common/PolicyLegend';

interface LossComparisonChartProps {
  data: Array<{
    scenario: string;
    static: number;
    loadAware: number;
    ai: number;
  }>;
}

export const LossComparisonChart: React.FC<LossComparisonChartProps> = ({ data }) => {
  return (
    <div className="w-full h-full flex flex-col justify-between">
      <div className="w-full h-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--color-border)" />
            <XAxis
              dataKey="scenario"
              tick={{ fill: 'var(--color-text-secondary)', fontSize: 12 }}
              axisLine={{ stroke: 'var(--color-border)' }}
            />
            <YAxis
              unit="%"
              tick={{ fill: 'var(--color-text-secondary)', fontSize: 12 }}
              axisLine={{ stroke: 'var(--color-border)' }}
            />
            <Tooltip
              content={({ active, payload, label }) => {
                if (active && payload && payload.length) {
                  return (
                    <div className="bg-brand-surface border border-brand-border p-3 rounded-lg shadow-lg text-caption">
                      <p className="font-semibold text-brand-text-primary mb-1">{label} Scenario</p>
                      <div className="space-y-1">
                        <p className="flex items-center gap-2 text-slate-600 dark:text-slate-400">
                          <span className="w-2.5 h-2.5 rounded-sm bg-[#64748B]" />
                          Static: <span className="font-mono font-bold">{payload[0].value}% loss</span>
                        </p>
                        <p className="flex items-center gap-2 text-blue-600 dark:text-blue-400">
                          <span className="w-2.5 h-2.5 rounded-sm bg-[#2563EB]" />
                          Load-aware: <span className="font-mono font-bold">{payload[1].value}% loss</span>
                        </p>
                        <p className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
                          <span className="w-2.5 h-2.5 rounded-sm bg-[#16A34A]" />
                          AI agent: <span className="font-mono font-bold">{payload[2].value}% loss</span>
                        </p>
                      </div>
                    </div>
                  );
                }
                return null;
              }}
            />
            <Bar dataKey="static" fill="#64748B" radius={[4, 4, 0, 0]} name="Static Dijkstra" />
            <Bar dataKey="loadAware" fill="#2563EB" radius={[4, 4, 0, 0]} name="Load-aware Dijkstra" />
            <Bar dataKey="ai" fill="#16A34A" radius={[4, 4, 0, 0]} name="AI agent" />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <PolicyLegend className="mt-3 justify-center" />
    </div>
  );
};
