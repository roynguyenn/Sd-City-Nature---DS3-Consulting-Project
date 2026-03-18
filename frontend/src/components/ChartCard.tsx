import { ReactNode } from 'react';
import { LoadingSpinner } from './LoadingSpinner';

interface ChartCardProps {
  title: string;
  subtitle?: string;
  loading?: boolean;
  error?: string | null;
  children: ReactNode;
  /** When true, content wrapper has no min-height (for compact content like KPI strip) */
  compact?: boolean;
}

export function ChartCard({
  title,
  subtitle,
  loading = false,
  error = null,
  children,
  compact: _compact = false
}: ChartCardProps) {
  return (
    <div className="bg-white rounded-lg shadow-md p-6 min-w-0 overflow-hidden">
      <div className="mb-4">
        <h3 className="text-xl font-semibold text-gray-800">{title}</h3>
        {subtitle && <p className="text-sm text-gray-600 mt-1">{subtitle}</p>}
      </div>

      {loading && <LoadingSpinner />}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          <p className="font-medium">Error loading data</p>
          <p className="text-sm">{error}</p>
        </div>
      )}

      {!loading && !error && <div className="chart-container min-w-0">{children}</div>}
    </div>
  );
}