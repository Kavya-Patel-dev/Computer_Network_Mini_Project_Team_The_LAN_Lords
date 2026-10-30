import React from 'react';
import { useViewport } from '../../context/ViewportContext';
import { MailCheck, AlertCircle } from 'lucide-react';

export const P06VerifyEmail: React.FC = () => {
  const { navigate } = useViewport();

  return (
    <div className="min-h-screen bg-brand-bg flex flex-col justify-center items-center p-4">
      <div className="w-full max-w-md bg-brand-surface border border-brand-border rounded-xl p-8 shadow-xl text-center">
        <div className="w-12 h-12 rounded-full bg-blue-50 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-800 text-brand-primary flex items-center justify-center mx-auto mb-4">
          <MailCheck className="w-6 h-6" />
        </div>

        <h1 className="text-h1 font-bold text-brand-text-primary">Check Your Inbox</h1>
        <p className="text-body text-brand-text-secondary mt-2 mb-4">Email verification is not enabled for this deployment.</p>
        <div className="p-3 bg-amber-50 border border-amber-300 rounded-lg text-caption text-amber-900 mb-6 flex items-start gap-2">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>No verification email was sent. Registration activates user accounts directly.</span>
        </div>

        <div className="space-y-3">
          <button onClick={() => navigate('/login')} className="w-full py-2.5 rounded-lg bg-brand-primary text-white text-btn font-semibold hover:opacity-90 touch-target">Back to Log in</button>
        </div>
      </div>
    </div>
  );
};
