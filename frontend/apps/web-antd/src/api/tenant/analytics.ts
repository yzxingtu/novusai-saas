/**
 * Tenant 数据分析 API
 * 对接后端 /tenant/analytics/* 接口
 */
import { requestClient } from '#/utils/request';

const API_PREFIX = '/tenant/analytics';

// ── Types ──

export interface CallTrendItem {
  date: string;
  calls: number;
  tokens: number;
  input_tokens: number;
  output_tokens: number;
  cost: number;
  success: number;
  failed: number;
}

export interface ModelDistributionItem {
  model_id: number;
  model_name: string;
  calls: number;
  tokens: number;
  cost: number;
}

export interface AgentRankingItem {
  agent_id: number | null;
  agent_name: string;
  calls: number;
  tokens: number;
  cost: number;
}

export interface CostTrendItem {
  date: string;
  cost: number;
  calls: number;
}

export interface DateRangeParams {
  start_date?: string;
  end_date?: string;
}

// ── API Functions ──

export async function getTenantCallTrendApi(params?: DateRangeParams): Promise<CallTrendItem[]> {
  return requestClient.get<CallTrendItem[]>(`${API_PREFIX}/call-trend`, { params });
}

export async function getTenantModelDistributionApi(params?: DateRangeParams): Promise<ModelDistributionItem[]> {
  return requestClient.get<ModelDistributionItem[]>(`${API_PREFIX}/model-distribution`, { params });
}

export async function getTenantAgentRankingApi(topN = 10, params?: DateRangeParams): Promise<AgentRankingItem[]> {
  return requestClient.get<AgentRankingItem[]>(`${API_PREFIX}/agent-ranking`, { params: { top_n: topN, ...params } });
}

export async function getTenantCostTrendApi(params?: DateRangeParams): Promise<CostTrendItem[]> {
  return requestClient.get<CostTrendItem[]>(`${API_PREFIX}/cost-trend`, { params });
}
