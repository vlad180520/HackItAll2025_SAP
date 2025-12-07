import { useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import type { InventoryResponse } from '../types/types';
import './InventoryChart.css';

interface InventoryChartProps {
  inventory: InventoryResponse | null;
}

// Capacities for percentage calculation
const CAPACITIES: Record<string, Record<string, number>> = {
  HUB1: { FIRST: 18109, BUSINESS: 18109, PREMIUM_ECONOMY: 9818, ECONOMY: 95075 },
};

const CLASS_COLORS: Record<string, string> = {
  FIRST: '#fbbf24',
  BUSINESS: '#818cf8',
  PREMIUM_ECONOMY: '#34d399',
  ECONOMY: '#60a5fa',
};

const CLASS_LABELS: Record<string, string> = {
  FIRST: 'First',
  BUSINESS: 'Business',
  PREMIUM_ECONOMY: 'Premium',
  ECONOMY: 'Economy',
};

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

  const airportCards = useMemo(() => {
    if (!inventory?.inventories) return [];
    
    return Object.entries(inventory.inventories).map(([code, inv]) => {
      const isHub = code === 'HUB1';
      const classes = ['FIRST', 'BUSINESS', 'PREMIUM_ECONOMY', 'ECONOMY'];
      
      return {
        code,
        isHub,
        classes: classes.map(cls => {
          const value = inv[cls] || 0;
          const capacity = CAPACITIES[code]?.[cls] || 10000;
          const percentage = Math.min(100, (value / capacity) * 100);
          
          return {
            name: cls,
            label: CLASS_LABELS[cls],
            value,
            capacity,
            percentage,
            isLow: percentage < 20,
          };
        }),
      };
    });
  }, [inventory]);

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      return (
        <div style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-color)',
          borderRadius: '8px',
          padding: '12px 16px',
          boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
        }}>
          <p style={{ margin: '0 0 8px 0', fontWeight: 600, color: 'var(--text-primary)' }}>
            {payload[0]?.payload?.airport}
          </p>
          {payload.map((entry: any, index: number) => (
            <p key={index} style={{ margin: '4px 0', color: entry.color, fontSize: '0.85rem' }}>
              {CLASS_LABELS[entry.dataKey]}: <strong>{entry.value.toLocaleString()}</strong>
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  if (!inventory?.inventories || Object.keys(inventory.inventories).length === 0) {
    return (
      <div className="inventory-chart">
        <div className="no-inventory">
          No inventory data available.
          <br />
          <span style={{ fontSize: '0.85rem' }}>Start a simulation to see inventory levels.</span>
        </div>
      </div>
    );
  }

  return (
    <div className="inventory-chart">
      {/* Airport Cards */}
      <div className="airport-grid">
        {airportCards.map(airport => (
          <div key={airport.code} className={`airport-card ${airport.isHub ? 'hub' : ''}`}>
            <div className="airport-header">
              <div>
                <div className="airport-code">{airport.code}</div>
                <div className="airport-name">{airport.isHub ? 'Main Hub' : 'Outstation'}</div>
              </div>
            </div>
            
            <div className="inventory-items">
              {airport.classes.map(cls => (
                <div key={cls.name} className="inventory-item">
                  <div className="item-header">
                    <span className="item-label">{cls.label}</span>
                    <span className="item-value">{cls.value.toLocaleString()}</span>
                  </div>
                  <div className="item-bar">
                    <div 
                      className={`item-bar-fill ${cls.name.toLowerCase().replace('_', '-')} ${cls.isLow ? 'low' : ''}`}
                      style={{ width: `${cls.percentage}%` }}
                    />
                  </div>
                  {cls.isLow && cls.value > 0 && (
                    <span className="low-stock-warning">⚠️ Low stock</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Chart */}
      {chartData.length > 0 && (
        <div style={{ marginTop: '32px' }}>
          <h4 style={{ margin: '0 0 16px 0', color: 'var(--text-secondary)' }}>📊 Inventory Comparison</h4>
          <div style={{ 
            background: 'var(--bg-secondary)', 
            borderRadius: '12px', 
            padding: '20px',
            border: '1px solid var(--border-color)'
          }}>
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
                <XAxis 
                  dataKey="airport" 
                  tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                  axisLine={{ stroke: 'var(--border-color)' }}
                />
                <YAxis 
                  tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                  axisLine={{ stroke: 'var(--border-color)' }}
                />
                <Tooltip content={<CustomTooltip />} />
                <Legend 
                  wrapperStyle={{ paddingTop: '20px' }}
                  formatter={(value) => <span style={{ color: 'var(--text-secondary)' }}>{CLASS_LABELS[value]}</span>}
                />
                <Bar dataKey="FIRST" fill={CLASS_COLORS.FIRST} radius={[4, 4, 0, 0]} />
                <Bar dataKey="BUSINESS" fill={CLASS_COLORS.BUSINESS} radius={[4, 4, 0, 0]} />
                <Bar dataKey="PREMIUM_ECONOMY" fill={CLASS_COLORS.PREMIUM_ECONOMY} radius={[4, 4, 0, 0]} />
                <Bar dataKey="ECONOMY" fill={CLASS_COLORS.ECONOMY} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}

export default InventoryChart;
