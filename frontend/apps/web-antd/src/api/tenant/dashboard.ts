/**
 * 租户端仪表盘 API
 * 对接后端 /tenant/dashboard/* 接口
 */
import { requestClient } from '#/utils/request';

const API_PREFIX = '/tenant/dashboard';

// ── Types ──

export interface TenantDashboardStats {
  total_users: number;
  active_users: number;
  api_calls: number;
  total_tokens: number;
  total_cost: number;
  storage_used_bytes: number;
  storage_used_mb: number;
  total_agents: number;
  total_knowledge_bases: number;
  total_kb_documents: number;
  monthly_conversations: number;
}

export interface AITrendItem {
  date: string;
  calls: number;
  tokens: number;
}

export interface StorageDetail {
  total_files: number;
  total_size_bytes: number;
  total_size_mb: number;
  type_distribution: Array<{
    count: number;
    mime_type: string;
    size_bytes: number;
  }>;
}

export interface TenantActivityItem {
  id: number;
  username: null | string;
  action: null | string;
  module: null | string;
  path: string;
  method: string;
  status_code: null | number;
  duration_ms: null | number;
  created_at: null | string;
}

// ── API Functions ──

export async function getTenantDashboardStatsApi(): Promise<TenantDashboardStats> {
  return requestClient.get<TenantDashboardStats>(`${API_PREFIX}/stats`);
}

export async function getAITrendApi(days = 7): Promise<AITrendItem[]> {
  return requestClient.get<AITrendItem[]>(`${API_PREFIX}/ai-trend`, {
    params: { days },
  });
}

export async function getStorageDetailApi(): Promise<StorageDetail> {
  return requestClient.get<StorageDetail>(`${API_PREFIX}/storage-detail`);
}

export async function getTenantRecentActivitiesApi(
  limit = 20,
): Promise<TenantActivityItem[]> {
  return requestClient.get<TenantActivityItem[]>(
    `${API_PREFIX}/recent-activities`,
    { params: { limit } },
  );
}
