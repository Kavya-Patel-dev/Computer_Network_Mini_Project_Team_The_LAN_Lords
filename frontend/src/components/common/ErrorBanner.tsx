import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface ErrorBannerProps {
  message: string;
  onRetry?: () => void;
  className?: string;
  errorId?: string;
}

export const ErrorBanner: React.FC<ErrorBannerProps> = ({
  message,
  onRetry,
  className = '',
  errorId = 'ERR-503-NET-SIM',
}) => {
  return (
    <div
      role="alert"
      className={`p-4 bg-rose-50 border border-rose-300 dark:bg-rose-950/40 dark:border-rose-800 rounded-lg flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-rose-900 dark:text-rose-200 ${className}`}
    >
      <div className="flex items-center gap-3">
        <AlertTriangle className="w-5 h-5 text-rose-600 dark:text-rose-400 shrink-0" />
        <div>
          <p className="text-body font-medium">{message}</p>
          {errorId && (
            <p className="text-caption text-rose-700/80 dark:text-rose-400/80 font-mono mt-0.5">
              Reference code: {errorId}
            </p>
          )}
        </div>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-rose-600 text-white hover:bg-rose-700 text-caption font-semibold transition-colors shrink-0 touch-target focus:ring-2 focus:ring-rose-500"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Retry
        </button>
      )}
    </div>
  );
};
