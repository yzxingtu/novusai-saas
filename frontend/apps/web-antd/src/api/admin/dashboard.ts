/**
 * Platform admin dashboard API / 平台管理端仪表盘 API
 * Backend: /admin/dashboard/*
 */
import { requestClient } from '#/utils/request';

const API_PREFIX = '/admin/dashboard';

// ── Types / 类型定义 ──

/** Dashboard stats / 仪表盘统计 */
export interface DashboardStats {
  total_tenants: number;
  active_tenants: number;
  total_users: number;
  today_login: number;
}

/** System health status / 系统健康状态 */
export interface SystemHealth {
  status: 'degraded' | 'healthy' | 'unhealthy';
  redis: { connected: boolean };
  database: { connected: boolean };
  celery: { connected: boolean };
  memory_mb: number;
  uptime_seconds: number;
}

/** AI overview / AI 概览 */
export interface AIOverview {
  total_calls: number;
  total_tokens: number;
  total_cost: number;
  active_providers: number;
  today_calls: number;
  today_tokens: number;
  success_rate: number;
}

/** Storage overview / 存储概览 */
export interface StorageOverview {
  total_files: number;
  total_size_bytes: number;
  total_size_mb: number;
  driver_distribution: Array<{
    driver: string;
    file_count: number;
    size_bytes: number;
  }>;
}

/** Plugin overview / 插件概览 */
export interface PluginOverview {
  total: number;
  enabled: number;
  disabled: number;
  error_count: number;
}

/** Tenant growth item / 租户增长项 */
export interface TenantGrowthItem {
  date: string;
  count: number;
}

/** Activity item / 活动记录项 */
export interface ActivityItem {
  id: number;
  username: null | string;
  nickname: null | string;
  user_type: string;
  action: null | string;
  module: null | string;
  resource: null | string;
  path: string;
  method: string;
  status_code: null | number;
  ip: null | string;
  duration_ms: null | number;
  created_at: null | string;
}

/** System info / 系统信息 */
export interface SystemInfo {
  python_version: string;
  platform: string;
  app_env: string;
  debug: boolean;
  health: SystemHealth;
  plugins: PluginOverview;
}

// ── API Functions / API 接口 ──

/** Get dashboard stats / 获取仪表盘统计 */
export async function getDashboardStatsApi(): Promise<DashboardStats> {
  return requestClient.get<DashboardStats>(`${API_PREFIX}/stats`);
}

/** Get system health / 获取系统健康状态 */
export async function getSystemHealthApi(): Promise<SystemHealth> {
  return requestClient.get<SystemHealth>(`${API_PREFIX}/health`);
}

/** Get AI overview / 获取 AI 概览 */
export async function getAIOverviewApi(): Promise<AIOverview> {
  return requestClient.get<AIOverview>(`${API_PREFIX}/ai-overview`);
}

/** Get storage overview / 获取存储概览 */
export async function getStorageOverviewApi(): Promise<StorageOverview> {
  return requestClient.get<StorageOverview>(`${API_PREFIX}/storage-overview`);
}

/** Get plugin overview / 获取插件概览 */
export async function getPluginOverviewApi(): Promise<PluginOverview> {
  return requestClient.get<PluginOverview>(`${API_PREFIX}/plugin-overview`);
}

/** Get tenant growth trend / 获取租户增长趋势 */
export async function getTenantGrowthApi(
  days = 30,
): Promise<TenantGrowthItem[]> {
  return requestClient.get<TenantGrowthItem[]>(`${API_PREFIX}/tenant-growth`, {
    params: { days },
  });
}

/** Get recent activities / 获取最近活动 */
export async function getRecentActivitiesApi(
  limit = 20,
): Promise<ActivityItem[]> {
  return requestClient.get<ActivityItem[]>(`${API_PREFIX}/recent-activities`, {
    params: { limit },
  });
}

/** Get system info / 获取系统信息 */
export async function getSystemInfoApi(): Promise<SystemInfo> {
  return requestClient.get<SystemInfo>(`${API_PREFIX}/system-info`);
}
