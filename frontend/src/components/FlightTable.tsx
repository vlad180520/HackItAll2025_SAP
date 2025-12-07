import { useMemo } from 'react';
import type { HistoryResponse } from '../types/types';
import './FlightTable.css';

interface FlightTableProps {
  history: HistoryResponse | null;
}

function FlightTable({ history }: FlightTableProps) {
  const decisions = useMemo(() => {
    return history?.decision_log || [];
  }, [history]);

  const recentDecisions = useMemo(() => {
    return decisions.slice(-20).reverse();
  }, [decisions]);

  if (decisions.length === 0) {
    return (
      <div className="flight-table">
        <h3>Flight Decisions</h3>
        <div className="no-flights">
          No decisions yet.
          <br />
          <span style={{ fontSize: '0.85rem' }}>Start the simulation to see flight decisions.</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flight-table">
      <h3>
        Flight Decisions
        <span style={{ 
          fontSize: '0.8rem', 
          fontWeight: 400, 
          color: 'var(--text-muted)',
          marginLeft: '12px' 
        }}>
          Showing {recentDecisions.length} of {decisions.length} total
        </span>
      </h3>
      
      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Round</th>
              <th>Time</th>
              <th>Decisions</th>
              <th>Purchases</th>
              <th>Rationale</th>
            </tr>
          </thead>
          <tbody>
            {recentDecisions.map((decision, idx) => (
              <tr key={idx}>
                <td className="round-cell">
                  {decision.round}
                  {idx === 0 && decisions.length > 1 && (
                    <span className="recent-badge">Latest</span>
                  )}
                </td>
                <td className="time-cell">
                  Day {decision.time.day}, Hour {decision.time.hour}
                </td>
                <td className={`decisions-cell ${decision.decisions > 0 ? 'has-decisions' : 'no-decisions'}`}>
                  {decision.decisions > 0 ? decision.decisions : '—'}
                </td>
                <td className={`purchases-cell ${decision.purchases > 0 ? 'has-purchases' : 'no-purchases'}`}>
                  {decision.purchases > 0 ? decision.purchases : '—'}
                </td>
                <td className="rationale-cell" title={decision.rationale}>
                  {decision.rationale || '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default FlightTable;
