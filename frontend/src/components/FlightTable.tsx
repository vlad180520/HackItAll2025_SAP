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

  return (
    <div className="flight-table">
      <h3>Flight Decisions</h3>
      {decisions.length === 0 ? (
        <p>No decisions yet. Start the simulation to see flight decisions.</p>
      ) : (
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
            {decisions.slice(-20).reverse().map((decision, idx) => (
              <tr key={idx}>
                <td>{decision.round}</td>
                <td>Day {decision.time.day}, Hour {decision.time.hour}</td>
                <td>{decision.decisions}</td>
                <td>{decision.purchases}</td>
                <td className="rationale-cell">{decision.rationale}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default FlightTable;

