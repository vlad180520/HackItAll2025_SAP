import { useMemo } from 'react';
import type { PenaltyRecord } from '../types/types';
import './PenaltyLog.css';

interface PenaltyLogProps {
  penalties: PenaltyRecord[];
}

function PenaltyLog({ penalties }: PenaltyLogProps) {
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

  const penaltyCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    penalties.forEach(p => {
      counts[p.code] = (counts[p.code] || 0) + 1;
    });
    return counts;
  }, [penalties]);

  return (
    <div className="penalty-log">
      <h3>Penalty Log</h3>
      <div className="penalty-summary">
        <div className="summary-item">
          <strong>Total Penalties:</strong> {penalties.length}
        </div>
        <div className="summary-item">
          <strong>Total Cost:</strong> ${totalPenalty.toFixed(2)}
        </div>
      </div>
      <div className="penalty-breakdown">
        <h4>Penalty Breakdown by Type</h4>
        <ul>
          {Object.entries(penaltyCounts).map(([code, count]) => (
            <li key={code}>
              {code}: {count} occurrence{count !== 1 ? 's' : ''}
            </li>
          ))}
        </ul>
      </div>
      {sortedPenalties.length === 0 ? (
        <p>No penalties recorded.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Code</th>
              <th>Cost</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {sortedPenalties.slice(0, 50).map((penalty, idx) => (
              <tr key={idx}>
                <td>
                  Day {penalty.issued_time.day}, Hour {penalty.issued_time.hour}
                </td>
                <td>{penalty.code}</td>
                <td>${penalty.cost.toFixed(2)}</td>
                <td>{penalty.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default PenaltyLog;

