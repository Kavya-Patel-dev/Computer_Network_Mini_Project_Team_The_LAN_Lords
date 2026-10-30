import React, { useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { Mail, ArrowLeft, AlertCircle } from 'lucide-react';

export const P04ForgotPassword: React.FC = () => {
  const { navigate } = useViewport();
  const [email, setEmail] = useState('');

  return (
    <div className="min-h-screen bg-brand-bg flex flex-col justify-center items-center p-4">
      <div className="w-full max-w-md bg-brand-surface border border-brand-border rounded-xl p-8 shadow-xl">
        <button
          onClick={() => navigate('/login')}
          className="inline-flex items-center gap-1.5 text-caption font-medium text-brand-text-muted hover:text-brand-text-primary mb-4"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Log in
        </button>

        <h1 className="text-h1 font-bold text-brand-text-primary">Reset Password</h1>
        <p className="text-body text-brand-text-secondary mt-1 mb-6">
          Enter your registered email address to receive password reset instructions.
        </p>

        <div className="mb-4 p-3 bg-amber-50 border border-amber-300 rounded-lg text-caption text-amber-900 flex items-start gap-2">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>Password reset email delivery is not configured. No reset email will be sent.</span>
        </div>
        <form onSubmit={(e) => e.preventDefault()} className="space-y-4">
            <div>
              <label className="text-label text-brand-text-primary block mb-1">Work Email</label>
              <div className="relative">
                <Mail className="w-4 h-4 text-brand-text-muted absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@organization.com"
                  className="w-full pl-9 pr-3 py-2 bg-brand-bg border border-brand-border rounded-lg text-body text-brand-text-primary focus:outline-none focus:ring-2 focus:ring-brand-primary"
                />
              </div>
            </div>

            <button type="button" disabled className="w-full py-2.5 rounded-lg bg-brand-primary text-white text-btn font-semibold opacity-50 cursor-not-allowed touch-target">Reset unavailable</button>
        </form>
      </div>
    </div>
  );
};
