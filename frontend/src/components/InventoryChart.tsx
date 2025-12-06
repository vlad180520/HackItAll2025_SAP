import { useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import type { InventoryResponse } from '../types/types';
import './InventoryChart.css';

interface InventoryChartProps {
  inventory: InventoryResponse | null;
}

function InventoryChart({ inventory }: InventoryChartProps) {
  const chartData = useMemo(() => {
    if (!inventory?.inventories) return [];

    const airports = Object.keys(inventory.inventories);
    const classes = ['FIRST', 'BUSINESS', 'PREMIUM_ECONOMY', 'ECONOMY'];

    return airports.map(airport => {
      const data: Record<string, string | number> = { airport };
      classes.forEach(cls => {
        data[cls] = inventory.inventories[airport]?.[cls] || 0;
      });
      return data;
    });
  }, [inventory]);

  return (
    <div className="inventory-chart">
      <h3>Inventory Levels by Airport</h3>
      {chartData.length === 0 ? (
        <p>No inventory data available.</p>
      ) : (
        <ResponsiveContainer width="100%" height={400}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="airport" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="FIRST" fill="#8884d8" />
            <Bar dataKey="BUSINESS" fill="#82ca9d" />
            <Bar dataKey="PREMIUM_ECONOMY" fill="#ffc658" />
            <Bar dataKey="ECONOMY" fill="#ff7300" />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

export default InventoryChart;

