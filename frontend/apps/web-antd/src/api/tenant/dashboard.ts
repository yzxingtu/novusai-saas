/**
 * 租户端仪表盘 API
 * 对接后端 /tenant/dashboard/* 接口
 */
import { requestClient } from '#/utils/request';

const API_PREFIX = '/tenant/dashboard';

export interface TenantDashboardStats {
  total_users: number;
  active_users: number;
  api_calls: number;
  resource_usage: number;
}

/**
 * 获取租户仪表盘统计数据
 */
export async function getTenantDashboardStatsApi(): Promise<TenantDashboardStats> {
  const res = await requestClient.get<TenantDashboardStats>(`${API_PREFIX}/stats`);
  return res;
}
