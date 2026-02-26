/**
 * 平台管理端仪表盘 API
 * 对接后端 /admin/dashboard/* 接口
 */
import { requestClient } from '#/utils/request';

const API_PREFIX = '/admin/dashboard';

// ── Types ──

export interface DashboardStats {
  total_tenants: number;
  active_tenants: number;
  total_users: number;
  today_login: number;
}

export interface SystemHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  redis: { connected: boolean };
  database: { connected: boolean };
  celery: { connected: boolean };
  memory_mb: number;
  uptime_seconds: number;
}

export interface AIOverview {
  total_calls: number;
  total_tokens: number;
  total_cost: number;
  active_providers: number;
  today_calls: number;
  today_tokens: number;
  success_rate: number;
}

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

export interface PluginOverview {
  total: number;
  enabled: number;
  disabled: number;
  error_count: number;
}

export interface TenantGrowthItem {
  date: string;
  count: number;
}

export interface ActivityItem {
  id: number;
  username: string | null;
  nickname: string | null;
  user_type: string;
  action: string | null;
  module: string | null;
  resource: string | null;
  path: string;
  method: string;
  status_code: number | null;
  ip: string | null;
  duration_ms: number | null;
  created_at: string | null;
}

export interface SystemInfo {
  python_version: string;
  platform: string;
  app_env: string;
  debug: boolean;
  health: SystemHealth;
  plugins: PluginOverview;
}

// ── API Functions ──

export async function getDashboardStatsApi(): Promise<DashboardStats> {
  return requestClient.get<DashboardStats>(`${API_PREFIX}/stats`);
}

export async function getSystemHealthApi(): Promise<SystemHealth> {
  return requestClient.get<SystemHealth>(`${API_PREFIX}/health`);
}

export async function getAIOverviewApi(): Promise<AIOverview> {
  return requestClient.get<AIOverview>(`${API_PREFIX}/ai-overview`);
}

export async function getStorageOverviewApi(): Promise<StorageOverview> {
  return requestClient.get<StorageOverview>(`${API_PREFIX}/storage-overview`);
}

export async function getPluginOverviewApi(): Promise<PluginOverview> {
  return requestClient.get<PluginOverview>(`${API_PREFIX}/plugin-overview`);
}

export async function getTenantGrowthApi(days = 30): Promise<TenantGrowthItem[]> {
  return requestClient.get<TenantGrowthItem[]>(`${API_PREFIX}/tenant-growth`, { params: { days } });
}

export async function getRecentActivitiesApi(limit = 20): Promise<ActivityItem[]> {
  return requestClient.get<ActivityItem[]>(`${API_PREFIX}/recent-activities`, { params: { limit } });
}

export async function getSystemInfoApi(): Promise<SystemInfo> {
  return requestClient.get<SystemInfo>(`${API_PREFIX}/system-info`);
}
