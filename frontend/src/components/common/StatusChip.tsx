import React from 'react';
import { PlanStatus } from '../../types/plan';
import { 
  FileEdit, 
  Clock, 
  AlertCircle, 
  CheckCircle2, 
  XCircle, 
  Play, 
  CheckCheck 
} from 'lucide-react';

interface StatusChipProps {
  status: PlanStatus;
  className?: string;
}

export const StatusChip: React.FC<StatusChipProps> = ({ status, className = '' }) => {
  switch (status) {
    case 'Draft':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-caption font-medium bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border border-slate-300 dark:border-slate-700 ${className}`}>
          <FileEdit className="w-3.5 h-3.5" />
          Draft
        </span>
      );
    case 'Pending Review':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-caption font-medium bg-amber-50 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300 border border-amber-300 dark:border-amber-800 ${className}`}>
          <Clock className="w-3.5 h-3.5 animate-pulse" />
          Pending Review
        </span>
      );
    case 'Changes Requested':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-caption font-medium bg-orange-50 text-orange-800 dark:bg-orange-950/40 dark:text-orange-300 border border-orange-300 dark:border-orange-800 ${className}`}>
          <AlertCircle className="w-3.5 h-3.5" />
          Changes Requested
        </span>
      );
    case 'Approved':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-caption font-medium bg-emerald-50 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800 ${className}`}>
          <CheckCircle2 className="w-3.5 h-3.5" />
          Approved
        </span>
      );
    case 'Rejected':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-caption font-medium bg-rose-50 text-rose-800 dark:bg-rose-950/40 dark:text-rose-300 border border-rose-300 dark:border-rose-800 ${className}`}>
          <XCircle className="w-3.5 h-3.5" />
          Rejected
        </span>
      );
    case 'Running':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-caption font-medium bg-blue-50 text-blue-800 dark:bg-blue-950/40 dark:text-blue-300 border border-blue-300 dark:border-blue-800 ${className}`}>
          <Play className="w-3.5 h-3.5 fill-current animate-pulse" />
          Running
        </span>
      );
    case 'Completed':
      return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-caption font-medium bg-teal-50 text-teal-800 dark:bg-teal-950/40 dark:text-teal-300 border border-teal-300 dark:border-teal-800 ${className}`}>
          <CheckCheck className="w-3.5 h-3.5" />
          Completed
        </span>
      );
    default:
      return null;
  }
};
