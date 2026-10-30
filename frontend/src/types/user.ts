import { ScenarioType } from './network';

export type UserRole = 'user' | 'admin';
export type UserStatus = 'active' | 'deactivated';

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  status: UserStatus;
  plansCount: number;
  lastActive: string;
  createdAt: string;
  sessionsCount?: number;
}

export interface ShareLink {
  token: string;
  run_id: string;
  planName: string;
  created_at: string;
  expires_at: string;
  views: number;
  status: 'active' | 'expired' | 'revoked';
  scenarios: ScenarioType[];
}

export interface AuditLogEntry {
  id: string;
  time: string;
  actor: string;
  role: UserRole;
  action: string;
  target: string;
  result: 'Success' | 'Denied';
  ip: string;
  details: Record<string, string>;
}

export type NotificationType =
  | 'plan_approved'
  | 'changes_requested'
  | 'plan_rejected'
  | 'simulation_completed'
  | 'simulation_failed'
  | 'review_pending'
  | 'share_expiring';

export interface NotificationItem {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  time: string;
  read: boolean;
  linkTo: string;
}
