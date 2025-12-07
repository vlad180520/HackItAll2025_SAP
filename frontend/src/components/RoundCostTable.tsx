import { useMemo } from 'react';
import type { HistoryResponse } from '../types/types';
import './RoundCostTable.css';

interface RoundCostTableProps {
  history: HistoryResponse | null;
  showAll?: boolean;
}

function RoundCostTable({ history, showAll = false }: RoundCostTableProps) {
  const data = useMemo(() => {
    if (!history?.decision_log || !history?.cost_log) return [];
    
    // Merge decision_log and cost_log by round
    const merged = history.decision_log.map((decision, idx) => {
      const costEntry = history.cost_log[idx] || {};
      return {
        round: decision.round,
        time: decision.time,
        decisions: decision.decisions,
        purchases: decision.purchases,
        rationale: decision.rationale,
        api_total_cost: costEntry.api_total_cost || 0,
        incremental_cost: costEntry.incremental_cost || 0,
      };
    });
    
    // Sort by round descending, then limit
    const sorted = [...merged].sort((a, b) => b.round - a.round);
    return showAll ? sorted : sorted.slice(0, 20);
  }, [history, showAll]);

  const formatCost = (cost: number | undefined | null) => {
    if (cost === undefined || cost === null || isNaN(cost)) return '0.00';
    return cost.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  const exportToCSV = () => {
    if (!history || !history.decision_log || history.decision_log.length === 0) {
      alert('No data to export');
      return;
    }

    const headers = ['Round', 'Day', 'Hour', 'Decisions', 'Purchases', 'API Total Cost', 'Rationale'];
    const rows = data.map(entry => [
      entry.round,
      entry.time?.day || 0,
      entry.time?.hour || 0,
      entry.decisions,
      entry.purchases,
      formatCost(entry.api_total_cost),
      `"${(entry.rationale || '').replace(/"/g, '""')}"`
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `round_data_${new Date().toISOString().slice(0, 10)}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const totalRounds = history?.total_rounds || 0;

  return (
    <div className="round-cost-table">
      <div className="table-header">
        <div className="header-actions">
          {history && history.decision_log && (
            <>
              <span className="total-rounds-info">
                Showing {data.length} of {totalRounds} rounds
              </span>
              <button onClick={exportToCSV} className="export-button">
                Export CSV
              </button>
            </>
          )}
        </div>
      </div>
      
      {data.length === 0 ? (
        <p>No data yet. Start the simulation to see round data.</p>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Round</th>
                <th>Time</th>
                <th>Decisions</th>
                <th>Purchases</th>
                <th>API Total Cost</th>
                <th>Rationale</th>
              </tr>
            </thead>
            <tbody>
              {data.map((entry, idx) => (
                <tr key={idx}>
                  <td className="round-cell">
                    {entry.round}
                    {idx === 0 && data.length > 1 && (
                      <span className="recent-badge">Latest</span>
                    )}
                  </td>
                  <td className="time-cell">
                    Day {entry.time?.day ?? '?'}, Hour {entry.time?.hour ?? '?'}
                  </td>
                  <td className={`decisions-cell ${entry.decisions > 0 ? 'has-decisions' : 'no-decisions'}`}>
                    {entry.decisions > 0 ? entry.decisions : '—'}
                  </td>
                  <td className={`purchases-cell ${entry.purchases > 0 ? 'has-purchases' : 'no-purchases'}`}>
                    {entry.purchases > 0 ? entry.purchases : '—'}
                  </td>
                  <td className="api-total">
                    ${formatCost(entry.api_total_cost)}
                  </td>
                  <td className="rationale-cell" title={entry.rationale || ''}>
                    {entry.rationale || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default RoundCostTable;
