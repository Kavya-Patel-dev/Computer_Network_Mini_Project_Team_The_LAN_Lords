import React, { useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { useAuth } from '../../context/AuthContext';
import { Shield, Check, Info } from 'lucide-react';

export const P03Register: React.FC = () => {
  const { navigate } = useViewport();
  const { register } = useAuth();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const hasLength = password.length >= 8;
  const hasNumber = /\d/.test(password);
  const hasSpecial = /[!@#$%^&*]/.test(password);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    if (!hasLength || !hasNumber || !hasSpecial) {
      setError('Use at least 8 characters with a number and a special character.');
      return;
    }
    setIsLoading(true);
    try {
      await register(name, email, password);
      navigate('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Account registration failed.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-brand-bg flex flex-col justify-center items-center p-4">
      <div className="w-full max-w-md bg-brand-surface border border-brand-border rounded-xl p-8 shadow-xl">
        <div className="text-center mb-6">
          <h1 className="text-h1 font-bold text-brand-text-primary">Create Your Account</h1>
          <p className="text-body text-brand-text-secondary mt-1">
            Start modeling and evaluating adaptive routing architectures
          </p>
          <div className="mt-3 p-2 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 rounded text-caption text-blue-800 dark:text-blue-300 flex items-center justify-center gap-1.5">
            <Info className="w-4 h-4 shrink-0" />
            <span>New accounts are always User accounts; admins are added by invitation.</span>
          </div>
        </div>

        {error && <div role="alert" className="mb-4 p-3 bg-rose-50 border border-rose-300 dark:bg-rose-950/40 dark:border-rose-800 rounded-lg text-rose-800 dark:text-rose-200 text-caption">{error}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-label text-brand-text-primary block mb-1">Full Name *</label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Kavya Patel"
              className="w-full px-3 py-2 bg-brand-bg border border-brand-border rounded-lg text-body text-brand-text-primary focus:outline-none focus:ring-2 focus:ring-brand-primary"
            />
          </div>

          <div>
            <label className="text-label text-brand-text-primary block mb-1">Work Email *</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@organization.com"
              className="w-full px-3 py-2 bg-brand-bg border border-brand-border rounded-lg text-body text-brand-text-primary focus:outline-none focus:ring-2 focus:ring-brand-primary"
            />
          </div>

          <div>
            <label className="text-label text-brand-text-primary block mb-1">Password *</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 bg-brand-bg border border-brand-border rounded-lg text-body text-brand-text-primary focus:outline-none focus:ring-2 focus:ring-brand-primary"
            />
            {/* Password checklist */}
            <div className="mt-2 space-y-1 text-caption text-brand-text-muted">
              <div className={`flex items-center gap-1.5 ${hasLength ? 'text-emerald-600 font-medium' : ''}`}>
                <Check className="w-3.5 h-3.5" /> At least 8 characters
              </div>
              <div className={`flex items-center gap-1.5 ${hasNumber ? 'text-emerald-600 font-medium' : ''}`}>
                <Check className="w-3.5 h-3.5" /> Includes a number
              </div>
              <div className={`flex items-center gap-1.5 ${hasSpecial ? 'text-emerald-600 font-medium' : ''}`}>
                <Check className="w-3.5 h-3.5" /> Includes a special character
              </div>
            </div>
          </div>

          <div>
            <label className="text-label text-brand-text-primary block mb-1">Confirm Password *</label>
            <input
              type="password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-3 py-2 bg-brand-bg border border-brand-border rounded-lg text-body text-brand-text-primary focus:outline-none focus:ring-2 focus:ring-brand-primary"
            />
          </div>

          <div className="flex items-center gap-2">
            <input type="checkbox" required id="terms" className="rounded text-brand-primary" />
            <label htmlFor="terms" className="text-caption text-brand-text-secondary select-none">
              I accept the Simulation Usage Policy and Research Disclosures
            </label>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-2.5 rounded-lg bg-brand-primary text-white text-btn font-semibold hover:opacity-90 transition-opacity touch-target"
          >
            {isLoading ? 'Creating account…' : 'Create Account'}
          </button>
        </form>

        <p className="mt-6 text-center text-caption text-brand-text-secondary">
          Already registered?{' '}
          <button
            onClick={() => navigate('/login')}
            className="text-brand-primary font-semibold hover:underline"
          >
            Log In
          </button>
        </p>
      </div>
    </div>
  );
};
