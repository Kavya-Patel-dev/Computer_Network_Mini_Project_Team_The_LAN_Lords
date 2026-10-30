import React, { useEffect, useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { api } from '../../api/client';
import { PageHeader } from '../../components/common/PageHeader';
import { EmptyState } from '../../components/common/EmptyState';
import { Share2, Plus, Copy, Trash2, ExternalLink, Check } from 'lucide-react';

type ShareRow = { id: string; run_id: string; plan_name: string; created_at: string; expires_at: string; views: number; status: 'active' | 'expired' | 'revoked' };
type NewShare = { id: string; token: string; expires_at: string };

export const U19ShareLinks: React.FC = () => {
  const { navigate, currentPath } = useViewport();
  const runId = currentPath.split('/')[2] || '';
  const [links, setLinks] = useState<ShareRow[]>([]);
  const [newShare, setNewShare] = useState<NewShare | null>(null);
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = async () => {
    try {
      const data = await api.get<{ items: ShareRow[] }>('/shares');
      setLinks(data.items);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load share links.');
    } finally { setLoading(false); }
  };

  useEffect(() => { void refresh(); }, []);

  const createLink = async () => {
    if (!runId) { setError('Open Share Links from a saved simulation result so its run ID is available.'); return; }
    setBusy(true); setError(null); setNotice(null);
    try {
      const result = await api.post<{ id: string; token: string; expires_at: string }>(`/results/${encodeURIComponent(runId)}/share`);
      setNewShare(result);
      setNotice('The token is shown once. Copy and save the URL now; the server stores only its hash.');
      await refresh();
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not create the share link.'); }
    finally { setBusy(false); }
  };

  const copyLink = async () => {
    if (!newShare) return;
    const url = `${window.location.origin}/#/share/${newShare.token}`;
    try { await navigator.clipboard.writeText(url); setCopied(true); setNotice('Share URL copied.'); }
    catch { setError('Clipboard access was blocked. Copy the displayed URL manually.'); }
  };

  const revoke = async (shareId: string) => {
    try {
      await api.delete(`/shares/id/${encodeURIComponent(shareId)}`);
      setNotice('Share access revoked.');
      if (newShare?.id === shareId) setNewShare(null);
      await refresh();
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not revoke this share link.'); }
  };

  const generatedUrl = newShare ? `${window.location.origin}/#/share/${newShare.token}` : '';

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <PageHeader
        title="Shared Benchmark Links"
        subtitle="Manage secure, tokenized URLs for saved simulation results. A generated token is shown only once."
        actions={
          <button disabled={busy || !runId} onClick={() => void createLink()} className="px-4 py-2 rounded-lg bg-brand-primary text-white text-btn font-semibold hover:opacity-90 flex items-center gap-1.5 shadow-sm disabled:opacity-50">
            <Plus className="w-4 h-4 stroke-[2.5]" /><span>{busy ? 'Creating…' : 'Generate New Share Link'}</span>
          </button>
        }
      />
      {(error || notice) && <div role={error ? 'alert' : 'status'} className={`p-3 rounded-lg border text-caption ${error ? 'border-rose-300 text-rose-700' : 'border-brand-border bg-brand-surface text-brand-text-secondary'}`}>{error || notice}</div>}
      {newShare && (
        <div className="p-4 rounded-lg border border-emerald-300 bg-emerald-50 dark:bg-emerald-950/30 space-y-2">
          <p className="text-caption font-semibold text-emerald-800 dark:text-emerald-200">Copy this new URL now. The API does not retain the unencrypted token.</p>
          <div className="flex gap-2"><input readOnly value={generatedUrl} className="min-w-0 flex-1 px-3 py-2 rounded border border-brand-border bg-brand-bg font-mono text-caption" /><button onClick={() => void copyLink()} className="px-3 py-2 rounded bg-brand-primary text-white text-caption">{copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}</button></div>
          <button onClick={() => navigate(`/share/${newShare.token}`)} className="text-caption text-brand-primary underline">Preview shared result</button>
        </div>
      )}
      {loading ? <div className="p-6 text-center text-brand-text-muted">Loading share links…</div> : links.length === 0 ? (
        <EmptyState icon={<Share2 className="w-6 h-6" />} title="No share links generated yet" description="Create a time-limited link from an existing simulation result." />
      ) : (
        <div className="overflow-x-auto bg-brand-surface border border-brand-border rounded-xl shadow-sm">
          <table className="w-full text-left text-body border-collapse">
            <thead><tr className="border-b border-brand-border bg-brand-bg/60"><th className="py-3 px-4 text-overline text-brand-text-muted">Associated Plan</th><th className="py-3 px-4 text-overline text-brand-text-muted">Token URL</th><th className="py-3 px-4 text-overline text-brand-text-muted">Status</th><th className="py-3 px-4 text-overline text-brand-text-muted">Expiry</th><th className="py-3 px-4 text-overline text-brand-text-muted text-right">Views</th><th className="py-3 px-4 text-overline text-brand-text-muted text-right">Actions</th></tr></thead>
            <tbody className="divide-y divide-brand-border text-caption">
              {links.map((link) => <tr key={link.id} className="hover:bg-brand-bg/30">
                <td className="py-3 px-4 font-semibold text-brand-text-primary">{link.plan_name}<span className="block font-mono text-[10px] text-brand-text-muted">Run {link.run_id}</span></td>
                <td className="py-3 px-4 font-mono text-brand-text-secondary">{newShare?.id === link.id ? generatedUrl : 'Token is not retrievable after creation'}</td>
                <td className="py-3 px-4"><span className="px-2 py-0.5 rounded-full font-semibold uppercase text-[10px]">{link.status}</span></td>
                <td className="py-3 px-4 text-brand-text-muted">{new Date(link.expires_at).toLocaleString()}</td>
                <td className="py-3 px-4 text-right font-mono tabular-nums font-bold text-brand-text-primary">{link.views}</td>
                <td className="py-3 px-4 text-right space-x-1">
                  {newShare?.id === link.id && <button onClick={() => void copyLink()} title="Copy URL" className="p-1.5 rounded hover:bg-brand-bg text-brand-text-muted">{copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}</button>}
                  {newShare?.id === link.id && <button onClick={() => navigate(`/share/${newShare.token}`)} title="Preview" className="p-1.5 rounded hover:bg-brand-bg text-brand-text-muted"><ExternalLink className="w-4 h-4" /></button>}
                  {link.status === 'active' && <button onClick={() => void revoke(link.id)} title="Revoke access" className="p-1.5 rounded hover:bg-rose-50 text-brand-text-muted hover:text-rose-600"><Trash2 className="w-4 h-4" /></button>}
                </td>
              </tr>)}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
