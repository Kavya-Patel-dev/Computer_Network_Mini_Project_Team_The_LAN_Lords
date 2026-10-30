import React, { useEffect, useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { api } from '../../api/client';
import { 
  X, 
  AlertTriangle, 
  CheckCircle, 
  Send, 
  Undo2, 
  Trash2, 
  Share2, 
  Download, 
  HelpCircle, 
  UserPlus, 
  ShieldAlert, 
  PowerOff, 
  Clock 
} from 'lucide-react';

export const ModalContainer: React.FC = () => {
  const { activeOverlay, closeOverlay, overlayPayload, mode, navigate } = useViewport();

  // Local states for inputs in modals
  const [deleteConfirmation, setDeleteConfirmation] = useState('');
  const [adminComment, setAdminComment] = useState('');
  const [reviewNote, setReviewNote] = useState('');
  const [rejectionReason, setRejectionReason] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [actionBusy, setActionBusy] = useState(false);

  const updatePlan = async (action: 'submit' | 'withdraw' | 'delete') => {
    const planId = overlayPayload?.plan?.id;
    if (!planId) {
      setActionError('This plan is missing its saved record ID. Reload the plans list and try again.');
      return;
    }
    setActionBusy(true);
    setActionError(null);
    try {
      if (action === 'delete') await api.delete(`/records/${encodeURIComponent(planId)}`);
      else await api.post(`/records/${encodeURIComponent(planId)}/${action}`);
      window.dispatchEvent(new Event('lanlords:plans-changed'));
      closeOverlay();
      navigate('/plans');
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'The plan action failed.');
    } finally {
      setActionBusy(false);
    }
  };

  const exportResult = async () => {
    const runId = overlayPayload?.runId;
    if (!runId) {
      setActionError('This export is not connected to a saved simulation run.');
      return;
    }
    setActionBusy(true);
    setActionError(null);
    try {
      const result = await api.get(`/results/${encodeURIComponent(runId)}`);
      const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' }));
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `routing-result-${runId}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
      closeOverlay();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Could not download the saved result.');
    } finally {
      setActionBusy(false);
    }
  };

  useEffect(() => {
    if (['O04', 'O05', 'O06'].includes(activeOverlay || '')) {
      setReviewNote(overlayPayload?.note || '');
      setAdminComment(overlayPayload?.note || '');
      setRejectionReason(overlayPayload?.note || '');
      setSelectedTags(overlayPayload?.tags || []);
      setActionError(null);
    }
  }, [activeOverlay, overlayPayload]);

  if (!activeOverlay) return null;

  const isMobile = mode === 'mobile';

  const overlayWrapperClasses = isMobile
    ? 'fixed inset-x-0 bottom-0 z-50 bg-brand-surface border-t border-brand-border rounded-t-2xl max-h-[90vh] overflow-y-auto p-5 shadow-2xl animate-in slide-in-from-bottom'
    : 'fixed z-50 bg-brand-surface border border-brand-border rounded-xl max-w-lg w-full max-h-[85vh] overflow-y-auto p-6 shadow-2xl animate-in fade-in zoom-in-95';

  const tagsList = [
    'Bandwidth too low',
    'No redundancy',
    'Invalid topology',
    'Unrealistic traffic',
    'Bottleneck detected',
    'Other',
  ];

  const toggleTag = (tag: string) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  };

  const confirmReview = async (decision: 'approved' | 'changes_requested' | 'rejected', note: string, tags: string[] = []) => {
    if (!overlayPayload?.onConfirm) return;
    setActionError(null);
    try {
      await overlayPayload.onConfirm(note, tags, decision);
      closeOverlay();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'The review could not be saved.');
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className={overlayWrapperClasses}>
        {/* Modal Header */}
        <div className="flex items-center justify-between pb-3 mb-4 border-b border-brand-border">
          <span className="text-overline text-brand-text-muted">System Overlay ({activeOverlay})</span>
          <button
            onClick={closeOverlay}
            className="p-1 rounded-full text-brand-text-muted hover:text-brand-text-primary hover:bg-brand-bg transition-colors"
            aria-label="Close dialog"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        {actionError && <div role="alert" className="mb-4 p-3 rounded-lg border border-rose-300 bg-rose-50 text-rose-800 text-caption">{actionError}</div>}

        {/* O01: Submit For Review */}
        {activeOverlay === 'O01' && (
          <div className="space-y-4">
            <div className="flex items-center gap-3 text-brand-primary">
              <Send className="w-6 h-6" />
              <h3 className="text-h2 font-bold text-brand-text-primary">Submit Plan for Review</h3>
            </div>
            <p className="text-body text-brand-text-secondary">
              Once submitted, an independent network administrator will inspect your topology,
              flow definitions, and scenario matrix before granting simulation access.
            </p>
            <div className="p-3 bg-brand-bg border border-brand-border rounded-lg text-caption space-y-1">
              <p className="font-semibold text-brand-text-primary">Package Payload:</p>
              <p className="text-brand-text-secondary">• Topology: {overlayPayload?.plan?.routerCount ?? '—'} Routers, {overlayPayload?.plan?.hostCount ?? '—'} Hosts</p>
              <p className="text-brand-text-secondary">• Traffic Profile: {overlayPayload?.plan?.trafficPreset ?? '—'} preset</p>
              <p className="text-brand-text-secondary">• Scenarios: Normal, Failures, Spike & Bandwidth drop</p>
            </div>
            <div className="flex justify-end gap-3 pt-3 border-t border-brand-border">
              <button onClick={closeOverlay} className="px-4 py-2 rounded-lg text-brand-text-secondary hover:bg-brand-bg text-btn">
                Cancel
              </button>
              <button
                onClick={() => void updatePlan('submit')}
                disabled={actionBusy}
                className="px-4 py-2 rounded-lg bg-brand-primary text-white text-btn font-semibold hover:opacity-90"
              >
                {actionBusy ? 'Submitting…' : 'Submit for Review'}
              </button>
            </div>
          </div>
        )}

        {/* O02: Withdraw Submission */}
        {activeOverlay === 'O02' && (
          <div className="space-y-4">
            <div className="flex items-center gap-3 text-amber-600">
              <Undo2 className="w-6 h-6" />
              <h3 className="text-h2 font-bold text-brand-text-primary">Withdraw Submission</h3>
            </div>
            <p className="text-body text-brand-text-secondary">
              Withdrawing returns this plan to <span className="font-semibold text-slate-800 dark:text-slate-200">Draft</span> state.
              The review queue item will be cancelled, and you may edit the topology freely.
            </p>
            <div className="flex justify-end gap-3 pt-3 border-t border-brand-border">
              <button onClick={closeOverlay} className="px-4 py-2 rounded-lg text-brand-text-secondary hover:bg-brand-bg text-btn">
                Keep in Review
              </button>
              <button
                onClick={() => void updatePlan('withdraw')}
                disabled={actionBusy}
                className="px-4 py-2 rounded-lg bg-amber-600 text-white text-btn font-semibold hover:bg-amber-700"
              >
                {actionBusy ? 'Withdrawing…' : 'Withdraw to Draft'}
              </button>
            </div>
          </div>
        )}

        {/* O03: Delete Draft */}
        {activeOverlay === 'O03' && (
          <div className="space-y-4">
            <div className="flex items-center gap-3 text-rose-600">
              <Trash2 className="w-6 h-6" />
              <h3 className="text-h2 font-bold text-brand-text-primary">Delete Draft Plan</h3>
            </div>
            <p className="text-body text-brand-text-secondary">
              This action cannot be undone. To confirm deletion, type the plan name{' '}
              <span className="font-mono font-bold text-brand-text-primary">
                {overlayPayload?.plan?.name || 'Office-HQ Core'}
              </span>{' '}
              below:
            </p>
            <input
              type="text"
              value={deleteConfirmation}
              onChange={(e) => setDeleteConfirmation(e.target.value)}
              placeholder="Type plan name to confirm"
              className="w-full px-3 py-2 border border-brand-border rounded-lg bg-brand-bg text-body"
            />
            <div className="flex justify-end gap-3 pt-3 border-t border-brand-border">
              <button onClick={closeOverlay} className="px-4 py-2 rounded-lg text-brand-text-secondary hover:bg-brand-bg text-btn">
                Cancel
              </button>
              <button
                disabled={deleteConfirmation !== overlayPayload?.plan?.name || actionBusy}
                onClick={() => void updatePlan('delete')}
                className="px-4 py-2 rounded-lg bg-rose-600 text-white text-btn font-semibold hover:bg-rose-700 disabled:opacity-40"
              >
                {actionBusy ? 'Deleting…' : 'Delete Plan'}
              </button>
            </div>
          </div>
        )}

        {/* O04: Approve Plan */}
        {activeOverlay === 'O04' && (
          <div className="space-y-4">
            <div className="flex items-center gap-3 text-emerald-600">
              <CheckCircle className="w-6 h-6" />
              <h3 className="text-h2 font-bold text-brand-text-primary">Approve Network Plan</h3>
            </div>
            <p className="text-body text-brand-text-secondary">
              Approval unlocks simulation runs across all 5 evaluation scenarios for this plan.
            </p>
            <div>
              <label className="text-label text-brand-text-primary block mb-1.5">Optional Reviewer Note:</label>
              <textarea
                rows={3}
                value={reviewNote}
                onChange={(event) => setReviewNote(event.target.value)}
                placeholder="Topology complies with dual-homing requirements and bandwidth capacities..."
                className="w-full p-2.5 bg-brand-bg border border-brand-border rounded-lg text-body"
              />
            </div>
            <div className="flex justify-end gap-3 pt-3 border-t border-brand-border">
              <button onClick={closeOverlay} className="px-4 py-2 rounded-lg text-brand-text-secondary hover:bg-brand-bg text-btn">
                Cancel
              </button>
              <button
                onClick={() => void confirmReview('approved', reviewNote)}
                className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-btn font-semibold hover:bg-emerald-700"
              >
                Confirm Approval
              </button>
            </div>
          </div>
        )}

        {/* O05: Request Changes */}
        {activeOverlay === 'O05' && (
          <div className="space-y-4">
            <div className="flex items-center gap-3 text-orange-600">
              <AlertTriangle className="w-6 h-6" />
              <h3 className="text-h2 font-bold text-brand-text-primary">Request Plan Modifications</h3>
            </div>
            <p className="text-body text-brand-text-secondary">
              The submitter will receive your required feedback and can revise the network to create the next version.
            </p>
            <div>
              <label className="text-label text-brand-text-primary block mb-1.5">Select Issue Tags:</label>
              <div className="flex flex-wrap gap-2">
                {tagsList.map((tag) => (
                  <button
                    key={tag}
                    onClick={() => toggleTag(tag)}
                    className={`px-2.5 py-1 rounded-full text-caption font-medium border transition-colors ${
                      selectedTags.includes(tag)
                        ? 'bg-orange-100 text-orange-800 border-orange-400 dark:bg-orange-950 dark:text-orange-300'
                        : 'bg-brand-bg text-brand-text-secondary border-brand-border hover:border-brand-primary'
                    }`}
                  >
                    {tag}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-label text-brand-text-primary block mb-1.5">Required Feedback Note *:</label>
              <textarea
                rows={3}
                value={adminComment}
                onChange={(e) => setAdminComment(e.target.value)}
                placeholder="Explain the required topology or traffic revisions..."
                className="w-full p-2.5 bg-brand-bg border border-brand-border rounded-lg text-body"
              />
            </div>
            <div className="flex justify-end gap-3 pt-3 border-t border-brand-border">
              <button onClick={closeOverlay} className="px-4 py-2 rounded-lg text-brand-text-secondary hover:bg-brand-bg text-btn">
                Cancel
              </button>
              <button
                disabled={!adminComment.trim()}
                onClick={() => void confirmReview('changes_requested', adminComment, selectedTags)}
                className="px-4 py-2 rounded-lg bg-orange-600 text-white text-btn font-semibold hover:bg-orange-700 disabled:opacity-40"
              >
                Send to User
              </button>
            </div>
          </div>
        )}

        {/* O06: Reject Plan */}
        {activeOverlay === 'O06' && (
          <div className="space-y-4">
            <div className="flex items-center gap-3 text-rose-600">
              <AlertTriangle className="w-6 h-6" />
              <h3 className="text-h2 font-bold text-brand-text-primary">Reject Plan</h3>
            </div>
            <div className="p-3 bg-rose-50 dark:bg-rose-950/40 border border-rose-300 dark:border-rose-800 rounded-lg text-caption text-rose-900 dark:text-rose-200">
              ⚠️ <strong>Warning:</strong> Rejection is final for this version. The user will have to duplicate this plan to submit again.
            </div>
            <div>
              <label className="text-label text-brand-text-primary block mb-1.5">Mandatory Reason for Rejection *:</label>
              <textarea
                rows={3}
                value={rejectionReason}
                onChange={(event) => setRejectionReason(event.target.value)}
                placeholder="Describe reason for permanent rejection..."
                className="w-full p-2.5 bg-brand-bg border border-brand-border rounded-lg text-body"
              />
            </div>
            <div className="flex justify-end gap-3 pt-3 border-t border-brand-border">
              <button onClick={closeOverlay} className="px-4 py-2 rounded-lg text-brand-text-secondary hover:bg-brand-bg text-btn">
                Cancel
              </button>
              <button
                onClick={() => void confirmReview('rejected', rejectionReason)}
                className="px-4 py-2 rounded-lg bg-rose-600 text-white text-btn font-semibold hover:bg-rose-700"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        )}

        {/* O07: Invite User */}
        {activeOverlay === 'O07' && (
          <div className="space-y-4">
            <div className="flex items-center gap-3 text-brand-primary">
              <UserPlus className="w-6 h-6" />
              <h3 className="text-h2 font-bold text-brand-text-primary">Invite New Operator</h3>
            </div>
            <div>
              <label className="text-label text-brand-text-primary block mb-1">Registration:</label>
              <p className="text-body text-brand-text-secondary">New accounts are created through the public registration page. Email invitation delivery is not configured for this deployment.</p>
            </div>
            <div>
              <label className="text-label text-brand-text-primary block mb-1">Role:</label>
              <p className="text-caption text-brand-text-muted">Public registration always creates a user. Admin access can only be granted by an existing administrator.</p>
            </div>
            <div className="flex justify-end gap-3 pt-3 border-t border-brand-border">
              <button onClick={closeOverlay} className="px-4 py-2 rounded-lg text-brand-text-secondary hover:bg-brand-bg text-btn">
                Cancel
              </button>
              <button onClick={() => closeOverlay()} className="px-4 py-2 rounded-lg bg-brand-primary text-white text-btn font-semibold hover:opacity-90">
                Close
              </button>
            </div>
          </div>
        )}

        {/* O10: Create Share Link */}
        {activeOverlay === 'O10' && (
          <div className="space-y-4">
            <div className="flex items-center gap-3 text-brand-primary">
              <Share2 className="w-6 h-6" />
              <h3 className="text-h2 font-bold text-brand-text-primary">Create Read-Only Share Link</h3>
            </div>
            <p className="text-body text-brand-text-secondary">Share links are generated from saved simulation results. This dialog does not create a token; open the results catalog and use Share on the run you want to publish.</p>
            <div className="flex justify-end pt-3 border-t border-brand-border">
              <button onClick={() => { closeOverlay(); navigate('/results'); }} className="px-4 py-2 rounded-lg bg-brand-primary text-white text-btn">
                Open Results
              </button>
            </div>
          </div>
        )}

        {/* O11: Export Report */}
        {activeOverlay === 'O11' && (
          <div className="space-y-4">
            <div className="flex items-center gap-3 text-brand-primary">
              <Download className="w-6 h-6" />
              <h3 className="text-h2 font-bold text-brand-text-primary">Export Saved Simulation Result</h3>
            </div>
            <p className="text-caption text-brand-text-secondary">Download the saved backend result as JSON. PDF and image report generation are not configured.</p>
            <div className="flex justify-end gap-3 pt-3 border-t border-brand-border">
              <button onClick={closeOverlay} className="px-4 py-2 rounded-lg text-brand-text-secondary hover:bg-brand-bg text-btn">
                Cancel
              </button>
              <button
                onClick={() => void exportResult()}
                disabled={actionBusy}
                className="px-4 py-2 rounded-lg bg-brand-primary text-white text-btn font-semibold hover:opacity-90 disabled:opacity-50"
              >
                {actionBusy ? 'Preparing…' : 'Download JSON'}
              </button>
            </div>
          </div>
        )}

        {/* O12: Limitations Drawer (Reachable from every result page) */}
        {activeOverlay === 'O12' && (
          <div className="space-y-4">
            <div className="flex items-center gap-3 text-brand-primary">
              <HelpCircle className="w-6 h-6" />
              <h3 className="text-h2 font-bold text-brand-text-primary">Simulation & AI Model Limitations</h3>
            </div>
            <div className="space-y-3 text-body text-brand-text-secondary leading-relaxed">
              <div className="p-3 bg-brand-bg border border-brand-border rounded-lg">
                <p className="font-semibold text-brand-text-primary mb-1">1. Synthetic Simulation Environment</p>
                <p className="text-caption">
                  All results stem from a discrete-event routing simulation model. No physical hardware switches,
                  ASICs, VLAN tags, or real-world BGP/OSPF daemon convergence times are executed.
                </p>
              </div>

              <div className="p-3 bg-brand-bg border border-brand-border rounded-lg">
                <p className="font-semibold text-brand-text-primary mb-1">2. Imitation-Trained Agent</p>
                <p className="text-caption">
                  The AI routing agent is behavior-cloned from load-aware Dijkstra heuristics. It does not possess
                  magical foresight and does not "always win". Under constrained tree topologies or sudden unannounced
                  router outages, heuristic fallback or load-aware Dijkstra may yield equal or slightly superior performance.
                </p>
              </div>

              <div className="p-3 bg-brand-bg border border-brand-border rounded-lg">
                <p className="font-semibold text-brand-text-primary mb-1">3. Supported Topologies</p>
                <p className="text-caption">
                  Networks must be connected, maintain between 5 and 50 routers, and all host PCs/servers must operate
                  strictly as leaf endpoints.
                </p>
              </div>
            </div>
            <div className="flex justify-end pt-3 border-t border-brand-border">
              <button onClick={closeOverlay} className="px-4 py-2 rounded-lg bg-brand-primary text-white text-btn font-semibold">
                Understood
              </button>
            </div>
          </div>
        )}

        {/* O13: Cancel Simulation */}
        {activeOverlay === 'O13' && (
          <div className="space-y-4">
            <div className="flex items-center gap-3 text-amber-600">
              <AlertTriangle className="w-6 h-6" />
              <h3 className="text-h2 font-bold text-brand-text-primary">Cancel Simulation Run</h3>
            </div>
            <p className="text-body text-brand-text-secondary">
              Simulation in progress. If cancelled now, you can choose to preserve partial telemetry recorded so far
              or discard this run.
            </p>
            <div className="space-y-2 text-caption">
              <label className="flex items-center gap-2">
                <input type="radio" name="cancelAction" defaultChecked className="text-brand-primary" />
                Keep partial scenario results
              </label>
              <label className="flex items-center gap-2">
                <input type="radio" name="cancelAction" className="text-brand-primary" />
                Discard completely
              </label>
            </div>
            <p className="text-caption text-amber-700">The current simulation request cannot be cancelled after it starts. This dialog will not stop backend work.</p>
            <div className="flex justify-end gap-3 pt-3 border-t border-brand-border">
              <button onClick={closeOverlay} className="px-4 py-2 rounded-lg text-brand-text-secondary hover:bg-brand-bg text-btn">
                Keep Running
              </button>
              <button disabled title="Cancellation is not supported by the current simulation API" className="px-4 py-2 rounded-lg bg-amber-600 text-white text-btn font-semibold opacity-50 cursor-not-allowed">
                Cancellation unavailable
              </button>
            </div>
          </div>
        )}

        {/* O14: Session Expired */}
        {activeOverlay === 'O14' && (
          <div className="space-y-4">
            <div className="flex items-center gap-3 text-amber-600">
              <Clock className="w-6 h-6" />
              <h3 className="text-h2 font-bold text-brand-text-primary">Session Expired</h3>
            </div>
            <p className="text-body text-brand-text-secondary">
              Your security session has timed out. Any unsaved network canvas edits have been preserved in your local browser storage.
            </p>
            <div className="flex justify-end pt-3 border-t border-brand-border">
              <button
                onClick={() => {
                  closeOverlay();
                  window.location.hash = '/login';
                }}
                className="px-4 py-2 rounded-lg bg-brand-primary text-white text-btn font-semibold"
              >
                Log In Again
              </button>
            </div>
          </div>
        )}

        {/* O15: Delete Account */}
        {activeOverlay === 'O15' && (
          <div className="space-y-4">
            <div className="flex items-center gap-3 text-rose-600">
              <ShieldAlert className="w-6 h-6" />
              <h3 className="text-h2 font-bold text-brand-text-primary">Delete Account (Danger Zone)</h3>
            </div>
            <p className="text-body text-brand-text-secondary">
              Account deletion and data-retention handling are not configured in this deployment. No data will be deleted here.
            </p>
            <div className="flex justify-end gap-3 pt-3 border-t border-brand-border">
              <button onClick={closeOverlay} className="px-4 py-2 rounded-lg text-brand-text-secondary hover:bg-brand-bg text-btn">
                Cancel
              </button>
              <button disabled className="px-4 py-2 rounded-lg bg-rose-600 text-white text-btn font-semibold opacity-50 cursor-not-allowed">
                Deletion unavailable
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
