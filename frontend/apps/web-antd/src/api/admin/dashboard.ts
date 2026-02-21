/**
 * 平台管理端仪表盘 API
 * 对接后端 /admin/dashboard/* 接口
 */
import { requestClient } from '#/utils/request';

const API_PREFIX = '/admin/dashboard';

export interface DashboardStats {
  total_tenants: number;
  active_tenants: number;
  total_users: number;
  today_login: number;
}

/**
 * 获取仪表盘统计数据
 */
export async function getDashboardStatsApi(): Promise<DashboardStats> {
  const res = await requestClient.get<DashboardStats>(`${API_PREFIX}/stats`);
  return res;
}
