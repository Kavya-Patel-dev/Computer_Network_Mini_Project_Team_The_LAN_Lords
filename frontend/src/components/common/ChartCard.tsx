import React, { ReactNode, useState } from 'react';
import { Table, Download, Eye } from 'lucide-react';

interface ChartCardProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
  tableData?: Array<Record<string, any>>;
  className?: string;
}

export const ChartCard: React.FC<ChartCardProps> = ({
  title,
  subtitle,
  children,
  tableData,
  className = '',
}) => {
  const [showTableModal, setShowTableModal] = useState(false);

  const handleExportCSV = () => {
    if (!tableData || tableData.length === 0) return;
    const headers = Object.keys(tableData[0]).join(',');
    const rows = tableData.map((row) => Object.values(row).join(',')).join('\n');
    const csvContent = `data:text/csv;charset=utf-8,${headers}\n${rows}`;
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `${title.toLowerCase().replace(/\s+/g, '_')}_data.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className={`bg-brand-surface border border-brand-border rounded-lg p-5 flex flex-col justify-between ${className}`}>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <h3 className="text-h3 font-semibold text-brand-text-primary">{title}</h3>
          {subtitle && <p className="text-caption text-brand-text-muted mt-0.5">{subtitle}</p>}
        </div>

        <div className="flex items-center gap-2">
          {tableData && (
            <button
              onClick={() => setShowTableModal(true)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-caption font-medium rounded-md bg-brand-bg border border-brand-border text-brand-text-secondary hover:text-brand-primary transition-colors focus:outline-none"
              title="View chart values as table"
            >
              <Table className="w-3.5 h-3.5" />
              <span>View as table</span>
            </button>
          )}

          <button
            onClick={handleExportCSV}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 text-caption font-medium rounded-md bg-brand-bg border border-brand-border text-brand-text-secondary hover:text-brand-primary transition-colors focus:outline-none"
            title="Export CSV"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export</span>
          </button>
        </div>
      </div>

      {/* Main Chart Body */}
      <div className="w-full min-h-[260px] flex items-center justify-center">
        {children}
      </div>

      {/* Accessible Table Modal when requested */}
      {showTableModal && tableData && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-brand-surface border border-brand-border rounded-lg p-6 max-w-2xl w-full max-h-[80vh] overflow-y-auto shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h4 className="text-h3 font-semibold text-brand-text-primary">
                Tabular Data: {title}
              </h4>
              <button
                onClick={() => setShowTableModal(false)}
                className="text-caption font-semibold px-2.5 py-1 rounded bg-brand-bg border border-brand-border text-brand-text-secondary hover:text-brand-text-primary"
              >
                Close
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-body border-collapse">
                <thead>
                  <tr className="border-b border-brand-border">
                    {Object.keys(tableData[0]).map((k) => (
                      <th key={k} className="py-2 px-3 text-overline text-brand-text-muted">
                        {k}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-brand-border">
                  {tableData.map((row, idx) => (
                    <tr key={idx} className="hover:bg-brand-bg/50">
                      {Object.values(row).map((val, vIdx) => (
                        <td key={vIdx} className="py-2 px-3 font-mono text-caption text-brand-text-secondary">
                          {val}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
