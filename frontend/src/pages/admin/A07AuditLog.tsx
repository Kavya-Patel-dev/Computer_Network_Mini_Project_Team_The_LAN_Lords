import React, { useEffect, useMemo, useState } from 'react';
import { api } from '../../api/client';
import { PageHeader } from '../../components/common/PageHeader';
import { Search, Download, ChevronDown, ChevronRight, Shield, Info } from 'lucide-react';

export const A07AuditLog: React.FC = () => {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [resultFilter, setResultFilter] = useState('all');
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<{ items: any[] }>('/admin/audit?limit=100')
      .then((data) => { setLogs(data.items); setError(null); })
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load audit events.'))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => logs.filter((log) => {
    const matchesSearch =
      log.actor.toLowerCase().includes(search.toLowerCase()) ||
      log.action.toLowerCase().includes(search.toLowerCase()) ||
      log.target.toLowerCase().includes(search.toLowerCase());
    const matchesResult = resultFilter === 'all' || log.result.toLowerCase() === resultFilter;
    return matchesSearch && matchesResult;
  }), [logs, search, resultFilter]);
  const exportCsv = () => {
    const rows = [['time', 'actor', 'role', 'action', 'target', 'result'], ...filtered.map((log) => [log.time, log.actor, log.role, log.action, log.target, log.result])];
    const csv = rows.map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\r\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a'); link.href = url; link.download = 'audit-log.csv'; link.click(); URL.revokeObjectURL(url);
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <PageHeader
        title="Security Audit Log"
        subtitle="Chronological audit records of all administrative decisions, submissions, and credential events."
        actions={
          <button
            onClick={exportCsv}
            className="px-3.5 py-2 rounded-lg border border-brand-border bg-brand-surface hover:bg-brand-bg text-caption font-semibold flex items-center gap-1.5 shadow-sm"
          >
            <Download className="w-4 h-4 text-brand-text-muted" />
            <span>Export CSV</span>
          </button>
        }
      />

      {/* Persistent Immutability Note */}
      <div className="p-3 bg-brand-surface border border-brand-border rounded-lg flex items-center gap-2 text-caption text-brand-text-muted">
        <Info className="w-4 h-4 text-brand-primary shrink-0" />
        <span>Audit events are recorded by the server and visible only to administrators. Storage retention follows the database deployment policy.</span>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 bg-brand-surface border border-brand-border rounded-lg p-3">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-brand-text-muted absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by actor, action type, or target..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-brand-bg border border-brand-border text-body text-brand-text-primary placeholder:text-brand-text-muted focus:outline-none focus:ring-1 focus:ring-brand-primary"
          />
        </div>

        <div className="flex items-center gap-1.5 text-caption">
          {['all', 'success', 'denied'].map((r) => (
            <button
              key={r}
              onClick={() => setResultFilter(r)}
              className={`px-3 py-1 rounded-full font-medium transition-colors ${
                resultFilter === r
                  ? 'bg-brand-primary text-white font-semibold'
                  : 'bg-brand-bg text-brand-text-secondary hover:text-brand-text-primary border border-brand-border'
              }`}
            >
              {r === 'all' ? 'All Results' : r === 'success' ? 'Success' : 'Denied'}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto bg-brand-surface border border-brand-border rounded-xl shadow-sm">
        <table className="w-full text-left text-body border-collapse">
          <thead>
            <tr className="border-b border-brand-border bg-brand-bg/60">
              <th className="py-3 px-4 w-8"></th>
              <th className="py-3 px-4 text-overline text-brand-text-muted">Timestamp</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted">Actor</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted">Action</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted">Target Resource</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted">Result</th>
              <th className="py-3 px-4 text-overline text-brand-text-muted font-mono">Source</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-brand-border text-caption">
            {error && <tr><td colSpan={7} className="p-6 text-center text-rose-600">{error}</td></tr>}
            {!error && loading && <tr><td colSpan={7} className="p-6 text-center text-brand-text-muted">Loading audit events…</td></tr>}
            {!error && !loading && filtered.length === 0 && <tr><td colSpan={7} className="p-6 text-center text-brand-text-muted">No audit events match the selected filters.</td></tr>}
            {!loading && filtered.map((log) => {
              const isExpanded = expandedId === log.id;

              return (
                <React.Fragment key={log.id}>
                  <tr
                    onClick={() => setExpandedId(isExpanded ? null : log.id)}
                    className="hover:bg-brand-bg/30 cursor-pointer transition-colors"
                  >
                    <td className="py-3 px-2 text-center text-brand-text-muted">
                      {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                    </td>
                    <td className="py-3 px-4 font-mono text-brand-text-secondary">{log.time}</td>
                    <td className="py-3 px-4 font-semibold text-brand-text-primary">
                      {log.actor}{' '}
                      <span className="text-[10px] uppercase font-mono text-brand-text-muted">({log.role})</span>
                    </td>
                    <td className="py-3 px-4 font-mono font-medium text-brand-primary">{log.action}</td>
                    <td className="py-3 px-4 text-brand-text-secondary">{log.target}</td>
                    <td className="py-3 px-4">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                          log.result === 'Success'
                            ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                            : 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300'
                        }`}
                      >
                        {log.result}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono text-brand-text-muted">Not captured</td>
                  </tr>

                  {/* Expanded JSON Details */}
                  {isExpanded && (
                    <tr className="bg-brand-bg/60">
                      <td colSpan={7} className="p-4 pl-12">
                        <div className="bg-slate-950 text-slate-200 p-3 rounded-lg font-mono text-[11px] space-y-1 border border-slate-800">
                          <p className="text-slate-400 font-bold mb-1">// Event Payload Parameters:</p>
                          {Object.entries(log.details).map(([k, v]) => (
                            <div key={k} className="flex gap-2">
                              <span className="text-blue-400 font-bold">"{k}":</span>
                              <span className="text-emerald-400">{JSON.stringify(v)}</span>
                            </div>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
