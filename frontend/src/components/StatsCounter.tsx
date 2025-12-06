import { useMemo } from 'react';
import type { StatusResponse } from '../types/types';
import './StatsCounter.css';

interface StatsCounterProps {
  status: StatusResponse | null;
}

function StatsCounter({ status }: StatsCounterProps) {
  const stats = useMemo(() => {
    if (!status) {
      return { totalDecisions: 0, totalPurchases: 0 };
    }

    // Use cumulative counters from backend (never decrease)
    return {
      totalDecisions: status.cumulative_decisions || 0,
      totalPurchases: status.cumulative_purchases || 0,
    };
  }, [status]);

  return (
    <div className="stats-counter">
      <div className="stat-card decisions">
        <div className="stat-icon">✈️</div>
        <div className="stat-content">
          <div className="stat-label">Total Decisions</div>
          <div className="stat-value">{stats.totalDecisions}</div>
        </div>
      </div>
      <div className="stat-card purchases">
        <div className="stat-icon">📦</div>
        <div className="stat-content">
          <div className="stat-label">Total Purchases</div>
          <div className="stat-value">{stats.totalPurchases}</div>
        </div>
      </div>
    </div>
  );
}

export default StatsCounter;
