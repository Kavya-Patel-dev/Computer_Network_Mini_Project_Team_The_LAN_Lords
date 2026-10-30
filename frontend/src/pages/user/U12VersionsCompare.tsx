import React, { useEffect, useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { api } from '../../api/client';
import { Plan, PlanVersion } from '../../types/plan';
import { PageHeader } from '../../components/common/PageHeader';
import { AlertCircle, ArrowLeft, History } from 'lucide-react';

export const U12VersionsCompare: React.FC = () => {
  const { currentPath, navigate } = useViewport();
  const planId = currentPath.split('/')[2] || '';
  const [plan, setPlan] = useState<Plan | null>(null);
  const [versions, setVersions] = useState<PlanVersion[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!planId) return;
    api.get<Plan>(`/records/${encodeURIComponent(planId)}`)
      .then((value) => { setPlan(value); setVersions(value.versions || []); })
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load version history.'));
  }, [planId]);

  if (error) return <div role="alert" className="p-6 text-rose-700">{error}</div>;
  if (!plan) return <div className="p-6 text-brand-text-muted">Loading saved version history…</div>;

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <PageHeader title={`Version History: ${plan.name}`} subtitle={`Current saved version ${plan.version}.`} actions={<button onClick={() => navigate(`/plans/${plan.id}`)} className="px-3 py-2 rounded-lg border border-brand-border bg-brand-surface text-caption flex items-center gap-2"><ArrowLeft className="w-4 h-4" />Plan details</button>} />
      <div className="p-4 rounded-lg border border-amber-300 bg-amber-50 text-amber-900 text-caption flex gap-2"><AlertCircle className="w-4 h-4 shrink-0 mt-0.5" /><span>The API currently stores version event summaries, not immutable topology snapshots. This page shows the real audit trail; side-by-side topology diffs are unavailable until snapshots are added.</span></div>
      {versions.length === 0 ? <div className="p-6 bg-brand-surface border border-brand-border rounded-xl text-brand-text-muted">No version events are recorded.</div> : (
        <ol className="space-y-3">{[...versions].reverse().map((version, index) => <li key={`${version.version}-${version.date}-${index}`} className="bg-brand-surface border border-brand-border rounded-xl p-4 flex gap-3"><History className="w-5 h-5 text-brand-primary mt-0.5 shrink-0" /><div className="flex-1 space-y-1"><div className="flex flex-wrap justify-between gap-2"><strong>{version.version} · {version.summary}</strong><span className="text-caption text-brand-text-muted">{new Date(version.date).toLocaleString()}</span></div><p className="text-caption text-brand-text-secondary">By {version.author} · {version.status}{version.decision ? ` · ${version.decision}` : ''}</p></div></li>)}</ol>
      )}
    </div>
  );
};
