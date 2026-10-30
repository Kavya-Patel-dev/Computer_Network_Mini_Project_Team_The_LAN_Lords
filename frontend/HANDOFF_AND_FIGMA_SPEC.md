# NetRoute AI: Complete Design System, Figma Frame Hierarchy & Engineering Handoff Specification

## 1. Product & Architecture Overview
**NetRoute AI** is an intelligent, discrete-event network routing simulation studio allowing network operators and researchers to design topologies, model traffic profiles, and compare three routing policies (**Static Dijkstra**, **Load-aware Dijkstra**, and **AI Agent**) across five stress conditions (**Normal**, **Link Cut Failure**, **Router Hardware Outage**, **4x Traffic Spike Surge**, and **50% Bandwidth Drop**).

### Governance & Roles
Two strictly segregated roles:
- **User ("Kavya Patel"):** Owns plans, edits topologies in Draft or Changes Requested status, submits for review, runs simulations on Approved plans, explores heatmaps and explainability Q-values, and manages external share links.
- **Admin ("Riya Shah", "Arjun Mehta"):** Reviews queued plans with SLA tracking (On time, Due soon, Overdue), annotates diagrams with pins, requests changes or approves, manages operators, and audits platform settings.
- **Self-Review Guard:** When an admin creates their own plan (e.g. *Admin Core Backbone* by Riya Shah), the review panel is blocked with *"Waiting for another admin. You cannot review your own plan."*

> **Backend Enforcement Notice:** UI hiding is for usability only; every permission is enforced by the backend and each forbidden API call returns 403.

---

## 2. Figma File Structure & Frame Naming Hierarchy

```
Figma Master Project /
├── 01 Cover & README
│   └── "00 Cover / Desktop 1440"
├── 02 Tokens & Styles
│   ├── "Tokens / Colors / Light & Dark"
│   ├── "Tokens / Typography / Inter, JetBrains Mono, Noto Sans"
│   └── "Tokens / Status & Heatmaps"
├── 03 Reusable Components
│   ├── "Component / StatusChip / Variants"
│   ├── "Component / Topology / Router & Hosts"
│   ├── "Component / MetricTable / Strategy Benchmarks"
│   ├── "Component / VerdictCard / 3 Variants"
│   └── "Component / KpiCard / Default"
├── 04 Public Pages (P01 - P09)
│   ├── "P01 Landing / Desktop 1440" | "Tablet 768" | "Mobile 390"
│   ├── "P02 Login / Desktop 1440" | "Mobile 390"
│   ├── "P03 Register / Desktop 1440" | "Mobile 390"
│   ├── "P04 Forgot Password / Desktop 1440"
│   ├── "P06 Verify Email / Desktop 1440"
│   ├── "P07 Demo Result / Desktop 1440" | "Mobile 390"
│   ├── "P08 Shared Result / Desktop 1440" | "Mobile 390"
│   └── "P09 Error 403 / 404 / 500 / Offline"
├── 05 User Workspace (U01 - U22)
│   ├── "U01 Dashboard / Desktop 1440" | "Tablet 768" | "Mobile 390"
│   ├── "U02 My Plans / Desktop 1440" | "Mobile 390"
│   ├── "U03 New Plan Mode / Desktop 1440" | "Mobile 390"
│   ├── "U04 Canvas Editor / Desktop 1440" | "Mobile 390 (List View & Canvas)"
│   ├── "U05 Form Table Editor / Desktop 1440"
│   ├── "U06 Upload File / Desktop 1440"
│   ├── "U07 Generate Needs / Desktop 1440"
│   ├── "U08 Traffic & Scenarios / Desktop 1440"
│   ├── "U09 Review & Submit / Desktop 1440"
│   ├── "U10 Plan Detail / Desktop 1440" | "Mobile 390"
│   ├── "U11 Analysis Report / Desktop 1440"
│   ├── "U12 Versions Compare / Desktop 1440"
│   ├── "U13 Run Simulation / Desktop 1440"
│   ├── "U14 Results Overview / Desktop 1440" | "Tablet 768" | "Mobile 390"
│   ├── "U15 Heatmap / Desktop 1440" | "Mobile 390"
│   ├── "U16 Explainability & Q-Values / Desktop 1440"
│   ├── "U17 Failure Timeline / Desktop 1440"
│   ├── "U18 What-If Explorer / Desktop 1440"
│   ├── "U19 Share Links / Desktop 1440"
│   ├── "U20 Results List / Desktop 1440"
│   ├── "U21 Notifications / Desktop 1440"
│   └── "U22 Profile & Settings / Desktop 1440"
├── 06 Admin Suite (A01 - A10)
│   ├── "A01 Review Queue / Desktop 1440" | "Mobile 390"
│   ├── "A02 Review Screen / Desktop 1440" | "Blocked Self-Review"
│   ├── "A03 All Plans / Desktop 1440"
│   ├── "A04 Stats & Analytics / Desktop 1440"
│   ├── "A05 User Directory / Desktop 1440"
│   ├── "A06 User Detail / Desktop 1440"
│   ├── "A07 Audit Log / Desktop 1440"
│   ├── "A08 Platform Settings / Desktop 1440"
│   ├── "A09 Permissions Matrix / Desktop 1440"
│   └── "A10 Model Architecture / Desktop 1440"
└── 07 Overlays (O01 - O15)
    ├── "O01 Submit For Review / Modal & BottomSheet"
    ├── "O02 Withdraw Submission"
    ├── "O03 Delete Draft"
    ├── "O04 Approve Plan"
    ├── "O05 Request Changes"
    ├── "O06 Reject Plan"
    ├── "O07 Invite User"
    ├── "O10 Create Share Link"
    ├── "O11 Export Report Package"
    ├── "O12 Limitations Drawer"
    ├── "O13 Cancel Simulation"
    ├── "O14 Session Expired"
    └── "O15 Delete Account"
```

---

## 3. Section 1 Honesty Rules & Benchmark Dataset

### Core Principles
1. **Never write "AI always wins"**: The AI routing agent is an imitation-trained behavioral model approximating load-aware Dijkstra.
2. **Never display "accuracy"**: Routing efficiency is evaluated on **Packet Loss (%)**, **Latency (ms)**, **Delivered Throughput (Mbps)**, **Route Flapping (%)**, and **Recovery Steps**.
3. **Persistent Notice**: Every results frame contains the note `"Simulation result"`.

### Reference Data: Network "Office-HQ" (6 Routers R1-R6, 12 PCs, 2 Servers)
| Metric | Static Dijkstra | Load-aware Dijkstra | AI Agent (Imitation) | Delta vs Static |
| :--- | :---: | :---: | :---: | :---: |
| **Packet Loss (Normal)** | 3.2% | **0.4%** | **0.5%** | **-62.0% loss** (within 8% of load-aware) |
| **Mean Latency** | 18.6 ms | **12.4 ms** | 12.6 ms | -32.2% |
| **Median Latency** | 14.2 ms | **11.8 ms** | 11.9 ms | -16.2% |
| **p95 Latency** | 62.0 ms | **24.0 ms** | 26.0 ms | -58.0% |
| **Delivered Throughput** | 71.3 Mbps | **83.9 Mbps** | 83.7 Mbps | +17.4% |
| **Congested Steps (&gt;90%)** | 41.0% | **9.0%** | 10.0% | -75.6% |
| **Flows at Delay Cap** | 17.0% | **2.0%** | **2.0%** | -88.2% |
| **Route Flapping** | **0.0%** | 36.0% | 38.0% | Dynamic path switching |
| **Recovery Steps (Failure)** | 76 steps | **41 steps** | 45 steps | -40.8% faster |
| **AI Fallback Rate** | — | — | **0.9%** | Rule-engaged |

### Mandatory Scenarios & Verdict Variants
1. **Variant A (Normal):** Verdict: *"AI cut packet loss by 62% compared with static routing and is within 8% of load-aware Dijkstra."*
2. **Variant B (Router Failure):** AI is slightly **WORSE** than load-aware (**2.4% vs 2.2% loss**), with verdict: *"AI performed slightly worse than load-aware Dijkstra in this scenario (2.4% vs 2.2% packet loss). Safe fallback engaged during detour queue saturation."*
3. **Variant C (Tree Topology):** Verdict: *"All three strategies perform almost the same because the network has few alternative paths."*

---

## 4. Design Tokens & Styling Guide

### Typography Scale
- **Display:** 700 / Desktop 40px (lh 48px), Mobile 32px (lh 40px) • `-0.02em` tracking
- **H1:** 700 / Desktop 28px (lh 36px), Mobile 24px (lh 32px)
- **H2:** 600 / 20px (lh 28px)
- **H3:** 600 / 16px (lh 24px)
- **Body-L:** 400 / 16px (lh 24px)
- **Body:** 400 / Desktop 14px (lh 20px), Mobile 16px (lh 24px)
- **Label:** 500 / 14px (lh 20px)
- **Button:** 600 / Desktop 14px (lh 20px), Mobile 16px (lh 24px)
- **Caption:** 400 / 12px (lh 16px) *(Strictly no text below 12px)*
- **Overline:** 600 / 12px (lh 16px) • uppercase, `+0.06em` tracking
- **KPI:** 700 / Desktop 32px (lh 40px), Mobile 28px (lh 36px) • tabular figures
- **Mono:** 500 / Desktop 13px (lh 20px), Mobile 14px (lh 20px) • tabular figures
- **Localization Line Height:** Add `+4px` line height for Gujarati (ગુજરાતી) and Devanagari (हिन्दी) scripts.

### Color Tokens
- **Light Theme:**
  - Background: `#FFFFFF`
  - Surface: `#F8FAFC`
  - Border: `#E2E8F0`
  - Text Primary: `#0F172A`
  - Text Secondary: `#475569`
  - Text Muted: `#64748B`
  - Primary: `#2563EB` (white text)
  - Success: `#15803D`
  - Warning: `#B45309`
  - Danger: `#B91C1C`
  - Info: `#0E7490`
- **Dark Theme:**
  - Background: `#0B1220`
  - Surface: `#111A2E`
  - Border: `#26324A`
  - Text Primary: `#F1F5F9`
  - Text Secondary: `#CBD5E1`
  - Text Muted: `#94A3B8`
  - Primary: `#60A5FA` (dark text)
  - Success: `#4ADE80`
  - Warning: `#FBBF24`
  - Danger: `#F87171`
  - Info: `#22D3EE`
- **Policy Colors (Identical Across All Charts):**
  - Static Dijkstra: `#64748B` (Slate Gray)
  - Load-aware Dijkstra: `#2563EB` (Royal Blue)
  - AI Agent: `#16A34A` (Emerald Green)
- **Utilization Heatmap Colors (with color-blind markers):**
  - `&lt; 50%`: `#16A34A` (● circle)
  - `50% – 80%`: `#EAB308` (▲ triangle)
  - `80% – 100%`: `#EA580C` (■ square)
  - `&gt; 100%`: `#DC2626` (◆ diamond)
  - Failed Link: `#94A3B8` dashed (✕ cross)

---

## 5. Engineering API Contract & JSON Schema Specifications

### 1. Topology Schema
```typescript
interface Topology {
  id: string;
  name: string;
  nodes: Array<{
    id: string; // e.g. "R1", "PC1", "S1"
    type: "router" | "pc" | "server";
    label: string;
    x?: number;
    y?: number;
  }>;
  links: Array<{
    id: string;
    src: string;
    dst: string;
    bandwidth_mbps: number;
    latency_ms: number;
    loss_percent: number; // 0 to 100
  }>;
}
```

### 2. Traffic Flow Schema
```typescript
interface TrafficConfig {
  mode: "preset" | "manual";
  preset?: "light" | "medium" | "heavy";
  flows?: Array<{
    id: string;
    src: string;
    dst: string;
    demand_mbps: number;
    class: "real_time" | "streaming" | "bulk" | "background";
  }>;
}
```

### 3. Simulation Benchmark Metrics Schema
```typescript
interface StrategyMetrics {
  loss: number;
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

type ScenarioResult = Record<"static" | "load_aware" | "ai", StrategyMetrics>;
```

### 4. Explainability & Attention Weights Schema
```typescript
interface ExplainabilityRecord {
  flow: string; // "PC1 -> S2"
  time: number; // seconds
  candidates: Array<{
    path: string[]; // ["PC1", "R4", "R1", "R2", "S2"]
    q_value: number; // 0.0 to 1.0
    chosen: boolean;
    reason: string;
  }>;
  attention: Record<string, number>; // { "R1": 0.88, "R3": 0.95 }
  fallback: {
    used: boolean;
    reason?: "invalid action" | "failed path" | "no valid candidate" | "overloaded candidate";
  };
}
```
