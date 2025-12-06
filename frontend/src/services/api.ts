/** API service for backend communication */

import axios from 'axios';
import type {
  StatusResponse,
  InventoryResponse,
  HistoryResponse,
} from '../types/types';

const API_BASE_URL = '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getStatus = async (): Promise<StatusResponse> => {
  const response = await api.get<StatusResponse>('/status');
  return response.data;
};

export const getInventory = async (): Promise<InventoryResponse> => {
  const response = await api.get<InventoryResponse>('/inventory');
  return response.data;
};

export const getHistory = async (limit?: number): Promise<HistoryResponse> => {
  const params = limit !== undefined ? { limit } : {};
  const response = await api.get<HistoryResponse>('/history', { params });
  return response.data;
};

export const startSimulation = async (apiKey: string): Promise<void> => {
  await api.post('/start', { api_key: apiKey });
};

export const stopSimulation = async (): Promise<void> => {
  await api.post('/stop');
};

