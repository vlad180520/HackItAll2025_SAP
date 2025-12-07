import { useMemo } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip, LineChart, Line, XAxis, YAxis, CartesianGrid } from 'recharts';
import type { HistoryResponse } from '../types/types';
import './CostBreakdown.css';

interface CostBreakdownProps {
  history: HistoryResponse | null;
}

const COLORS = ['#00d4ff', '#a855f7', '#10b981', '#f59e0b', '#ef4444'];

function CostBreakdown({ history }: CostBreakdownProps) {
  // Get final total cost from the last entry
  const finalCost = useMemo(() => {
    if (!history?.cost_log || history.cost_log.length === 0) return 0;
    const lastEntry = history.cost_log[history.cost_log.length - 1];
    return lastEntry?.api_total_cost || 0;
  }, [history]);

  // Calculate penalty totals from penalty entries
  const penaltyStats = useMemo(() => {
    if (!history?.cost_log) return { count: 0, totalCost: 0 };
    
    let count = 0;
    let totalCost = 0;
    
    history.cost_log.forEach(entry => {
      if (entry.penalties && Array.isArray(entry.penalties)) {
        entry.penalties.forEach(p => {
          if (p && typeof p.cost === 'number') {
            count++;
            totalCost += p.cost;
          }
        });
      }
    });
    
    return { count, totalCost };
  }, [history]);

  // Line chart data - cumulative cost over rounds
  const lineData = useMemo(() => {
    if (!history?.cost_log) return [];
    
    return history.cost_log
      .filter(entry => entry && typeof entry.round === 'number')
      .map(entry => ({
        round: entry.round,
        totalCost: entry.api_total_cost || 0,
      }))
      .sort((a, b) => a.round - b.round);
  }, [history]);

  // Pie data - operations vs penalties
  const pieData = useMemo(() => {
    const operations = finalCost - penaltyStats.totalCost;
    return [
      { name: 'Operations', value: Math.max(0, operations) },
      { name: 'Penalties', value: penaltyStats.totalCost },
    ].filter(item => item.value > 0);
  }, [finalCost, penaltyStats]);

  const totalRounds = history?.total_rounds || 0;
  const operationsCost = finalCost - penaltyStats.totalCost;
  const penaltyPercentage = finalCost > 0 ? (penaltyStats.totalCost / finalCost) * 100 : 0;

  const formatCurrency = (value: number) => {
    return '$' + value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-color)',
          borderRadius: '8px',
          padding: '12px 16px',
          boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
        }}>
          <p style={{ margin: '0 0 4px 0', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            Round {label}
          </p>
          <p style={{ margin: 0, color: 'var(--accent-cyan)', fontWeight: 600 }}>
            {formatCurrency(payload[0]?.value || 0)}
          </p>
        </div>
      );
    }
    return null;
  };

  if (!history?.cost_log || history.cost_log.length === 0) {
    return (
      <div className="cost-breakdown">
        <p className="no-data">No cost data available. Run a simulation to see cost analysis.</p>
      </div>
    );
  }

  return (
    <div className="cost-breakdown">
      {/* Summary Cards */}
      <div className="analysis-summary">
        <h4>Cost Summary</h4>
        <div className="summary-grid">
          <div className="summary-card">
            <div className="card-label">Final Total Cost</div>
            <div className="card-value">{formatCurrency(finalCost)}</div>
          </div>
          <div className="summary-card">
            <div className="card-label">Operations Cost</div>
            <div className="card-value">{formatCurrency(operationsCost)}</div>
            <div className="card-detail">{(100 - penaltyPercentage).toFixed(1)}% of total</div>
          </div>
          <div className="summary-card">
            <div className="card-label">Penalty Cost</div>
            <div className="card-value">{formatCurrency(penaltyStats.totalCost)}</div>
            <div className="card-detail">{penaltyPercentage.toFixed(1)}% of total</div>
          </div>
          <div className="summary-card">
            <div className="card-label">Avg Cost / Round</div>
            <div className="card-value">{formatCurrency(totalRounds > 0 ? finalCost / totalRounds : 0)}</div>
          </div>
        </div>
      </div>

      {/* Statistics */}
      <div className="detailed-analysis">
        <div className="analysis-section">
          <h4>📊 Simulation Statistics</h4>
          <table className="analysis-table">
            <tbody>
              <tr>
                <td><strong>Total Rounds:</strong></td>
                <td>{totalRounds}</td>
              </tr>
              <tr>
                <td><strong>Total Penalties:</strong></td>
                <td>{penaltyStats.count}</td>
              </tr>
              <tr>
                <td><strong>Final Cost:</strong></td>
                <td>{formatCurrency(finalCost)}</td>
              </tr>
              <tr>
                <td><strong>Penalty %:</strong></td>
                <td>{penaltyPercentage.toFixed(2)}%</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="analysis-section">
          <h4>⚠️ Penalty Summary</h4>
          <table className="analysis-table">
            <tbody>
              <tr>
                <td><strong>Penalty Count:</strong></td>
                <td>{penaltyStats.count}</td>
              </tr>
              <tr>
                <td><strong>Total Penalty Cost:</strong></td>
                <td className="penalty-value">{formatCurrency(penaltyStats.totalCost)}</td>
              </tr>
              <tr>
                <td><strong>Avg per Penalty:</strong></td>
                <td>{formatCurrency(penaltyStats.count > 0 ? penaltyStats.totalCost / penaltyStats.count : 0)}</td>
              </tr>
            </tbody>
          </table>
          {penaltyPercentage > 50 && (
            <div className="warning-message">
              ⚠️ Penalties represent {penaltyPercentage.toFixed(1)}% of total cost!
            </div>
          )}
        </div>
      </div>

      {/* Charts */}
      <div className="charts-container">
        {pieData.length > 0 && (
          <div className="chart-section">
            <h4>Cost Distribution</h4>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  outerRadius={100}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {pieData.map((_entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value: number) => formatCurrency(value)} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}

        {lineData.length > 0 && (
          <div className="chart-section">
            <h4>Cumulative Cost Over Time</h4>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={lineData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
                <XAxis 
                  dataKey="round" 
                  tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
                  axisLine={{ stroke: 'var(--border-color)' }}
                  label={{ value: 'Round', position: 'bottom', fill: 'var(--text-muted)' }}
                />
                <YAxis 
                  tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
                  axisLine={{ stroke: 'var(--border-color)' }}
                  tickFormatter={(value) => `$${(value / 1000000).toFixed(0)}M`}
                />
                <Tooltip content={<CustomTooltip />} />
                <Line 
                  type="monotone" 
                  dataKey="totalCost" 
                  stroke="var(--accent-cyan)" 
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}

export default CostBreakdown;
