/**
 * Admin 数据分析 API
 * 对接后端 /admin/analytics/* 接口
 */
import { requestClient } from '#/utils/request';

const API_PREFIX = '/admin/analytics';

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

export interface ProviderPerformanceItem {
  provider_id: number;
  provider_name: string;
  calls: number;
  avg_latency: number;
  success_rate: number;
  avg_tokens: number;
  total_cost: number;
}

export interface TenantRankingItem {
  tenant_id: null | number;
  tenant_name: string;
  calls: number;
  tokens: number;
  cost: number;
}

export interface LatencyDistributionItem {
  range: string;
  count: number;
}

export interface SuccessRateTrendItem {
  date: string;
  total: number;
  success: number;
  failed: number;
  rate: number;
}

export interface DateRangeParams {
  start_date?: string;
  end_date?: string;
  tenant_id?: number;
}

// ── API Functions ──

export async function getCallTrendApi(
  params?: DateRangeParams,
): Promise<CallTrendItem[]> {
  return requestClient.get<CallTrendItem[]>(`${API_PREFIX}/call-trend`, {
    params,
  });
}

export async function getModelDistributionApi(
  params?: DateRangeParams,
): Promise<ModelDistributionItem[]> {
  return requestClient.get<ModelDistributionItem[]>(
    `${API_PREFIX}/model-distribution`,
    { params },
  );
}

export async function getProviderPerformanceApi(
  params?: Omit<DateRangeParams, 'tenant_id'>,
): Promise<ProviderPerformanceItem[]> {
  return requestClient.get<ProviderPerformanceItem[]>(
    `${API_PREFIX}/provider-performance`,
    { params },
  );
}

export async function getTenantRankingApi(
  topN = 10,
  params?: Omit<DateRangeParams, 'tenant_id'>,
): Promise<TenantRankingItem[]> {
  return requestClient.get<TenantRankingItem[]>(
    `${API_PREFIX}/tenant-ranking`,
    { params: { top_n: topN, ...params } },
  );
}

export async function getLatencyDistributionApi(
  params?: DateRangeParams,
): Promise<LatencyDistributionItem[]> {
  return requestClient.get<LatencyDistributionItem[]>(
    `${API_PREFIX}/latency-distribution`,
    { params },
  );
}

export async function getSuccessRateTrendApi(
  params?: DateRangeParams,
): Promise<SuccessRateTrendItem[]> {
  return requestClient.get<SuccessRateTrendItem[]>(
    `${API_PREFIX}/success-rate-trend`,
    { params },
  );
}
