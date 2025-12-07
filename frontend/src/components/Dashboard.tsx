import { useState, useEffect, useCallback, useMemo } from 'react';
import { getStatus, getInventory, getHistory, startSimulation, stopSimulation } from '../services/api';
import type { StatusResponse, InventoryResponse, HistoryResponse } from '../types/types';
import FlightTable from './FlightTable';
import InventoryChart from './InventoryChart';
import CostBreakdown from './CostBreakdown';
import PenaltyLog from './PenaltyLog';
import RoundCostTable from './RoundCostTable';
import StatsCounter from './StatsCounter';
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

  const fetchData = useCallback(async () => {
    try {
      const limit = showAllRounds ? 0 : 20;
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
  }, [showAllRounds]);

  // Poll for updates
  useEffect(() => {
    fetchData();
    const pollInterval = status?.status === 'running' ? 2000 : 10000;
    const interval = setInterval(fetchData, pollInterval);
    return () => clearInterval(interval);
  }, [fetchData, status?.status]);

  const handleStartSimulation = async () => {
    if (!apiKey) {
      setError('Please enter an API key in the header');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await startSimulation(apiKey);
      setStatus({ status: 'running', round: 0, costs: 0, penalties: [] });
      // Immediate refresh
      setTimeout(fetchData, 500);
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
      setTimeout(fetchData, 500);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to stop simulation');
    } finally {
      setLoading(false);
    }
  };

  // Calculate costs breakdown

  const formatNumber = (num: number) => {
    return new Intl.NumberFormat('de-DE', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(num);
  };

  // Get final cost - prefer from history if status shows 0
  const finalCost = useMemo(() => {
    // First try status cost
    const statusCost = typeof status?.costs === 'number' ? status.costs : 0;
    if (statusCost > 0) return statusCost;

    // Fallback: get from last cost_log entry
    if (history?.cost_log && history.cost_log.length > 0) {
      const lastEntry = history.cost_log[history.cost_log.length - 1];
      if (lastEntry?.api_total_cost) return lastEntry.api_total_cost;
    }

    return statusCost;
  }, [status, history]);

  const costBreakdown = useMemo(() => {
    if (!history?.cost_log || history.cost_log.length === 0) return null;

    const totalPenalties = history.cost_log.reduce((sum, entry) => {
      if (!entry || !entry.penalties) return sum;
      const penalties = entry.penalties || [];
      return sum + penalties.reduce((pSum: number, p: any) => pSum + (p?.cost || 0), 0);
    }, 0);

    return {
      total: finalCost,
      penalties: totalPenalties,
      operations: finalCost - totalPenalties
    };
  }, [history, finalCost]);

  const getStatusColor = () => {
    switch (status?.status) {
      case 'running': return 'var(--accent-green)';
      case 'completed': return 'var(--accent-blue)';
      case 'error': return 'var(--accent-red)';
      default: return 'var(--text-muted)';
    }
  };

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <div className="status-info">
          <h2 style={{ color: getStatusColor() }}>
            {status?.status === 'running' ? '● Running' :
              status?.status === 'completed' ? '✓ Completed' :
                status?.status === 'error' ? '✕ Error' : '○ Ready'}
          </h2>

          <div className="round-display">
            {status?.round || 0} <span>/ 720 rounds</span>
          </div>

          <div className="cost-display">
            ${formatNumber(finalCost)}
          </div>

          {status?.status === 'running' && (
            <p className="running-indicator">Simulation in progress...</p>
          )}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', alignItems: 'flex-end' }}>
          {status?.status === 'running' ? (
            <button
              onClick={handleStopSimulation}
              disabled={loading}
              className="start-button stop-button"
            >
              {loading ? '⏳ Stopping...' : '⏹ Stop Simulation'}
            </button>
          ) : (
            <button
              onClick={handleStartSimulation}
              disabled={loading}
              className="start-button"
            >
              {loading ? '⏳ Starting...' : status?.status === 'completed' ? '🔄 Restart' : '▶ Start Simulation'}
            </button>
          )}

          {!apiKey && (
            <span style={{ fontSize: '0.8rem', color: 'var(--accent-orange)' }}>
              ⚠️ Enter API key above
            </span>
          )}
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      <StatsCounter status={status} />

      <div className="tabs">
        <button
          className={activeTab === 'monitoring' ? 'active' : ''}
          onClick={() => setActiveTab('monitoring')}
        >
          📊 Monitoring
        </button>
        <button
          className={activeTab === 'roundCosts' ? 'active' : ''}
          onClick={() => setActiveTab('roundCosts')}
        >
          💰 Round Costs
        </button>
        <button
          className={activeTab === 'costs' ? 'active' : ''}
          onClick={() => setActiveTab('costs')}
        >
          📈 Cost Breakdown
        </button>
        <button
          className={activeTab === 'inventory' ? 'active' : ''}
          onClick={() => setActiveTab('inventory')}
        >
          📦 Inventory
        </button>
        <button
          className={activeTab === 'penalties' ? 'active' : ''}
          onClick={() => setActiveTab('penalties')}
        >
          ⚠️ Penalties
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
              <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                💰 Round Costs
              </h3>
              <button
                onClick={() => setShowAllRounds(!showAllRounds)}
                className="view-all-button"
              >
                {showAllRounds ? '📋 Show Last 20' : '📊 View All Rounds'}
              </button>
            </div>
            <RoundCostTable history={history} showAll={showAllRounds} />
          </div>
        )}
        {activeTab === 'costs' && (
          <div>
            <h3 style={{ margin: '0 0 16px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
              📈 Cost Analysis
            </h3>
            <CostBreakdown history={history} />
          </div>
        )}
        {activeTab === 'inventory' && (
          <div>
            <h3 style={{ margin: '0 0 16px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
              📦 Airport Inventory
            </h3>
            <InventoryChart inventory={inventory} />
          </div>
        )}
        {activeTab === 'penalties' && (
          <div>
            <PenaltyLog penalties={
              (history?.cost_log || [])
                .filter(entry => entry && entry.penalties)
                .flatMap(entry => entry.penalties || [])
                .filter(p => p && p.issued_time)
            } />
          </div>
        )}
      </div>
    </div>
  );
}

export default Dashboard;
