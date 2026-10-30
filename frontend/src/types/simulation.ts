import { ScenarioType } from './network';

export type StrategyType = 'static' | 'load_aware' | 'ai';

export interface StrategyMetrics {
  loss: number; // Percentage, e.g. 0.5% (Packet loss, strictly NO "accuracy")
  latency_mean_ms: number;
  latency_median_ms: number;
  latency_p95_ms: number;
  throughput_mbps: number;
  congested_steps_pct: number;
  flows_at_cap_pct: number;
  flapping_pct: number;
  recovery_steps: number;
  fallback_rate_pct: number;
}

export type ScenarioResult = Record<StrategyType, StrategyMetrics>;

export interface TimeSeriesPoint {
  step: number;
  timeSec: number;
  staticLoss: number;
  loadAwareLoss: number;
  aiLoss: number;
  staticLatency: number;
  loadAwareLatency: number;
  aiLatency: number;
  event?: string;
  isSpike?: boolean;
  isFailure?: boolean;
}

export interface CandidatePath {
  path: string[];
  q_value: number;
  chosen: boolean;
  reason?: string;
}

export interface SimulationRun {
  runId: string;
  planId: string;
  planName: string;
  version: string;
  runDate: string;
  trafficPreset: string;
  selectedScenarios: ScenarioType[];
  verdictType: 'better' | 'equal' | 'worse';
  verdictText: string;
  scenarios: Record<ScenarioType, ScenarioResult>;
  timeSeries: TimeSeriesPoint[];
  linkUtilization: Record<string, { static: number; loadAware: number; ai: number; history: number[] }>;
  candidatePaths: CandidatePath[];
  attentionWeights: Record<string, number>;
  fallback: {
    used: boolean;
    reason?: 'invalid action' | 'failed path' | 'no valid candidate' | 'overloaded candidate';
  };
}
