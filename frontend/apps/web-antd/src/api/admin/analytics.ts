/**
 * Admin analytics API / Admin 数据分析 API
 * Backend: /admin/analytics/*
 */
import { requestClient } from '#/utils/request';

const API_PREFIX = '/admin/analytics';

// ── Types / 类型定义 ──

/** Call trend item / 调用趋势项 */
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

/** Model distribution item / 模型分布项 */
export interface ModelDistributionItem {
  model_id: number;
  model_name: string;
  calls: number;
  tokens: number;
  cost: number;
}

/** Provider performance item / 供应商性能项 */
export interface ProviderPerformanceItem {
  provider_id: number;
  provider_name: string;
  calls: number;
  avg_latency: number;
  success_rate: number;
  avg_tokens: number;
  total_cost: number;
}

/** Tenant ranking item / 租户排名项 */
export interface TenantRankingItem {
  tenant_id: null | number;
  tenant_name: string;
  calls: number;
  tokens: number;
  cost: number;
}

/** Latency distribution item / 延迟分布项 */
export interface LatencyDistributionItem {
  range: string;
  count: number;
}

/** Success rate trend item / 成功率趋势项 */
export interface SuccessRateTrendItem {
  date: string;
  total: number;
  success: number;
  failed: number;
  rate: number;
}

/** Date range query params / 日期范围查询参数 */
export interface DateRangeParams {
  start_date?: string;
  end_date?: string;
  tenant_id?: number;
}

// ── API Functions / API 接口 ──

/** Get call trend / 获取调用趋势 */
export async function getCallTrendApi(
  params?: DateRangeParams,
): Promise<CallTrendItem[]> {
  return requestClient.get<CallTrendItem[]>(`${API_PREFIX}/call-trend`, {
    params,
  });
}

/** Get model distribution / 获取模型分布 */
export async function getModelDistributionApi(
  params?: DateRangeParams,
): Promise<ModelDistributionItem[]> {
  return requestClient.get<ModelDistributionItem[]>(
    `${API_PREFIX}/model-distribution`,
    { params },
  );
}

/** Get provider performance / 获取供应商性能 */
export async function getProviderPerformanceApi(
  params?: Omit<DateRangeParams, 'tenant_id'>,
): Promise<ProviderPerformanceItem[]> {
  return requestClient.get<ProviderPerformanceItem[]>(
    `${API_PREFIX}/provider-performance`,
    { params },
  );
}

/** Get tenant ranking / 获取租户排名 */
export async function getTenantRankingApi(
  topN = 10,
  params?: Omit<DateRangeParams, 'tenant_id'>,
): Promise<TenantRankingItem[]> {
  return requestClient.get<TenantRankingItem[]>(
    `${API_PREFIX}/tenant-ranking`,
    { params: { top_n: topN, ...params } },
  );
}

/** Get latency distribution / 获取延迟分布 */
export async function getLatencyDistributionApi(
  params?: DateRangeParams,
): Promise<LatencyDistributionItem[]> {
  return requestClient.get<LatencyDistributionItem[]>(
    `${API_PREFIX}/latency-distribution`,
    { params },
  );
}

/** Get success rate trend / 获取成功率趋势 */
export async function getSuccessRateTrendApi(
  params?: DateRangeParams,
): Promise<SuccessRateTrendItem[]> {
  return requestClient.get<SuccessRateTrendItem[]>(
    `${API_PREFIX}/success-rate-trend`,
    { params },
  );
}
