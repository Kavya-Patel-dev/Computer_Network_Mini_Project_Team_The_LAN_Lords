import React from 'react';
import { PageHeader } from '../../components/common/PageHeader';
import { Check, X, ShieldAlert, Info } from 'lucide-react';

export const A09PermissionsMatrix: React.FC = () => {
  const matrix = [
    { cap: 'Register & Log in', user: 'Public only', admin: 'Public only', note: 'Public authentication' },
    { cap: 'Create a plan', user: 'Yes', admin: 'Yes (Reviewed by another admin)', note: 'Wizard creation' },
    { cap: 'Edit a plan', user: 'Own (Draft / Changes Requested)', admin: 'Own (Draft / Changes Requested)', note: 'Locked once in review' },
    { cap: 'Submit & Withdraw plan', user: 'Own', admin: 'Own', note: 'Lifecycle actions' },
    { cap: 'Review (Approve / Request Changes / Reject)', user: 'No', admin: 'Any plan except own', note: 'Self-review strictly blocked' },
    { cap: 'Run simulation', user: 'Own approved plan', admin: 'Own approved plan', note: 'Requires prior approval' },
    { cap: 'View plan details', user: 'Own plans only', admin: 'All plans (Read-only for others)', note: 'Global catalog' },
    { cap: 'View simulation results', user: 'Own results', admin: 'All operators results', note: 'Benchmarking matrix' },
    { cap: 'Share & Revoke token links', user: 'Own results', admin: 'Own results', note: 'External links' },
    { cap: 'Delete plan', user: 'Own Draft only', admin: 'Own Draft only', note: 'Permanent deletion' },
    { cap: 'Access Stats & Analytics (A04)', user: 'No', admin: 'Yes', note: 'System metrics' },
    { cap: 'Manage Users & Roles (A05, A06)', user: 'No', admin: 'Yes (Cannot alter self)', note: 'Governance protection' },
    { cap: 'Access Audit Log (A07)', user: 'No', admin: 'Yes (Immutable read-only)', note: 'Security trail' },
    { cap: 'System Settings & SLA (A08)', user: 'No', admin: 'Yes', note: 'Global boundaries' },
    { cap: 'Model Checkpoint Info (A10)', user: 'No', admin: 'Yes', note: 'Architecture inspect' },
  ];

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <PageHeader
        title="Role & Capability Permissions Matrix"
        subtitle="Authoritative access control specification for the two system roles (User and Admin)."
      />

      {/* Security Enforcement Banner */}
      <div className="p-4 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 rounded-xl flex items-center gap-3 text-blue-900 dark:text-blue-200 text-caption font-medium">
        <ShieldAlert className="w-5 h-5 text-brand-primary shrink-0" />
        <span>
          <strong>Backend Enforcement Notice:</strong> UI hiding is for usability only; every permission is enforced by the backend and each forbidden API call returns 403.
        </span>
      </div>

      {/* Permissions Matrix Table */}
      <div className="overflow-x-auto bg-brand-surface border border-brand-border rounded-xl shadow-sm">
        <table className="w-full text-left text-body border-collapse">
          <thead>
            <tr className="border-b border-brand-border bg-brand-bg/60">
              <th className="py-3 px-4 text-overline text-brand-text-muted">Capability / Operation</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted">User Role</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted">Admin Role</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted">Policy Rule Context</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-brand-border text-caption">
            {matrix.map((row, idx) => (
              <tr key={idx} className="hover:bg-brand-bg/30">
                <td className="py-3 px-4 font-bold text-brand-text-primary">{row.cap}</td>
                <td className="py-3 px-4">
                  <div className="flex items-center gap-1.5">
                    {row.user === 'No' ? (
                      <X className="w-4 h-4 text-rose-500 shrink-0" />
                    ) : (
                      <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                    )}
                    <span className={row.user === 'No' ? 'text-brand-text-muted' : 'text-brand-text-primary'}>
                      {row.user}
                    </span>
                  </div>
                </td>
                <td className="py-3 px-4">
                  <div className="flex items-center gap-1.5">
                    <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span className="font-medium text-brand-text-primary">{row.admin}</span>
                  </div>
                </td>
                <td className="py-3 px-4 text-brand-text-muted font-mono text-[11px]">{row.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
