import { useMemo } from 'react';
import type { StatusResponse } from '../types/types';
import './StatsCounter.css';

interface StatsCounterProps {
  status: StatusResponse | null;
}

function StatsCounter({ status }: StatsCounterProps) {
  const stats = useMemo(() => {
    if (!status) {
      return { 
        totalDecisions: 0, 
        totalPurchases: 0,
        round: 0,
        progress: 0
      };
    }

    return {
      totalDecisions: status.cumulative_decisions || 0,
      totalPurchases: status.cumulative_purchases || 0,
      round: status.round || 0,
      progress: ((status.round || 0) / 720) * 100
    };
  }, [status]);

  const formatNumber = (num: number) => {
    if (num >= 1000000) {
      return (num / 1000000).toFixed(1) + 'M';
    }
    if (num >= 1000) {
      return (num / 1000).toFixed(1) + 'K';
    }
    return num.toLocaleString();
  };

  return (
    <div className="stats-counter">
      <div className="stat-card decisions">
        <div className="stat-icon">✈️</div>
        <div className="stat-content">
          <div className="stat-label">Kit Loads</div>
          <div className="stat-value">{formatNumber(stats.totalDecisions)}</div>
        </div>
      </div>
      
      <div className="stat-card purchases">
        <div className="stat-icon">📦</div>
        <div className="stat-content">
          <div className="stat-label">Purchases</div>
          <div className="stat-value">{formatNumber(stats.totalPurchases)}</div>
        </div>
      </div>
      
      <div className="stat-card progress-card">
        <div className="stat-icon">⏱️</div>
        <div className="stat-content">
          <div className="stat-label">Progress</div>
          <div className="stat-value">{stats.progress.toFixed(1)}%</div>
        </div>
        <div className="progress-bar">
          <div 
            className="progress-fill" 
            style={{ width: `${stats.progress}%` }}
          />
        </div>
      </div>
    </div>
  );
}

export default StatsCounter;
