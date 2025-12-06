import { useMemo } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip, LineChart, Line, XAxis, YAxis, CartesianGrid } from 'recharts';
import type { HistoryResponse } from '../types/types';
import './CostBreakdown.css';

interface CostBreakdownProps {
  history: HistoryResponse | null;
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8'];

function CostBreakdown({ history }: CostBreakdownProps) {
  const pieData = useMemo(() => {
    if (!history?.cost_log || history.cost_log.length === 0) return [];

    const totals = history.cost_log.reduce((acc, entry) => {
      const costs = entry.costs || {};
      acc.loading = (acc.loading || 0) + (costs.loading_cost || 0);
      acc.movement = (acc.movement || 0) + (costs.movement_cost || 0);
      acc.processing = (acc.processing || 0) + (costs.processing_cost || 0);
      acc.purchase = (acc.purchase || 0) + (costs.purchase_cost || 0);
      acc.penalties = (acc.penalties || 0) + (costs.penalties || 0);
      return acc;
    }, {} as Record<string, number>);

    return [
      { name: 'Loading', value: totals.loading || 0 },
      { name: 'Movement', value: totals.movement || 0 },
      { name: 'Processing', value: totals.processing || 0 },
      { name: 'Purchase', value: totals.purchase || 0 },
      { name: 'Penalties', value: totals.penalties || 0 },
    ].filter(item => item.value > 0);
  }, [history]);

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

  return (
    <div className="cost-breakdown">
      <h3>Cost Analysis</h3>
      {pieData.length === 0 ? (
        <p>No cost data available.</p>
      ) : (
        <div className="charts-container">
          <div className="pie-chart">
            <h4>Total Cost Breakdown</h4>
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
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="line-chart">
            <h4>Cost Over Time</h4>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={lineData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="round" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="total" stroke="#8884d8" name="Total Cost" />
                <Line type="monotone" dataKey="operational" stroke="#82ca9d" name="Operational" />
                <Line type="monotone" dataKey="penalties" stroke="#ff7300" name="Penalties" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}

export default CostBreakdown;

