import { useMemo } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip, LineChart, Line, XAxis, YAxis, CartesianGrid, BarChart, Bar } from 'recharts';
import type { HistoryResponse } from '../types/types';
import './CostBreakdown.css';

interface CostBreakdownProps {
  history: HistoryResponse | null;
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8', '#FF6B6B'];

function CostBreakdown({ history }: CostBreakdownProps) {
  const costTotals = useMemo(() => {
    if (!history?.cost_log || history.cost_log.length === 0) {
      return {
        loading: 0,
        movement: 0,
        processing: 0,
        purchase: 0,
        penalties: 0,
        total: 0,
      };
    }

    const totals = history.cost_log.reduce((acc, entry) => {
      const costs = entry.costs || {};
      acc.loading += costs.loading_cost || 0;
      acc.movement += costs.movement_cost || 0;
      acc.processing += costs.processing_cost || 0;
      acc.purchase += costs.purchase_cost || 0;
      acc.penalties += costs.penalties || 0;
      return acc;
    }, { loading: 0, movement: 0, processing: 0, purchase: 0, penalties: 0 });

    const total = totals.loading + totals.movement + totals.processing + totals.purchase + totals.penalties;

    return { ...totals, total };
  }, [history]);

  const pieData = useMemo(() => {
    return [
      { name: 'Loading', value: costTotals.loading },
      { name: 'Movement', value: costTotals.movement },
      { name: 'Processing', value: costTotals.processing },
      { name: 'Purchase', value: costTotals.purchase },
      { name: 'Penalties', value: costTotals.penalties },
    ].filter(item => item.value > 0);
  }, [costTotals]);

  const lineData = useMemo(() => {
    if (!history?.cost_log) return [];

    return history.cost_log.map(entry => ({
      round: entry.round,
      total: entry.costs?.total_cost || 0,
      operational: (entry.costs?.loading_cost || 0) + (entry.costs?.movement_cost || 0) +
                   (entry.costs?.processing_cost || 0) + (entry.costs?.purchase_cost || 0),
      penalties: entry.costs?.penalties || 0,
    }));
  }, [history]);

  const penaltyAnalysis = useMemo(() => {
    if (!history?.cost_log) return { totalPenalties: 0, penaltyRounds: 0, avgPenalty: 0, maxPenalty: 0 };

    let totalPenalties = 0;
    let penaltyRounds = 0;
    let maxPenalty = 0;

    history.cost_log.forEach(entry => {
      const penaltyCost = entry.costs?.penalties || 0;
      if (penaltyCost > 0) {
        totalPenalties += penaltyCost;
        penaltyRounds++;
        maxPenalty = Math.max(maxPenalty, penaltyCost);
      }
    });

    const avgPenalty = penaltyRounds > 0 ? totalPenalties / penaltyRounds : 0;

    return { totalPenalties, penaltyRounds, avgPenalty, maxPenalty };
  }, [history]);

  const operationalAnalysis = useMemo(() => {
    if (!history?.cost_log || history.cost_log.length === 0) {
      return { avgPerRound: 0, maxRound: 0, minRound: 0 };
    }

    const operationalCosts = history.cost_log.map(entry => 
      (entry.costs?.loading_cost || 0) + 
      (entry.costs?.movement_cost || 0) +
      (entry.costs?.processing_cost || 0) + 
      (entry.costs?.purchase_cost || 0)
    );

    const total = operationalCosts.reduce((sum, cost) => sum + cost, 0);
    const avgPerRound = total / operationalCosts.length;
    const maxRound = Math.max(...operationalCosts);
    const minRound = Math.min(...operationalCosts);

    return { avgPerRound, maxRound, minRound };
  }, [history]);

  const costCategoryData = useMemo(() => {
    return [
      { 
        category: 'Loading', 
        cost: costTotals.loading,
        percentage: costTotals.total > 0 ? (costTotals.loading / costTotals.total) * 100 : 0
      },
      { 
        category: 'Movement', 
        cost: costTotals.movement,
        percentage: costTotals.total > 0 ? (costTotals.movement / costTotals.total) * 100 : 0
      },
      { 
        category: 'Processing', 
        cost: costTotals.processing,
        percentage: costTotals.total > 0 ? (costTotals.processing / costTotals.total) * 100 : 0
      },
      { 
        category: 'Purchase', 
        cost: costTotals.purchase,
        percentage: costTotals.total > 0 ? (costTotals.purchase / costTotals.total) * 100 : 0
      },
      { 
        category: 'Penalties', 
        cost: costTotals.penalties,
        percentage: costTotals.total > 0 ? (costTotals.penalties / costTotals.total) * 100 : 0
      },
    ].filter(item => item.cost > 0);
  }, [costTotals]);

  const totalRounds = history?.total_rounds || 0;
  const operationalTotal = costTotals.loading + costTotals.movement + costTotals.processing + costTotals.purchase;
  const penaltyPercentage = costTotals.total > 0 ? (costTotals.penalties / costTotals.total) * 100 : 0;

  return (
    <div className="cost-breakdown">
      <h3>📊 Cost Analysis & Breakdown</h3>
      
      {pieData.length === 0 ? (
        <p className="no-data">No cost data available.</p>
      ) : (
        <>
          {/* Overall Summary */}
          <div className="analysis-summary">
            <h4>Overall Summary</h4>
            <div className="summary-grid">
              <div className="summary-card">
                <div className="card-label">Total Cost</div>
                <div className="card-value">${costTotals.total.toFixed(2)}</div>
              </div>
              <div className="summary-card">
                <div className="card-label">Operational</div>
                <div className="card-value">${operationalTotal.toFixed(2)}</div>
                <div className="card-detail">{((operationalTotal / costTotals.total) * 100).toFixed(1)}%</div>
              </div>
              <div className="summary-card">
                <div className="card-label">Penalties</div>
                <div className="card-value penalty-value">${costTotals.penalties.toFixed(2)}</div>
                <div className="card-detail">{penaltyPercentage.toFixed(1)}%</div>
              </div>
              <div className="summary-card">
                <div className="card-label">Avg per Round</div>
                <div className="card-value">${totalRounds > 0 ? (costTotals.total / totalRounds).toFixed(2) : '0.00'}</div>
              </div>
            </div>
          </div>

          {/* Detailed Analysis */}
          <div className="detailed-analysis">
            <div className="analysis-section">
              <h4>💰 Operational Costs Analysis</h4>
              <table className="analysis-table">
                <tbody>
                  <tr>
                    <td><strong>Average per Round:</strong></td>
                    <td>${operationalAnalysis.avgPerRound.toFixed(2)}</td>
                  </tr>
                  <tr>
                    <td><strong>Highest Round:</strong></td>
                    <td>${operationalAnalysis.maxRound.toFixed(2)}</td>
                  </tr>
                  <tr>
                    <td><strong>Lowest Round:</strong></td>
                    <td>${operationalAnalysis.minRound.toFixed(2)}</td>
                  </tr>
                  <tr>
                    <td><strong>Total Operational:</strong></td>
                    <td>${operationalTotal.toFixed(2)}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div className="analysis-section">
              <h4>⚠️ Penalty Analysis</h4>
              <table className="analysis-table">
                <tbody>
                  <tr>
                    <td><strong>Total Penalties:</strong></td>
                    <td className="penalty-value">${penaltyAnalysis.totalPenalties.toFixed(2)}</td>
                  </tr>
                  <tr>
                    <td><strong>Rounds with Penalties:</strong></td>
                    <td>{penaltyAnalysis.penaltyRounds} / {totalRounds}</td>
                  </tr>
                  <tr>
                    <td><strong>Avg Penalty (when occurs):</strong></td>
                    <td>${penaltyAnalysis.avgPenalty.toFixed(2)}</td>
                  </tr>
                  <tr>
                    <td><strong>Max Penalty in Round:</strong></td>
                    <td>${penaltyAnalysis.maxPenalty.toFixed(2)}</td>
                  </tr>
                </tbody>
              </table>
              {penaltyPercentage > 50 && (
                <div className="warning-message">
                  ⚠️ Penalties represent {penaltyPercentage.toFixed(1)}% of total cost - Consider optimizing strategy to reduce penalties!
                </div>
              )}
            </div>
          </div>

          {/* Cost Category Breakdown */}
          <div className="cost-category-breakdown">
            <h4>Cost Category Breakdown</h4>
            <table className="category-table">
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Total Cost</th>
                  <th>% of Total</th>
                  <th>Avg per Round</th>
                </tr>
              </thead>
              <tbody>
                {costCategoryData
                  .sort((a, b) => b.cost - a.cost)
                  .map((item, idx) => (
                    <tr key={idx}>
                      <td><strong>{item.category}</strong></td>
                      <td>${item.cost.toFixed(2)}</td>
                      <td>{item.percentage.toFixed(1)}%</td>
                      <td>${totalRounds > 0 ? (item.cost / totalRounds).toFixed(2) : '0.00'}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>

          {/* Charts */}
          <div className="charts-container">
            <div className="chart-section">
              <h4>Total Cost Distribution</h4>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {pieData.map((_entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value: number) => `$${value.toFixed(2)}`} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>

            <div className="chart-section">
              <h4>Cost by Category</h4>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={costCategoryData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="category" />
                  <YAxis />
                  <Tooltip formatter={(value: number) => `$${value.toFixed(2)}`} />
                  <Bar dataKey="cost" fill="#8884d8">
                    {costCategoryData.map((_entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="chart-section full-width">
              <h4>Cost Over Time</h4>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={lineData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="round" />
                  <YAxis />
                  <Tooltip formatter={(value: number) => `$${value.toFixed(2)}`} />
                  <Legend />
                  <Line type="monotone" dataKey="total" stroke="#8884d8" name="Total Cost" strokeWidth={2} />
                  <Line type="monotone" dataKey="operational" stroke="#82ca9d" name="Operational" />
                  <Line type="monotone" dataKey="penalties" stroke="#ff7300" name="Penalties" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default CostBreakdown;

