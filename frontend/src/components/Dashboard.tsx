import { useState, useEffect } from 'react';
import { getStatus, getInventory, getHistory, startSimulation, stopSimulation } from '../services/api';
import type { StatusResponse, InventoryResponse, HistoryResponse } from '../types/types';
import FlightTable from './FlightTable';
import InventoryChart from './InventoryChart';
import CostBreakdown from './CostBreakdown';
import PenaltyLog from './PenaltyLog';
import RoundCostTable from './RoundCostTable';
import './Dashboard.css';

interface DashboardProps {
  apiKey: string;
}

function Dashboard({ apiKey }: DashboardProps) {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [inventory, setInventory] = useState<InventoryResponse | null>(null);
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'monitoring' | 'costs' | 'inventory' | 'penalties' | 'roundCosts'>('monitoring');
  const [showAllRounds, setShowAllRounds] = useState(false);

  // Poll for updates every 2 seconds
  useEffect(() => {
    const fetchData = async () => {
      try {
        const limit = showAllRounds ? 0 : 20; // 0 means fetch all
        const [statusData, inventoryData, historyData] = await Promise.all([
          getStatus(),
          getInventory(),
          getHistory(limit),
        ]);
        setStatus(statusData);
        setInventory(inventoryData);
        setHistory(historyData);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch data');
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 2000);

    return () => clearInterval(interval);
  }, [showAllRounds]);

  const handleStartSimulation = async () => {
    if (!apiKey) {
      setError('Please enter an API key');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await startSimulation(apiKey);
      setStatus({ status: 'running', round: 0, costs: 0, penalties: [] });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start simulation');
    } finally {
      setLoading(false);
    }
  };

  const handleStopSimulation = async () => {
    setLoading(true);
    setError(null);
    try {
      await stopSimulation();
      setStatus(prev => prev ? { ...prev, status: 'stopped' } : null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to stop simulation');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <div className="status-info">
          <h2>Status: {status?.status || 'not_started'}</h2>
          <p>Round: {status?.round || 0} / 720</p>
          <p>Total Cost: ${typeof status?.costs === 'number' ? status.costs.toFixed(2) : '0.00'}</p>
          {status?.status === 'running' && (
            <p style={{ color: '#4CAF50', fontWeight: 'bold' }}>● Simulation Running...</p>
          )}
        </div>
        {status?.status === 'running' ? (
          <button
            onClick={handleStopSimulation}
            disabled={loading}
            className="start-button stop-button"
          >
            {loading ? 'Stopping...' : 'Stop Simulation'}
          </button>
        ) : (
          <button
            onClick={handleStartSimulation}
            disabled={loading}
            className="start-button"
          >
            {loading ? 'Starting...' : 'Start Simulation'}
          </button>
        )}
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="tabs">
        <button
          className={activeTab === 'monitoring' ? 'active' : ''}
          onClick={() => setActiveTab('monitoring')}
        >
          Monitoring
        </button>
        <button
          className={activeTab === 'roundCosts' ? 'active' : ''}
          onClick={() => setActiveTab('roundCosts')}
        >
          Round Costs
        </button>
        <button
          className={activeTab === 'costs' ? 'active' : ''}
          onClick={() => setActiveTab('costs')}
        >
          Cost Breakdown
        </button>
        <button
          className={activeTab === 'inventory' ? 'active' : ''}
          onClick={() => setActiveTab('inventory')}
        >
          Inventory
        </button>
        <button
          className={activeTab === 'penalties' ? 'active' : ''}
          onClick={() => setActiveTab('penalties')}
        >
          Penalties
        </button>
      </div>

      <div className="tab-content">
        {activeTab === 'monitoring' && (
          <div>
            <FlightTable history={history} />
          </div>
        )}
        {activeTab === 'roundCosts' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ margin: 0 }}>Round Costs</h3>
              <button
                onClick={() => setShowAllRounds(!showAllRounds)}
                className="view-all-button"
              >
                {showAllRounds ? 'Show Last 20' : 'View All Rounds'}
              </button>
            </div>
            <RoundCostTable history={history} showAll={showAllRounds} />
          </div>
        )}
        {activeTab === 'costs' && (
          <div>
            <CostBreakdown history={history} />
          </div>
        )}
        {activeTab === 'inventory' && (
          <div>
            <InventoryChart inventory={inventory} />
          </div>
        )}
        {activeTab === 'penalties' && (
          <div>
            <PenaltyLog penalties={status?.penalties || []} />
          </div>
        )}
      </div>
    </div>
  );
}

export default Dashboard;

