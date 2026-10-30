import { ShareLink } from '../types/user';

export const MOCK_SHARE_LINKS: ShareLink[] = [
  {
    token: 'tok_hq_share_8f2a',
    run_id: 'run-hq-101',
    planName: 'Office-HQ Core (v2)',
    created_at: '2026-10-19 14:10',
    expires_at: '2026-11-18 14:10 (29 days remaining)',
    views: 42,
    status: 'active',
    scenarios: ['normal', 'router_failure', 'link_failure'],
  },
  {
    token: 'tok_demo_public_77bc',
    run_id: 'run-hq-101',
    planName: 'Public Demo Network',
    created_at: '2026-10-01 10:00',
    expires_at: '2026-10-15 10:00 (Expired)',
    views: 128,
    status: 'expired',
    scenarios: ['normal'],
  },
  {
    token: 'tok_revoked_internal_33d1',
    run_id: 'run-tree-202',
    planName: 'Branch Tree Hierarchy',
    created_at: '2026-10-19 11:00',
    expires_at: 'Revoked on 2026-10-19',
    views: 3,
    status: 'revoked',
    scenarios: ['normal', 'link_failure'],
  },
];
