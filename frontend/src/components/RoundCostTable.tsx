import { useMemo } from 'react';
import type { HistoryResponse } from '../types/types';
import './RoundCostTable.css';

interface RoundCostTableProps {
  history: HistoryResponse | null;
  showAll?: boolean;
}

function RoundCostTable({ history, showAll = false }: RoundCostTableProps) {
  const costs = useMemo(() => {
    const costLog = history?.cost_log || [];
    return showAll ? costLog.reverse() : costLog.slice(-20).reverse();
  }, [history, showAll]);

  const formatCost = (cost: number) => {
    return cost.toFixed(2);
  };

  const calculateTotalCost = (costs: Record<string, number>) => {
    return Object.values(costs).reduce((sum, val) => sum + val, 0);
  };

  const exportToCSV = () => {
    if (!history || history.cost_log.length === 0) {
      alert('No data to export');
      return;
    }

    // Prepare CSV header
    const headers = [
      'Round',
      'Loading Cost',
      'Movement Cost',
      'Processing Cost',
      'Purchase Cost',
      'Penalties',
      'Calculated Total',
      'API Total'
    ];

    // Prepare CSV rows
    const rows = history.cost_log.map(costEntry => {
      const calculatedTotal = calculateTotalCost(costEntry.costs);
      const apiTotal = costEntry.api_total_cost || 0;
      return [
        costEntry.round,
        formatCost(costEntry.costs.loading_cost || 0),
        formatCost(costEntry.costs.movement_cost || 0),
        formatCost(costEntry.costs.processing_cost || 0),
        formatCost(costEntry.costs.purchase_cost || 0),
        formatCost(costEntry.costs.penalties || 0),
        formatCost(calculatedTotal),
        formatCost(apiTotal)
      ];
    });

    // Create CSV content
    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.join(','))
    ].join('\n');

    // Create and download file
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `round_costs_${new Date().toISOString().slice(0, 10)}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="round-cost-table">
      <div className="table-header">
        <h3>Round Costs</h3>
        <div className="header-actions">
          {history && (
            <>
              <span className="total-rounds-info">
                Showing {costs.length} of {history.total_rounds} rounds
              </span>
              <button onClick={exportToCSV} className="export-button">
                Export CSV
              </button>
            </>
          )}
        </div>
      </div>
      {costs.length === 0 ? (
        <p>No cost data yet. Start the simulation to see round costs.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Round</th>
              <th>Loading Cost</th>
              <th>Movement Cost</th>
              <th>Processing Cost</th>
              <th>Purchase Cost</th>
              <th>Penalties</th>
              <th>Total Round Cost</th>
              <th>API Total</th>
            </tr>
          </thead>
          <tbody>
            {costs.map((costEntry, idx) => {
              const calculatedTotal = calculateTotalCost(costEntry.costs);
              const apiTotal = costEntry.api_total_cost || 0;
              return (
                <tr key={idx}>
                  <td>{costEntry.round}</td>
                  <td>{formatCost(costEntry.costs.loading_cost || 0)}</td>
                  <td>{formatCost(costEntry.costs.movement_cost || 0)}</td>
                  <td>{formatCost(costEntry.costs.processing_cost || 0)}</td>
                  <td>{formatCost(costEntry.costs.purchase_cost || 0)}</td>
                  <td>{formatCost(costEntry.costs.penalties || 0)}</td>
                  <td className="total-cost">{formatCost(calculatedTotal)}</td>
                  <td className="api-total">{formatCost(apiTotal)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default RoundCostTable;
