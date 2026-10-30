import { NotificationItem } from '../types/user';

export const MOCK_NOTIFICATIONS: NotificationItem[] = [
  {
    id: 'notif-1',
    type: 'plan_approved',
    title: 'Plan Approved',
    message: 'Office-HQ Core (v2) has been approved by admin Riya Shah. Ready to simulate.',
    time: '2026-10-17 04:15 PM',
    read: false,
    linkTo: '/plans/plan-office-hq',
  },
  {
    id: 'notif-2',
    type: 'changes_requested',
    title: 'Changes Requested',
    message: 'Branch Office West requires modifications: "Please add a backup link between R2 and R4".',
    time: '2026-10-16 10:45 AM',
    read: false,
    linkTo: '/plans/plan-branch-west',
  },
  {
    id: 'notif-3',
    type: 'simulation_completed',
    title: 'Simulation Run Finished',
    message: 'Run #run-hq-101 (Office-HQ) completed. AI cut loss by 62% over static routing.',
    time: '2026-10-18 02:40 PM',
    read: true,
    linkTo: '/results/run-hq-101',
  },
  {
    id: 'notif-4',
    type: 'review_pending',
    title: 'Review Queue Item',
    message: 'Datacenter Mesh (v1) submitted by Kavya Patel is waiting for review (SLA: On time).',
    time: '2026-10-19 09:10 AM',
    read: false,
    linkTo: '/admin/review/plan-dc-mesh',
  },
  {
    id: 'notif-5',
    type: 'share_expiring',
    title: 'Share Link Expiring',
    message: 'Shared benchmark token tok_hq_share_8f2a will expire in 3 days.',
    time: '2026-10-20 09:00 AM',
    read: true,
    linkTo: '/results/run-hq-101/share',
  },
];
