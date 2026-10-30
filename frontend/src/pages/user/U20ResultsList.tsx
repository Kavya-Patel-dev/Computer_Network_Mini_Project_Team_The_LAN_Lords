import React, { useEffect, useMemo, useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api/client';
import { PageHeader } from '../../components/common/PageHeader';
import { Search, Eye, Share2, Download } from 'lucide-react';

type RunRow = { id: string; planName: string; version: string; owner: string; date: string; scenariosCount: number; verdictType: 'better' | 'equal' | 'worse'; verdictBadge: string; lossStatic: string | null; lossAi: string | null };

export const U20ResultsList: React.FC = () => {
  const { navigate } = useViewport();
  const { role } = useAuth();
  const [search, setSearch] = useState('');
  const [verdictFilter, setVerdictFilter] = useState('all');
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadRuns = async () => {
    setLoading(true);
    setLoadError(null);
    try { setRuns((await api.get<{ items: RunRow[] }>('/results?limit=100')).items); }
    catch (error) { setLoadError(error instanceof Error ? error.message : 'Could not load saved results.'); }
    finally { setLoading(false); }
  };

  useEffect(() => { void loadRuns(); }, []);

  const filteredRuns = useMemo(() => runs.filter((run) => {
    const matchesSearch = (run.planName + ' ' + run.id).toLowerCase().includes(search.toLowerCase());
    return matchesSearch && (verdictFilter === 'all' || run.verdictType === verdictFilter);
  }), [runs, search, verdictFilter]);

  const shareRun = async (run: RunRow) => {
    try {
      const share = await api.post<{ token: string }>(`/results/${encodeURIComponent(run.id)}/share`);
      const url = window.location.origin + '/#/share/' + share.token;
      await navigator.clipboard.writeText(url);
      setActionMessage('A 14-day share link was copied to the clipboard.');
    } catch (error) {
      setActionMessage(error instanceof Error ? error.message : 'Could not create a share link.');
    }
  };

  const exportRun = async (run: RunRow) => {
    try {
      const payload = await api.get(`/results/${encodeURIComponent(run.id)}`);
      const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' }));
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `routing-result-${run.id}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
      setActionMessage('Saved the actual result JSON.');
    } catch (error) {
      setActionMessage(error instanceof Error ? error.message : 'Could not export this result.');
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <PageHeader
        title="Simulation Results Catalog"
        subtitle="Historical multi-scenario execution runs, honest metrics, and comparative reports."
      />
      {(loadError || actionMessage) && <div role="status" className="p-3 rounded-lg border border-brand-border bg-brand-surface text-caption text-brand-text-secondary">{loadError || actionMessage}<button onClick={() => setActionMessage(null)} className="ml-3 text-brand-primary">Dismiss</button></div>}

      {/* Filter and Search Bar */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 bg-brand-surface border border-brand-border rounded-lg p-3">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-brand-text-muted absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search runs by plan name or ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-brand-bg border border-brand-border text-body text-brand-text-primary placeholder:text-brand-text-muted focus:outline-none focus:ring-1 focus:ring-brand-primary"
          />
        </div>

        <div className="flex items-center gap-1.5 overflow-x-auto text-caption">
          {['all', 'better', 'equal', 'worse'].map((v) => (
            <button
              key={v}
              onClick={() => setVerdictFilter(v)}
              className={`px-3 py-1 rounded-full whitespace-nowrap font-medium transition-colors ${
                verdictFilter === v
                  ? 'bg-brand-primary text-white font-semibold'
                  : 'bg-brand-bg text-brand-text-secondary hover:text-brand-text-primary border border-brand-border'
              }`}
            >
              {v === 'all'
                ? 'All Verdicts'
                : v === 'better'
                ? 'AI Substantial Gain'
                : v === 'equal'
                ? 'About Equal'
                : 'AI Behind Load-Aware'}
            </button>
          ))}
        </div>
      </div>

      {/* Runs Table */}
      <div className="overflow-x-auto bg-brand-surface border border-brand-border rounded-xl shadow-sm">
        <table className="w-full text-left text-body border-collapse">
          <thead>
            <tr className="border-b border-brand-border bg-brand-bg/60">
              <th className="py-3 px-4 text-overline text-brand-text-muted">Run ID & Plan</th>
              {role === 'admin' && (
                <th className="py-3 px-4 text-overline text-brand-text-muted">Owner</th>
              )}
              <th className="py-3 px-4 text-overline text-brand-text-muted">Execution Date</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted">Scenarios</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted">Simulation Verdict</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-brand-border text-caption">
            {filteredRuns.map((run) => (
              <tr
                key={run.id}
                onClick={() => navigate(`/results/${run.id}`)}
                className="hover:bg-brand-bg/30 cursor-pointer transition-colors"
              >
                <td className="py-3.5 px-4">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-body text-brand-text-primary">{run.planName}</span>
                    <span className="font-mono text-[11px] px-1.5 py-0.2 rounded bg-brand-bg border border-brand-border">
                      {run.version}
                    </span>
                  </div>
                  <span className="font-mono text-[11px] text-brand-text-muted">{run.id}</span>
                </td>

                {role === 'admin' && (
                  <td className="py-3.5 px-4 font-medium text-brand-text-secondary">{run.owner}</td>
                )}

                <td className="py-3.5 px-4 text-brand-text-secondary">{run.date}</td>

                <td className="py-3.5 px-4">
                  <span className="px-2 py-0.5 rounded bg-brand-bg border border-brand-border font-mono text-[11px]">
                    {run.scenariosCount} Scenarios
                  </span>
                </td>

                <td className="py-3.5 px-4">
                  <span
                    className={`inline-block px-2.5 py-0.5 rounded-full text-[11px] font-bold ${
                      run.verdictType === 'better'
                        ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                        : run.verdictType === 'equal'
                        ? 'bg-slate-200 text-slate-800 dark:bg-slate-800 dark:text-slate-200'
                        : 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                    }`}
                  >
                    {run.verdictBadge}
                  </span>
                </td>

                <td className="py-3.5 px-4 text-right space-x-1" onClick={(e) => e.stopPropagation()}>
                  <button
                    onClick={() => navigate(`/results/${run.id}`)}
                    className="p-1.5 rounded hover:bg-brand-bg text-brand-text-muted hover:text-brand-primary"
                    title="Open Results Overview"
                  >
                    <Eye className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => void shareRun(run)}
                    className="p-1.5 rounded hover:bg-brand-bg text-brand-text-muted hover:text-brand-text-primary"
                    title="Share Link"
                  >
                    <Share2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => void exportRun(run)}
                    className="p-1.5 rounded hover:bg-brand-bg text-brand-text-muted hover:text-brand-text-primary"
                    title="Export Report"
                  >
                    <Download className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
            {!loading && filteredRuns.length === 0 && <tr><td colSpan={role === 'admin' ? 6 : 5} className="p-6 text-center text-caption text-brand-text-muted">{loadError ? 'Results could not be loaded.' : 'No saved simulation results match this filter.'}</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
};
