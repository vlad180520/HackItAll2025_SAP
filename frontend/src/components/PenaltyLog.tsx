import { useMemo, useState } from 'react';
import type { PenaltyRecord } from '../types/types';
import './PenaltyLog.css';

interface PenaltyLogProps {
  penalties: PenaltyRecord[];
}

function PenaltyLog({ penalties }: PenaltyLogProps) {
  const [showAll, setShowAll] = useState(false);
  
  const sortedPenalties = useMemo(() => {
    return [...penalties].sort((a, b) => {
      if (a.issued_time.day !== b.issued_time.day) {
        return b.issued_time.day - a.issued_time.day;
      }
      return b.issued_time.hour - a.issued_time.hour;
    });
  }, [penalties]);

  const totalPenalty = useMemo(() => {
    return penalties.reduce((sum, p) => sum + p.cost, 0);
  }, [penalties]);

  const penaltyStats = useMemo(() => {
    const stats: Record<string, { count: number; totalCost: number; avgCost: number }> = {};
    penalties.forEach(p => {
      if (!stats[p.code]) {
        stats[p.code] = { count: 0, totalCost: 0, avgCost: 0 };
      }
      stats[p.code].count += 1;
      stats[p.code].totalCost += p.cost;
    });
    
    // Calculate averages
    Object.keys(stats).forEach(code => {
      stats[code].avgCost = stats[code].totalCost / stats[code].count;
    });
    
    return stats;
  }, [penalties]);

  const exportToCSV = () => {
    const headers = ['Day', 'Hour', 'Code', 'Cost', 'Reason'];
    const rows = sortedPenalties.map(p => [
      p.issued_time.day,
      p.issued_time.hour,
      p.code,
      p.cost.toFixed(2),
      `"${p.reason.replace(/"/g, '""')}"` // Escape quotes in reason
    ]);
    
    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.join(','))
    ].join('\n');
    
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `penalties_${new Date().toISOString()}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const displayedPenalties = showAll ? sortedPenalties : sortedPenalties.slice(0, 50);

  return (
    <div className="penalty-log">
      <div className="penalty-header">
        <h3>All Penalties ({penalties.length})</h3>
        <button onClick={exportToCSV} className="export-button">Export CSV</button>
      </div>

      <div className="penalty-summary">
        <div className="summary-item">
          <strong>Total Penalties:</strong> {penalties.length}
        </div>
        <div className="summary-item">
          <strong>Total Cost:</strong> ${totalPenalty.toFixed(2)}
        </div>
        <div className="summary-item">
          <strong>Avg Cost per Penalty:</strong> ${penalties.length > 0 ? (totalPenalty / penalties.length).toFixed(2) : '0.00'}
        </div>
      </div>

      <div className="penalty-breakdown">
        <h4>Penalty Breakdown by Type</h4>
        <table className="penalty-stats-table">
          <thead>
            <tr>
              <th>Code</th>
              <th>Count</th>
              <th>Total Cost</th>
              <th>Avg Cost</th>
              <th>% of Total</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(penaltyStats)
              .sort(([, a], [, b]) => b.totalCost - a.totalCost)
              .map(([code, stats]) => (
                <tr key={code}>
                  <td><strong>{code}</strong></td>
                  <td>{stats.count}</td>
                  <td>${stats.totalCost.toFixed(2)}</td>
                  <td>${stats.avgCost.toFixed(2)}</td>
                  <td>{((stats.totalCost / totalPenalty) * 100).toFixed(1)}%</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      <div className="penalty-table-section">
        <h4>Penalty Details</h4>
        {sortedPenalties.length === 0 ? (
          <p className="no-data">✅ No penalties recorded - Great job!</p>
        ) : (
          <>
            <table className="penalty-details-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Time</th>
                  <th>Code</th>
                  <th>Cost</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {displayedPenalties.map((penalty, idx) => (
                  <tr key={idx}>
                    <td>{sortedPenalties.length - idx}</td>
                    <td>Day {penalty.issued_time.day}, Hour {penalty.issued_time.hour}</td>
                    <td><span className="penalty-code">{penalty.code}</span></td>
                    <td className="cost-cell">${penalty.cost.toFixed(2)}</td>
                    <td className="reason-cell">{penalty.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {sortedPenalties.length > 50 && (
              <div className="show-more">
                <button onClick={() => setShowAll(!showAll)}>
                  {showAll ? 'Show Less' : `Show All ${sortedPenalties.length} Penalties`}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default PenaltyLog;

