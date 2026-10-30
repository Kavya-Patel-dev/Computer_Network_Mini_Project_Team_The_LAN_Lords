import { SimulationRun, ScenarioResult } from '../types/simulation';

// Exact Section 1 reference benchmark for Normal Scenario on Office-HQ
export const OFFICE_HQ_NORMAL_RESULTS: ScenarioResult = {
  static: {
    loss: 3.2,
    latency_mean_ms: 18.6,
    latency_median_ms: 14.2,
    latency_p95_ms: 62.0,
    throughput_mbps: 71.3,
    congested_steps_pct: 41.0,
    flows_at_cap_pct: 17.0,
    flapping_pct: 0.0,
    recovery_steps: 76,
    fallback_rate_pct: 0.0,
  },
  load_aware: {
    loss: 0.4,
    latency_mean_ms: 12.4,
    latency_median_ms: 11.8,
    latency_p95_ms: 24.0,
    throughput_mbps: 83.9,
    congested_steps_pct: 9.0,
    flows_at_cap_pct: 2.0,
    flapping_pct: 36.0,
    recovery_steps: 41,
    fallback_rate_pct: 0.0,
  },
  ai: {
    loss: 0.5,
    latency_mean_ms: 12.6,
    latency_median_ms: 11.9,
    latency_p95_ms: 26.0,
    throughput_mbps: 83.7,
    congested_steps_pct: 10.0,
    flows_at_cap_pct: 2.0,
    flapping_pct: 38.0,
    recovery_steps: 45,
    fallback_rate_pct: 0.9,
  },
};

// Router Failure Variant (Section 1: AI is slightly WORSE than load-aware: 2.4% vs 2.2%)
export const OFFICE_HQ_ROUTER_FAILURE_RESULTS: ScenarioResult = {
  static: {
    loss: 7.8,
    latency_mean_ms: 28.4,
    latency_median_ms: 21.0,
    latency_p95_ms: 94.0,
    throughput_mbps: 64.2,
    congested_steps_pct: 54.0,
    flows_at_cap_pct: 26.0,
    flapping_pct: 0.0,
    recovery_steps: 84,
    fallback_rate_pct: 0.0,
  },
  load_aware: {
    loss: 2.2, // Load-aware slightly beats AI here
    latency_mean_ms: 16.1,
    latency_median_ms: 14.5,
    latency_p95_ms: 42.0,
    throughput_mbps: 79.5,
    congested_steps_pct: 18.0,
    flows_at_cap_pct: 6.0,
    flapping_pct: 42.0,
    recovery_steps: 44,
    fallback_rate_pct: 0.0,
  },
  ai: {
    loss: 2.4, // Section 1 explicit requirement: 2.4% vs 2.2%
    latency_mean_ms: 16.8,
    latency_median_ms: 14.9,
    latency_p95_ms: 46.0,
    throughput_mbps: 78.8,
    congested_steps_pct: 20.0,
    flows_at_cap_pct: 7.0,
    flapping_pct: 46.0,
    recovery_steps: 48,
    fallback_rate_pct: 3.2,
  },
};

// Link Failure Scenario
export const OFFICE_HQ_LINK_FAILURE_RESULTS: ScenarioResult = {
  static: {
    loss: 5.6,
    latency_mean_ms: 22.1,
    latency_median_ms: 17.5,
    latency_p95_ms: 78.0,
    throughput_mbps: 68.4,
    congested_steps_pct: 47.0,
    flows_at_cap_pct: 21.0,
    flapping_pct: 0.0,
    recovery_steps: 79,
    fallback_rate_pct: 0.0,
  },
  load_aware: {
    loss: 1.1,
    latency_mean_ms: 14.0,
    latency_median_ms: 13.1,
    latency_p95_ms: 32.0,
    throughput_mbps: 81.6,
    congested_steps_pct: 14.0,
    flows_at_cap_pct: 4.0,
    flapping_pct: 39.0,
    recovery_steps: 43,
    fallback_rate_pct: 0.0,
  },
  ai: {
    loss: 1.2,
    latency_mean_ms: 14.2,
    latency_median_ms: 13.2,
    latency_p95_ms: 34.0,
    throughput_mbps: 81.3,
    congested_steps_pct: 15.0,
    flows_at_cap_pct: 4.0,
    flapping_pct: 41.0,
    recovery_steps: 46,
    fallback_rate_pct: 1.8,
  },
};

// Traffic Spike Scenario (4x surge)
export const OFFICE_HQ_SPIKE_RESULTS: ScenarioResult = {
  static: {
    loss: 6.9,
    latency_mean_ms: 26.5,
    latency_median_ms: 19.8,
    latency_p95_ms: 88.0,
    throughput_mbps: 66.1,
    congested_steps_pct: 58.0,
    flows_at_cap_pct: 29.0,
    flapping_pct: 0.0,
    recovery_steps: 81,
    fallback_rate_pct: 0.0,
  },
  load_aware: {
    loss: 1.9,
    latency_mean_ms: 15.8,
    latency_median_ms: 14.1,
    latency_p95_ms: 38.0,
    throughput_mbps: 80.2,
    congested_steps_pct: 22.0,
    flows_at_cap_pct: 7.0,
    flapping_pct: 44.0,
    recovery_steps: 46,
    fallback_rate_pct: 0.0,
  },
  ai: {
    loss: 1.7, // AI handles rapid surge slightly smoother
    latency_mean_ms: 15.4,
    latency_median_ms: 13.9,
    latency_p95_ms: 36.0,
    throughput_mbps: 80.8,
    congested_steps_pct: 21.0,
    flows_at_cap_pct: 6.0,
    flapping_pct: 43.0,
    recovery_steps: 44,
    fallback_rate_pct: 1.2,
  },
};

// Bandwidth Drop Scenario (50% drop on core links)
export const OFFICE_HQ_BW_DROP_RESULTS: ScenarioResult = {
  static: {
    loss: 4.8,
    latency_mean_ms: 21.0,
    latency_median_ms: 16.4,
    latency_p95_ms: 71.0,
    throughput_mbps: 69.2,
    congested_steps_pct: 49.0,
    flows_at_cap_pct: 22.0,
    flapping_pct: 0.0,
    recovery_steps: 75,
    fallback_rate_pct: 0.0,
  },
  load_aware: {
    loss: 1.4,
    latency_mean_ms: 14.5,
    latency_median_ms: 13.4,
    latency_p95_ms: 35.0,
    throughput_mbps: 81.0,
    congested_steps_pct: 19.0,
    flows_at_cap_pct: 5.0,
    flapping_pct: 37.0,
    recovery_steps: 42,
    fallback_rate_pct: 0.0,
  },
  ai: {
    loss: 1.5,
    latency_mean_ms: 14.7,
    latency_median_ms: 13.6,
    latency_p95_ms: 36.0,
    throughput_mbps: 80.7,
    congested_steps_pct: 20.0,
    flows_at_cap_pct: 5.0,
    flapping_pct: 39.0,
    recovery_steps: 45,
    fallback_rate_pct: 1.1,
  },
};

// Tree-like network variant (Section 1: Little difference because there are few alternative paths)
export const TREE_NETWORK_RESULTS: ScenarioResult = {
  static: {
    loss: 4.1,
    latency_mean_ms: 19.2,
    latency_median_ms: 15.6,
    latency_p95_ms: 55.0,
    throughput_mbps: 74.2,
    congested_steps_pct: 38.0,
    flows_at_cap_pct: 14.0,
    flapping_pct: 0.0,
    recovery_steps: 68,
    fallback_rate_pct: 0.0,
  },
  load_aware: {
    loss: 3.9,
    latency_mean_ms: 18.9,
    latency_median_ms: 15.2,
    latency_p95_ms: 54.0,
    throughput_mbps: 74.8,
    congested_steps_pct: 36.0,
    flows_at_cap_pct: 13.0,
    flapping_pct: 8.0,
    recovery_steps: 66,
    fallback_rate_pct: 0.0,
  },
  ai: {
    loss: 4.0,
    latency_mean_ms: 19.0,
    latency_median_ms: 15.4,
    latency_p95_ms: 54.5,
    throughput_mbps: 74.6,
    congested_steps_pct: 37.0,
    flows_at_cap_pct: 13.0,
    flapping_pct: 9.0,
    recovery_steps: 67,
    fallback_rate_pct: 0.2,
  },
};

// Generate realistic 60-step time series with events
export const GENERATE_TIME_SERIES = () => {
  const points = [];
  for (let s = 1; s <= 60; s++) {
    const isSpike = s >= 20 && s <= 35;
    const isFailure = s >= 40 && s <= 50;
    
    let baseStaticLoss = 2.8 + (Math.sin(s / 3) * 0.4);
    let baseLoadLoss = 0.35 + (Math.sin(s / 4) * 0.1);
    let baseAiLoss = 0.42 + (Math.cos(s / 4) * 0.12);

    let baseStaticLat = 13.8 + (Math.sin(s / 2) * 1.5);
    let baseLoadLat = 11.6 + (Math.sin(s / 3) * 0.5);
    let baseAiLat = 11.7 + (Math.cos(s / 3) * 0.5);

    if (isSpike) {
      baseStaticLoss += 4.5;
      baseLoadLoss += 1.6;
      baseAiLoss += 1.4;
      baseStaticLat += 14;
      baseLoadLat += 4.2;
      baseAiLat += 3.8;
    }

    if (isFailure) {
      baseStaticLoss += 5.2;
      baseLoadLoss += 1.9;
      baseAiLoss += 2.1;
      baseStaticLat += 16;
      baseLoadLat += 5.1;
      baseAiLat += 5.4;
    }

    let event: string | undefined = undefined;
    if (s === 20) event = 'Traffic Spike (+400%) Begins';
    if (s === 35) event = 'Traffic Normalized';
    if (s === 40) event = 'Core Link L-R3-R5 Failure';
    if (s === 45) event = 'AI & Load-aware Reroute Stabilized';
    if (s === 50) event = 'Link Restored';

    points.push({
      step: s,
      timeSec: s,
      staticLoss: parseFloat(baseStaticLoss.toFixed(2)),
      loadAwareLoss: parseFloat(baseLoadLoss.toFixed(2)),
      aiLoss: parseFloat(baseAiLoss.toFixed(2)),
      staticLatency: parseFloat(baseStaticLat.toFixed(1)),
      loadAwareLatency: parseFloat(baseLoadLat.toFixed(1)),
      aiLatency: parseFloat(baseAiLat.toFixed(1)),
      event,
      isSpike,
      isFailure,
    });
  }
  return points;
};

// Master Simulation Run for Office-HQ
export const MOCK_SIMULATION_RUN_OFFICE_HQ: SimulationRun = {
  runId: 'run-hq-101',
  planId: 'plan-office-hq',
  planName: 'Office-HQ',
  version: 'v2',
  runDate: '2026-10-18 14:32:00',
  trafficPreset: 'Medium (0.10 intensity)',
  selectedScenarios: ['normal', 'link_failure', 'router_failure', 'traffic_spike', 'bandwidth_drop'],
  verdictType: 'better',
  verdictText: 'AI cut packet loss by 62% compared with static routing and is within 8% of load-aware Dijkstra.',
  scenarios: {
    normal: OFFICE_HQ_NORMAL_RESULTS,
    link_failure: OFFICE_HQ_LINK_FAILURE_RESULTS,
    router_failure: OFFICE_HQ_ROUTER_FAILURE_RESULTS,
    traffic_spike: OFFICE_HQ_SPIKE_RESULTS,
    bandwidth_drop: OFFICE_HQ_BW_DROP_RESULTS,
  },
  timeSeries: GENERATE_TIME_SERIES(),
  linkUtilization: {
    'L-R1-R2': { static: 78, loadAware: 64, ai: 66, history: [50, 60, 64, 66, 68] },
    'L-R1-R3': { static: 94, loadAware: 72, ai: 74, history: [70, 75, 78, 74, 72] }, // hotspot for static
    'L-R2-R3': { static: 88, loadAware: 68, ai: 70, history: [65, 68, 70, 71, 70] },
    'L-R3-R4': { static: 91, loadAware: 58, ai: 61, history: [75, 82, 85, 65, 58] },
    'L-R3-R5': { static: 95, loadAware: 76, ai: 75, history: [80, 88, 92, 78, 75] }, // Hotspot
    'L-R3-R6': { static: 86, loadAware: 54, ai: 56, history: [60, 70, 65, 58, 56] },
    'L-R4-R5': { static: 32, loadAware: 62, ai: 59, history: [20, 45, 55, 60, 59] }, // Alternate detour
    'L-R5-R6': { static: 28, loadAware: 58, ai: 61, history: [22, 48, 52, 59, 61] },
    'L-R1-R4': { static: 45, loadAware: 69, ai: 67, history: [35, 55, 65, 68, 67] },
    'L-R2-R6': { static: 42, loadAware: 65, ai: 64, history: [38, 52, 60, 66, 64] },
    'L-S1-R1': { static: 65, loadAware: 65, ai: 65, history: [60, 64, 65, 65, 65] },
    'L-S2-R2': { static: 60, loadAware: 60, ai: 60, history: [58, 60, 60, 60, 60] },
    'L-PC1-R4': { static: 24, loadAware: 24, ai: 24, history: [20, 24, 24, 24, 24] },
    'L-PC5-R5': { static: 48, loadAware: 48, ai: 48, history: [40, 45, 48, 48, 48] },
  },
  candidatePaths: [
    {
      path: ['PC1', 'R4', 'R1', 'R2', 'S2'],
      q_value: 0.94,
      chosen: true,
      reason: 'Path 1 avoids link R3-R5, which is 92% loaded, balancing queue depth across R1-R2 core.',
    },
    {
      path: ['PC1', 'R4', 'R3', 'R2', 'S2'],
      q_value: 0.78,
      chosen: false,
      reason: 'Path 2 passes through R3 central which has high instantaneous buffer occupancy (72%).',
    },
    {
      path: ['PC1', 'R4', 'R5', 'R6', 'R2', 'S2'],
      q_value: 0.65,
      chosen: false,
      reason: 'Path 3 adds 2 extra hops (18ms latency penalty) along lower-bandwidth 200 Mbps edge links.',
    },
    {
      path: ['PC1', 'R4', 'R3', 'R5', 'R6', 'R2', 'S2'],
      q_value: 0.42,
      chosen: false,
      reason: 'Path 4 traverses congested link R3-R5 (92% load) and introduces unnecessary routing loops.',
    },
  ],
  attentionWeights: {
    R1: 0.88,
    R2: 0.74,
    R3: 0.95,
    R4: 0.62,
    R5: 0.85,
    R6: 0.45,
  },
  fallback: {
    used: false,
    reason: undefined,
  },
};

// Simulation Run for Tree Topology (Variant b)
export const MOCK_SIMULATION_RUN_TREE: SimulationRun = {
  runId: 'run-tree-202',
  planId: 'plan-tree',
  planName: 'Branch Tree Network',
  version: 'v1',
  runDate: '2026-10-19 10:15:00',
  trafficPreset: 'Medium (0.10 intensity)',
  selectedScenarios: ['normal', 'link_failure'],
  verdictType: 'equal',
  verdictText: 'Little difference because there are few alternative paths in this hierarchical tree topology.',
  scenarios: {
    normal: TREE_NETWORK_RESULTS,
    link_failure: TREE_NETWORK_RESULTS,
    router_failure: TREE_NETWORK_RESULTS,
    traffic_spike: TREE_NETWORK_RESULTS,
    bandwidth_drop: TREE_NETWORK_RESULTS,
  },
  timeSeries: GENERATE_TIME_SERIES().slice(0, 30),
  linkUtilization: {
    'TL-1': { static: 85, loadAware: 85, ai: 85, history: [80, 85, 85, 85] },
    'TL-2': { static: 72, loadAware: 71, ai: 72, history: [70, 72, 71, 72] },
    'TL-3': { static: 68, loadAware: 68, ai: 68, history: [65, 68, 68, 68] },
    'TL-4': { static: 55, loadAware: 54, ai: 55, history: [50, 55, 54, 55] },
    'TL-5': { static: 52, loadAware: 52, ai: 52, history: [50, 52, 52, 52] },
  },
  candidatePaths: [
    {
      path: ['TPC1', 'TR4', 'TR2', 'TR1', 'TS1'],
      q_value: 0.82,
      chosen: true,
      reason: 'Only available physical uplink tree path between TPC1 and server TS1.',
    },
  ],
  attentionWeights: {
    TR1: 0.99,
    TR2: 0.92,
    TR3: 0.20,
    TR4: 0.85,
    TR5: 0.15,
  },
  fallback: {
    used: false,
  },
};
