import React from 'react';
import { ScenarioResult } from '../../types/simulation';
import { Check } from 'lucide-react';
import { useViewport } from '../../context/ViewportContext';

interface MetricTableProps {
  results: ScenarioResult;
  className?: string;
}

interface MetricRowDef {
  key: string;
  label: string;
  unit: string;
  getStatic: (r: ScenarioResult) => number;
  getLoadAware: (r: ScenarioResult) => number;
  getAi: (r: ScenarioResult) => number;
  lowerIsBetter: boolean;
  format?: (val: number) => string;
}

const METRIC_ROWS: MetricRowDef[] = [
  {
    key: 'loss',
    label: 'Packet loss',
    unit: '%',
    getStatic: (r) => r.static.loss,
    getLoadAware: (r) => r.load_aware.loss,
    getAi: (r) => r.ai.loss,
    lowerIsBetter: true,
  },
  {
    key: 'latency_mean',
    label: 'Mean latency',
    unit: 'ms',
    getStatic: (r) => r.static.latency_mean_ms,
    getLoadAware: (r) => r.load_aware.latency_mean_ms,
    getAi: (r) => r.ai.latency_mean_ms,
    lowerIsBetter: true,
  },
  {
    key: 'latency_median',
    label: 'Median latency',
    unit: 'ms',
    getStatic: (r) => r.static.latency_median_ms,
    getLoadAware: (r) => r.load_aware.latency_median_ms,
    getAi: (r) => r.ai.latency_median_ms,
    lowerIsBetter: true,
  },
  {
    key: 'latency_p95',
    label: 'p95 latency',
    unit: 'ms',
    getStatic: (r) => r.static.latency_p95_ms,
    getLoadAware: (r) => r.load_aware.latency_p95_ms,
    getAi: (r) => r.ai.latency_p95_ms,
    lowerIsBetter: true,
  },
  {
    key: 'throughput',
    label: 'Delivered throughput',
    unit: 'Mbps',
    getStatic: (r) => r.static.throughput_mbps,
    getLoadAware: (r) => r.load_aware.throughput_mbps,
    getAi: (r) => r.ai.throughput_mbps,
    lowerIsBetter: false,
  },
  {
    key: 'congested_steps',
    label: 'Congested steps (link >90%)',
    unit: '%',
    getStatic: (r) => r.static.congested_steps_pct,
    getLoadAware: (r) => r.load_aware.congested_steps_pct,
    getAi: (r) => r.ai.congested_steps_pct,
    lowerIsBetter: true,
  },
  {
    key: 'flows_at_cap',
    label: 'Flows at delay cap',
    unit: '%',
    getStatic: (r) => r.static.flows_at_cap_pct,
    getLoadAware: (r) => r.load_aware.flows_at_cap_pct,
    getAi: (r) => r.ai.flows_at_cap_pct,
    lowerIsBetter: true,
  },
  {
    key: 'flapping',
    label: 'Route flapping',
    unit: '%',
    getStatic: (r) => r.static.flapping_pct,
    getLoadAware: (r) => r.load_aware.flapping_pct,
    getAi: (r) => r.ai.flapping_pct,
    lowerIsBetter: true,
  },
  {
    key: 'recovery',
    label: 'Recovery after failure',
    unit: 'steps',
    getStatic: (r) => r.static.recovery_steps,
    getLoadAware: (r) => r.load_aware.recovery_steps,
    getAi: (r) => r.ai.recovery_steps,
    lowerIsBetter: true,
    format: (v) => Math.round(v).toString(),
  },
  {
    key: 'fallback_rate',
    label: 'AI fallback rate',
    unit: '%',
    getStatic: () => 0,
    getLoadAware: () => 0,
    getAi: (r) => r.ai.fallback_rate_pct,
    lowerIsBetter: true,
  },
];

export const MetricTable: React.FC<MetricTableProps> = ({ results, className = '' }) => {
  const { mode } = useViewport();

  // Helper to determine best value
  const getBestStrategy = (row: MetricRowDef) => {
    const s = row.getStatic(results);
    const l = row.getLoadAware(results);
    const a = row.getAi(results);

    // AI fallback rate is only applicable to AI
    if (row.key === 'fallback_rate') return 'ai';

    if (row.lowerIsBetter) {
      const min = Math.min(s, l, a);
      if (l === min && a === min) return 'tie';
      if (s === min) return 'static';
      if (l === min) return 'load_aware';
      return 'ai';
    } else {
      const max = Math.max(s, l, a);
      if (l === max && a === max) return 'tie';
      if (s === max) return 'static';
      if (l === max) return 'load_aware';
      return 'ai';
    }
  };

  // Delta calculation vs static
  const getAiDelta = (row: MetricRowDef) => {
    if (row.key === 'fallback_rate') return null;
    const s = row.getStatic(results);
    const a = row.getAi(results);
    if (s === 0) return null;
    const diffPct = ((a - s) / s) * 100;
    const isGood = row.lowerIsBetter ? diffPct < 0 : diffPct > 0;
    return {
      text: `${diffPct > 0 ? '+' : ''}${diffPct.toFixed(1)}% vs static`,
      isGood,
    };
  };

  // Mobile stacked card layout
  if (mode === 'mobile') {
    return (
      <div className={`space-y-4 ${className}`}>
        {/* Strategy Summary Cards */}
        <div className="grid grid-cols-1 gap-3">
          <div className="p-4 bg-brand-surface border border-brand-border rounded-lg">
            <div className="flex items-center gap-2 mb-3">
              <span className="w-3 h-3 rounded-sm bg-[#64748B]" />
              <h3 className="text-h3 font-semibold text-brand-text-primary">Static Dijkstra</h3>
            </div>
            <div className="grid grid-cols-2 gap-2 text-caption">
              <div>
                <span className="text-brand-text-muted">Packet loss:</span>
                <p className="font-mono text-body font-bold text-brand-text-primary">{results.static.loss}%</p>
              </div>
              <div>
                <span className="text-brand-text-muted">Median latency:</span>
                <p className="font-mono text-body font-bold text-brand-text-primary">{results.static.latency_median_ms} ms</p>
              </div>
              <div>
                <span className="text-brand-text-muted">Delivered throughput:</span>
                <p className="font-mono text-body font-bold text-brand-text-primary">{results.static.throughput_mbps} Mbps</p>
              </div>
              <div>
                <span className="text-brand-text-muted">Recovery:</span>
                <p className="font-mono text-body font-bold text-brand-text-primary">{results.static.recovery_steps} steps</p>
              </div>
            </div>
          </div>

          <div className="p-4 bg-brand-surface border-2 border-brand-primary/40 rounded-lg">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm bg-[#2563EB]" />
                <h3 className="text-h3 font-semibold text-brand-text-primary">Load-aware Dijkstra</h3>
              </div>
              <span className="text-[11px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 font-medium">Baseline</span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-caption">
              <div>
                <span className="text-brand-text-muted">Packet loss:</span>
                <p className="font-mono text-body font-bold text-brand-text-primary flex items-center gap-1">
                  {results.load_aware.loss}%
                  {results.load_aware.loss <= results.ai.loss && <Check className="w-3.5 h-3.5 text-emerald-600" />}
                </p>
              </div>
              <div>
                <span className="text-brand-text-muted">Median latency:</span>
                <p className="font-mono text-body font-bold text-brand-text-primary">{results.load_aware.latency_median_ms} ms</p>
              </div>
              <div>
                <span className="text-brand-text-muted">Delivered throughput:</span>
                <p className="font-mono text-body font-bold text-brand-text-primary">{results.load_aware.throughput_mbps} Mbps</p>
              </div>
              <div>
                <span className="text-brand-text-muted">Recovery:</span>
                <p className="font-mono text-body font-bold text-brand-text-primary">{results.load_aware.recovery_steps} steps</p>
              </div>
            </div>
          </div>

          <div className="p-4 bg-emerald-50/50 dark:bg-emerald-950/20 border-2 border-emerald-500/40 rounded-lg">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm bg-[#16A34A]" />
                <h3 className="text-h3 font-semibold text-brand-text-primary">AI Agent</h3>
              </div>
              <span className="text-[11px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 font-medium">Evaluated</span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-caption">
              <div>
                <span className="text-brand-text-muted">Packet loss:</span>
                <p className="font-mono text-body font-bold text-brand-text-primary flex items-center gap-1">
                  {results.ai.loss}%
                  {results.ai.loss <= results.load_aware.loss && <Check className="w-3.5 h-3.5 text-emerald-600" />}
                </p>
                <span className="text-[10px] text-emerald-700 font-medium">
                  {((results.ai.loss - results.static.loss) / results.static.loss * 100).toFixed(0)}% vs static
                </span>
              </div>
              <div>
                <span className="text-brand-text-muted">Median latency:</span>
                <p className="font-mono text-body font-bold text-brand-text-primary">{results.ai.latency_median_ms} ms</p>
              </div>
              <div>
                <span className="text-brand-text-muted">Delivered throughput:</span>
                <p className="font-mono text-body font-bold text-brand-text-primary">{results.ai.throughput_mbps} Mbps</p>
              </div>
              <div>
                <span className="text-brand-text-muted">Fallback rate:</span>
                <p className="font-mono text-body font-bold text-brand-text-primary">{results.ai.fallback_rate_pct}%</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Desktop & Tablet Full Comparison Table
  return (
    <div className={`overflow-x-auto bg-brand-surface border border-brand-border rounded-lg ${className}`}>
      <table className="w-full text-left border-collapse">
        <thead>
          <tr className="border-b border-brand-border bg-brand-bg/50">
            <th className="py-3 px-4 text-overline text-brand-text-muted">Metric</th>
            <th className="py-3 px-4 text-overline text-brand-text-muted text-right">
              <span className="inline-flex items-center gap-1.5 justify-end">
                <span className="w-2.5 h-2.5 rounded-sm bg-[#64748B]" />
                Static Dijkstra
              </span>
            </th>
            <th className="py-3 px-4 text-overline text-brand-text-muted text-right">
              <span className="inline-flex items-center gap-1.5 justify-end">
                <span className="w-2.5 h-2.5 rounded-sm bg-[#2563EB]" />
                Load-aware Dijkstra
              </span>
            </th>
            <th className="py-3 px-4 text-overline text-brand-text-muted text-right bg-emerald-50/30 dark:bg-emerald-950/10">
              <span className="inline-flex items-center gap-1.5 justify-end">
                <span className="w-2.5 h-2.5 rounded-sm bg-[#16A34A]" />
                AI Agent
              </span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-brand-border text-body">
          {METRIC_ROWS.map((row) => {
            const best = getBestStrategy(row);
            const delta = getAiDelta(row);
            const valStatic = row.getStatic(results);
            const valLoad = row.getLoadAware(results);
            const valAi = row.getAi(results);

            const formatVal = (v: number) =>
              row.format ? row.format(v) : v.toString();

            return (
              <tr key={row.key} className="hover:bg-brand-bg/30 transition-colors">
                <td className="py-3 px-4 font-medium text-brand-text-primary">
                  {row.label}
                  <span className="ml-1 text-caption text-brand-text-muted font-normal">({row.unit})</span>
                </td>

                {/* Static */}
                <td className="py-3 px-4 text-right font-mono text-brand-text-secondary tabular-nums">
                  <span className={best === 'static' ? 'font-bold text-brand-text-primary' : ''}>
                    {formatVal(valStatic)}
                  </span>
                  {best === 'static' && (
                    <Check className="w-3.5 h-3.5 inline ml-1.5 text-emerald-600 align-baseline" />
                  )}
                </td>

                {/* Load-aware */}
                <td className="py-3 px-4 text-right font-mono text-brand-text-secondary tabular-nums">
                  <span className={best === 'load_aware' || best === 'tie' ? 'font-bold text-brand-text-primary' : ''}>
                    {formatVal(valLoad)}
                  </span>
                  {(best === 'load_aware' || best === 'tie') && (
                    <Check className="w-3.5 h-3.5 inline ml-1.5 text-emerald-600 align-baseline" />
                  )}
                </td>

                {/* AI Agent */}
                <td className="py-3 px-4 text-right font-mono text-brand-text-secondary tabular-nums bg-emerald-50/20 dark:bg-emerald-950/10">
                  <div>
                    <span className={best === 'ai' || best === 'tie' ? 'font-bold text-brand-text-primary' : ''}>
                      {formatVal(valAi)}
                    </span>
                    {(best === 'ai' || best === 'tie') && (
                      <Check className="w-3.5 h-3.5 inline ml-1.5 text-emerald-600 align-baseline" />
                    )}
                  </div>
                  {delta && (
                    <div
                      className={`text-[11px] font-sans font-medium mt-0.5 ${
                        delta.isGood ? 'text-emerald-700 dark:text-emerald-400' : 'text-amber-700 dark:text-amber-400'
                      }`}
                    >
                      {delta.text}
                    </div>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
