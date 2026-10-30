import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useViewport } from '../../context/ViewportContext';
import { Lock, Mail, Eye, EyeOff, AlertCircle, ArrowRight } from 'lucide-react';

export const P02Login: React.FC = () => {
  const { login } = useAuth();
  const { navigate } = useViewport();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorBanner(null);

    try {
      const user = await login(email, password);
      navigate(user.role === 'admin' ? '/admin/queue' : '/dashboard');
    } catch (error) {
      setErrorBanner(error instanceof Error ? error.message : 'Sign-in failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-brand-bg flex flex-col justify-center items-center p-4">
      <div className="w-full max-w-md bg-brand-surface border border-brand-border rounded-xl p-8 shadow-xl">
        <div className="text-center mb-6">
          <div className="w-10 h-10 rounded-lg bg-brand-primary text-white flex items-center justify-center font-bold text-h3 mx-auto mb-3">
            NR
          </div>
          <h1 className="text-h1 font-bold text-brand-text-primary">Log in to NetRoute AI</h1>
          <p className="text-body text-brand-text-secondary mt-1">
            Access your network topologies & simulation benchmarks
          </p>
        </div>

        {errorBanner && (
          <div className="mb-4 p-3 bg-rose-50 border border-rose-300 dark:bg-rose-950/40 dark:border-rose-800 rounded-lg flex items-center gap-2 text-rose-800 dark:text-rose-200 text-caption font-medium">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorBanner}</span>
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="text-label text-brand-text-primary block mb-1">Work Email</label>
            <div className="relative">
              <Mail className="w-4 h-4 text-brand-text-muted absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-brand-bg border border-brand-border rounded-lg text-body text-brand-text-primary focus:outline-none focus:ring-2 focus:ring-brand-primary"
              />
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-label text-brand-text-primary">Password</label>
              <button
                type="button"
                onClick={() => navigate('/forgot-password')}
                className="text-caption text-brand-primary hover:underline font-medium"
              >
                Forgot password?
              </button>
            </div>
            <div className="relative">
              <Lock className="w-4 h-4 text-brand-text-muted absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type={showPassword ? 'text' : 'password'}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-9 pr-10 py-2 bg-brand-bg border border-brand-border rounded-lg text-body text-brand-text-primary focus:outline-none focus:ring-2 focus:ring-brand-primary"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-brand-text-muted hover:text-brand-text-primary"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <input type="checkbox" id="remember" defaultChecked className="rounded text-brand-primary" />
            <label htmlFor="remember" className="text-caption text-brand-text-secondary select-none">
              Remember this device for 30 days
            </label>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-2.5 rounded-lg bg-brand-primary text-white text-btn font-semibold hover:opacity-90 transition-opacity flex items-center justify-center gap-2 disabled:opacity-50 touch-target"
          >
            {isLoading ? <span>Signing in...</span> : <span>Log In</span>}
          </button>
        </form>

        <p className="mt-6 text-center text-caption text-brand-text-secondary">
          Don't have an account?{' '}
          <button
            onClick={() => navigate('/register')}
            className="text-brand-primary font-semibold hover:underline"
          >
            Register
          </button>
        </p>
      </div>
    </div>
  );
};
