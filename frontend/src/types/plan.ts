import { Topology, TrafficFlow, ScenarioType } from './network';

export type PlanStatus =
  | 'Draft'
  | 'Pending Review'
  | 'Changes Requested'
  | 'Approved'
  | 'Rejected'
  | 'Running'
  | 'Completed';

export interface ReviewAnnotationPin {
  id: string;
  elementId: string; // node or link ID
  author: string;
  role: 'admin';
  time: string;
  note: string;
  resolved: boolean;
}

export interface PlanReviewInfo {
  decision: 'approved' | 'changes_requested' | 'rejected';
  admin: string;
  date: string;
  comment: string;
  tags: string[];
  pins?: ReviewAnnotationPin[];
}

export interface PlanVersion {
  version: string;
  date: string;
  author: string;
  status: PlanStatus;
  decision?: string;
  comment?: string;
  summary: string;
}

export interface Plan {
  id: string;
  name: string;
  description?: string;
  status: PlanStatus;
  version: string;
  owner: string;
  ownerEmail: string;
  submitted_at?: string;
  updated_at: string;
  routerCount: number;
  hostCount: number;
  topology: Topology;
  trafficPreset: 'latency_focused' | 'light' | 'medium' | 'heavy' | 'manual';
  flows: TrafficFlow[];
  selectedScenarios: ScenarioType[];
  review?: PlanReviewInfo;
  versions?: PlanVersion[];
}
