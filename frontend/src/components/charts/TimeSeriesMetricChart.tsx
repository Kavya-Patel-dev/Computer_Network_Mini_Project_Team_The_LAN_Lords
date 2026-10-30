import React, { useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceArea,
} from 'recharts';
import { TimeSeriesPoint } from '../../types/simulation';
import { PolicyLegend } from '../common/PolicyLegend';

interface TimeSeriesMetricChartProps {
  data: TimeSeriesPoint[];
}

export const TimeSeriesMetricChart: React.FC<TimeSeriesMetricChartProps> = ({ data }) => {
  const [metric, setMetric] = useState<'loss' | 'latency'>('loss');

  return (
    <div className="w-full h-full flex flex-col justify-between">
      {/* Metric Toggle */}
      <div className="flex items-center justify-between mb-3">
        <div className="inline-flex p-1 bg-brand-bg border border-brand-border rounded-lg text-caption">
          <button
            onClick={() => setMetric('loss')}
            className={`px-3 py-1 font-semibold rounded ${
              metric === 'loss'
                ? 'bg-brand-surface text-brand-primary shadow-sm'
                : 'text-brand-text-muted hover:text-brand-text-primary'
            }`}
          >
            Packet Loss (%)
          </button>
          <button
            onClick={() => setMetric('latency')}
            className={`px-3 py-1 font-semibold rounded ${
              metric === 'latency'
                ? 'bg-brand-surface text-brand-primary shadow-sm'
                : 'text-brand-text-muted hover:text-brand-text-primary'
            }`}
          >
            Latency (ms)
          </button>
        </div>

        <div className="flex items-center gap-2 text-[11px] text-brand-text-muted">
          <span className="w-3 h-3 bg-amber-500/20 border border-amber-500/40 rounded-sm inline-block" />
          <span>Traffic Spike (Steps 20-35)</span>
          <span className="w-3 h-3 bg-rose-500/20 border border-rose-500/40 rounded-sm inline-block ml-2" />
          <span>Link Failure (Steps 40-50)</span>
        </div>
      </div>

      <div className="w-full h-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={data}
            margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
            <XAxis
              dataKey="step"
              unit="s"
              tick={{ fill: 'var(--color-text-secondary)', fontSize: 12 }}
              axisLine={{ stroke: 'var(--color-border)' }}
            />
            <YAxis
              unit={metric === 'loss' ? '%' : 'ms'}
              tick={{ fill: 'var(--color-text-secondary)', fontSize: 12 }}
              axisLine={{ stroke: 'var(--color-border)' }}
            />

            {/* Event shading regions */}
            <ReferenceArea x1={20} x2={35} fill="#F59E0B" fillOpacity={0.12} />
            <ReferenceArea x1={40} x2={50} fill="#EF4444" fillOpacity={0.15} />

            <Tooltip
              content={({ active, payload, label }) => {
                if (active && payload && payload.length) {
                  const pt = data.find((d) => d.step === Number(label));
                  return (
                    <div className="bg-brand-surface border border-brand-border p-3 rounded-lg shadow-lg text-caption">
                      <p className="font-semibold text-brand-text-primary mb-1">Step {label} (Time: {label}s)</p>
                      {pt?.event && (
                        <p className="text-[11px] font-semibold text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 px-1.5 py-0.5 rounded mb-1.5 border border-amber-200 dark:border-amber-900">
                          ⚡ {pt.event}
                        </p>
                      )}
                      <div className="space-y-1">
                        <p className="flex items-center gap-2 text-slate-600 dark:text-slate-400">
                          <span className="w-2.5 h-2.5 rounded-sm bg-[#64748B]" />
                          Static: <span className="font-mono font-bold">{payload[0].value} {metric === 'loss' ? '%' : 'ms'}</span>
                        </p>
                        <p className="flex items-center gap-2 text-blue-600 dark:text-blue-400">
                          <span className="w-2.5 h-2.5 rounded-sm bg-[#2563EB]" />
                          Load-aware: <span className="font-mono font-bold">{payload[1].value} {metric === 'loss' ? '%' : 'ms'}</span>
                        </p>
                        <p className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
                          <span className="w-2.5 h-2.5 rounded-sm bg-[#16A34A]" />
                          AI agent: <span className="font-mono font-bold">{payload[2].value} {metric === 'loss' ? '%' : 'ms'}</span>
                        </p>
                      </div>
                    </div>
                  );
                }
                return null;
              }}
            />

            <Line
              type="monotone"
              dataKey={metric === 'loss' ? 'staticLoss' : 'staticLatency'}
              stroke="#64748B"
              strokeWidth={2}
              dot={false}
              name="Static Dijkstra"
            />
            <Line
              type="monotone"
              dataKey={metric === 'loss' ? 'loadAwareLoss' : 'loadAwareLatency'}
              stroke="#2563EB"
              strokeWidth={2}
              dot={false}
              name="Load-aware Dijkstra"
            />
            <Line
              type="monotone"
              dataKey={metric === 'loss' ? 'aiLoss' : 'aiLatency'}
              stroke="#16A34A"
              strokeWidth={2.5}
              dot={false}
              name="AI Agent"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <PolicyLegend className="mt-3 justify-center" />
    </div>
  );
};
