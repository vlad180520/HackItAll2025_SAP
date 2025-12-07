import { useMemo, useState } from 'react';
import type { PenaltyRecord } from '../types/types';
import './PenaltyLog.css';

interface PenaltyLogProps {
  penalties: PenaltyRecord[];
}

function PenaltyLog({ penalties }: PenaltyLogProps) {
  const [showAll, setShowAll] = useState(false);
  
  // Filter out invalid penalties and sort
  const sortedPenalties = useMemo(() => {
    const validPenalties = (penalties || []).filter(p => 
      p && p.issued_time && typeof p.issued_time.day === 'number' && typeof p.issued_time.hour === 'number'
    );
    
    return [...validPenalties].sort((a, b) => {
      const dayA = a.issued_time?.day ?? 0;
      const dayB = b.issued_time?.day ?? 0;
      const hourA = a.issued_time?.hour ?? 0;
      const hourB = b.issued_time?.hour ?? 0;
      
      if (dayA !== dayB) {
        return dayB - dayA;
      }
      return hourB - hourA;
    });
  }, [penalties]);

  const totalPenalty = useMemo(() => {
    return sortedPenalties.reduce((sum, p) => sum + (p.cost || 0), 0);
  }, [sortedPenalties]);

  const penaltyStats = useMemo(() => {
    const stats: Record<string, { count: number; totalCost: number; avgCost: number }> = {};
    sortedPenalties.forEach(p => {
      const code = p.code || 'UNKNOWN';
      if (!stats[code]) {
        stats[code] = { count: 0, totalCost: 0, avgCost: 0 };
      }
      stats[code].count += 1;
      stats[code].totalCost += (p.cost || 0);
    });
    
    Object.keys(stats).forEach(code => {
      stats[code].avgCost = stats[code].count > 0 ? stats[code].totalCost / stats[code].count : 0;
    });
    
    return stats;
  }, [sortedPenalties]);

  const exportToCSV = () => {
    if (sortedPenalties.length === 0) {
      alert('No penalties to export');
      return;
    }
    
    const headers = ['Day', 'Hour', 'Code', 'Cost', 'Reason'];
    const rows = sortedPenalties.map(p => [
      p.issued_time?.day ?? 0,
      p.issued_time?.hour ?? 0,
      p.code || '',
      (p.cost || 0).toFixed(2),
      `"${(p.reason || '').replace(/"/g, '""')}"`
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
        <h3>All Penalties ({sortedPenalties.length})</h3>
        <button onClick={exportToCSV} className="export-button">Export CSV</button>
      </div>

      <div className="penalty-summary">
        <div className="summary-item">
          <strong>Total Penalties:</strong> {sortedPenalties.length}
        </div>
        <div className="summary-item">
          <strong>Total Cost:</strong> ${totalPenalty.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </div>
      </div>

      {Object.keys(penaltyStats).length > 0 && (
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
                    <td>${stats.totalCost.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                    <td>${stats.avgCost.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                    <td>{totalPenalty > 0 ? ((stats.totalCost / totalPenalty) * 100).toFixed(1) : '0.0'}%</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}

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
                    <td>Day {penalty.issued_time?.day ?? '?'}, Hour {penalty.issued_time?.hour ?? '?'}</td>
                    <td><span className="penalty-code">{penalty.code || 'UNKNOWN'}</span></td>
                    <td className="cost-cell">${(penalty.cost || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                    <td className="reason-cell">{penalty.reason || '—'}</td>
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
