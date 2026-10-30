import { Topology } from '../types/network';

// Reference Network: Office-HQ (6 routers R1 to R6, 12 PCs, 2 servers)
export const TOPOLOGY_OFFICE_HQ: Topology = {
  id: 'topo-office-hq',
  name: 'Office-HQ',
  nodes: [
    // Routers
    { id: 'R1', type: 'router', label: 'R1 Core North', x: 280, y: 120 },
    { id: 'R2', type: 'router', label: 'R2 Core East', x: 520, y: 120 },
    { id: 'R3', type: 'router', label: 'R3 Dist Central', x: 400, y: 260 },
    { id: 'R4', type: 'router', label: 'R4 Edge West', x: 180, y: 380 },
    { id: 'R5', type: 'router', label: 'R5 Edge South', x: 400, y: 440 },
    { id: 'R6', type: 'router', label: 'R6 Edge East', x: 620, y: 380 },
    
    // Servers (Leafs)
    { id: 'S1', type: 'server', label: 'S1 App Server', x: 200, y: 40 },
    { id: 'S2', type: 'server', label: 'S2 DB Primary', x: 600, y: 40 },

    // 12 PCs (Leafs attached to routers R3, R4, R5, R6)
    { id: 'PC1', type: 'pc', label: 'PC-Finance-1', x: 80, y: 340 },
    { id: 'PC2', type: 'pc', label: 'PC-Finance-2', x: 80, y: 420 },
    { id: 'PC3', type: 'pc', label: 'PC-Sales-1', x: 140, y: 500 },
    { id: 'PC4', type: 'pc', label: 'PC-Sales-2', x: 260, y: 520 },
    { id: 'PC5', type: 'pc', label: 'PC-Dev-1', x: 360, y: 540 },
    { id: 'PC6', type: 'pc', label: 'PC-Dev-2', x: 440, y: 540 },
    { id: 'PC7', type: 'pc', label: 'PC-Ops-1', x: 540, y: 520 },
    { id: 'PC8', type: 'pc', label: 'PC-Ops-2', x: 680, y: 500 },
    { id: 'PC9', type: 'pc', label: 'PC-HR-1', x: 720, y: 420 },
    { id: 'PC10', type: 'pc', label: 'PC-HR-2', x: 720, y: 340 },
    { id: 'PC11', type: 'pc', label: 'PC-Exec-1', x: 340, y: 190 },
    { id: 'PC12', type: 'pc', label: 'PC-Exec-2', x: 460, y: 190 },
  ],
  links: [
    // Core Backbone Links
    { id: 'L-R1-R2', src: 'R1', dst: 'R2', bandwidth_mbps: 1000, latency_ms: 2, loss_percent: 0 },
    { id: 'L-R1-R3', src: 'R1', dst: 'R3', bandwidth_mbps: 1000, latency_ms: 3, loss_percent: 0 },
    { id: 'L-R2-R3', src: 'R2', dst: 'R3', bandwidth_mbps: 1000, latency_ms: 3, loss_percent: 0 },
    { id: 'L-R3-R4', src: 'R3', dst: 'R4', bandwidth_mbps: 500, latency_ms: 5, loss_percent: 0 },
    { id: 'L-R3-R5', src: 'R3', dst: 'R5', bandwidth_mbps: 500, latency_ms: 4, loss_percent: 0 },
    { id: 'L-R3-R6', src: 'R3', dst: 'R6', bandwidth_mbps: 500, latency_ms: 5, loss_percent: 0 },
    { id: 'L-R4-R5', src: 'R4', dst: 'R5', bandwidth_mbps: 200, latency_ms: 8, loss_percent: 0 },
    { id: 'L-R5-R6', src: 'R5', dst: 'R6', bandwidth_mbps: 200, latency_ms: 8, loss_percent: 0 },
    { id: 'L-R1-R4', src: 'R1', dst: 'R4', bandwidth_mbps: 500, latency_ms: 6, loss_percent: 0 },
    { id: 'L-R2-R6', src: 'R2', dst: 'R6', bandwidth_mbps: 500, latency_ms: 6, loss_percent: 0 },

    // Servers to Core
    { id: 'L-S1-R1', src: 'S1', dst: 'R1', bandwidth_mbps: 1000, latency_ms: 1, loss_percent: 0 },
    { id: 'L-S2-R2', src: 'S2', dst: 'R2', bandwidth_mbps: 1000, latency_ms: 1, loss_percent: 0 },

    // Host Access Links (Leafs)
    { id: 'L-PC1-R4', src: 'PC1', dst: 'R4', bandwidth_mbps: 100, latency_ms: 5, loss_percent: 0 },
    { id: 'L-PC2-R4', src: 'PC2', dst: 'R4', bandwidth_mbps: 100, latency_ms: 5, loss_percent: 0 },
    { id: 'L-PC3-R4', src: 'PC3', dst: 'R4', bandwidth_mbps: 100, latency_ms: 5, loss_percent: 0 },
    { id: 'L-PC4-R5', src: 'PC4', dst: 'R5', bandwidth_mbps: 100, latency_ms: 5, loss_percent: 0 },
    { id: 'L-PC5-R5', src: 'PC5', dst: 'R5', bandwidth_mbps: 100, latency_ms: 5, loss_percent: 0 },
    { id: 'L-PC6-R5', src: 'PC6', dst: 'R5', bandwidth_mbps: 100, latency_ms: 5, loss_percent: 0 },
    { id: 'L-PC7-R5', src: 'PC7', dst: 'R5', bandwidth_mbps: 100, latency_ms: 5, loss_percent: 0 },
    { id: 'L-PC8-R6', src: 'PC8', dst: 'R6', bandwidth_mbps: 100, latency_ms: 5, loss_percent: 0 },
    { id: 'L-PC9-R6', src: 'PC9', dst: 'R6', bandwidth_mbps: 100, latency_ms: 5, loss_percent: 0 },
    { id: 'L-PC10-R6', src: 'PC10', dst: 'R6', bandwidth_mbps: 100, latency_ms: 5, loss_percent: 0 },
    { id: 'L-PC11-R3', src: 'PC11', dst: 'R3', bandwidth_mbps: 100, latency_ms: 4, loss_percent: 0 },
    { id: 'L-PC12-R3', src: 'PC12', dst: 'R3', bandwidth_mbps: 100, latency_ms: 4, loss_percent: 0 },
  ],
};

// Tree-like topology variant (illustrates where all 3 routing strategies perform almost identically)
export const TOPOLOGY_TREE: Topology = {
  id: 'topo-tree-hierarchy',
  name: 'Branch Tree Network',
  nodes: [
    { id: 'TR1', type: 'router', label: 'TR1 Gateway', x: 400, y: 80 },
    { id: 'TR2', type: 'router', label: 'TR2 Dist West', x: 260, y: 220 },
    { id: 'TR3', type: 'router', label: 'TR3 Dist East', x: 540, y: 220 },
    { id: 'TR4', type: 'router', label: 'TR4 Access A', x: 180, y: 360 },
    { id: 'TR5', type: 'router', label: 'TR5 Access B', x: 620, y: 360 },
    { id: 'TS1', type: 'server', label: 'TS1 Central Storage', x: 400, y: 20 },
    { id: 'TPC1', type: 'pc', label: 'TPC1 User A', x: 120, y: 460 },
    { id: 'TPC2', type: 'pc', label: 'TPC2 User B', x: 220, y: 460 },
    { id: 'TPC3', type: 'pc', label: 'TPC3 User C', x: 580, y: 460 },
    { id: 'TPC4', type: 'pc', label: 'TPC4 User D', x: 680, y: 460 },
  ],
  links: [
    { id: 'TL-1', src: 'TS1', dst: 'TR1', bandwidth_mbps: 1000, latency_ms: 1, loss_percent: 0 },
    { id: 'TL-2', src: 'TR1', dst: 'TR2', bandwidth_mbps: 500, latency_ms: 4, loss_percent: 0 },
    { id: 'TL-3', src: 'TR1', dst: 'TR3', bandwidth_mbps: 500, latency_ms: 4, loss_percent: 0 },
    { id: 'TL-4', src: 'TR2', dst: 'TR4', bandwidth_mbps: 200, latency_ms: 6, loss_percent: 0 },
    { id: 'TL-5', src: 'TR3', dst: 'TR5', bandwidth_mbps: 200, latency_ms: 6, loss_percent: 0 },
    { id: 'TL-6', src: 'TPC1', dst: 'TR4', bandwidth_mbps: 100, latency_ms: 5, loss_percent: 0 },
    { id: 'TL-7', src: 'TPC2', dst: 'TR4', bandwidth_mbps: 100, latency_ms: 5, loss_percent: 0 },
    { id: 'TL-8', src: 'TPC3', dst: 'TR5', bandwidth_mbps: 100, latency_ms: 5, loss_percent: 0 },
    { id: 'TL-9', src: 'TPC4', dst: 'TR5', bandwidth_mbps: 100, latency_ms: 5, loss_percent: 0 },
  ],
};
