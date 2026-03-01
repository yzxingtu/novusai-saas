/**
 * 缓存管理 API
 * 对接后端 /admin/cache/* 接口
 */
import { requestClient } from '#/utils/request';

const API_PREFIX = '/admin/cache';

// ── Types ──

export interface CacheCategorySummary {
  category: string;
  label: string;
  key_count: number;
  size_bytes: number;
  size_human: string;
}

export interface CacheSummaryResponse {
  categories: CacheCategorySummary[];
  total_size_bytes: number;
  total_size_human: string;
}

export interface CacheClearRequest {
  categories: string[];
}

export interface CacheClearResponse {
  cleared_categories: string[];
  cleared_keys: number;
  cleared_size_bytes: number;
  cleared_size_human: string;
  duration_ms: number;
}

// ── API Functions ──

/** 获取缓存统计摘要 */
export function getCacheSummaryApi() {
  return requestClient.get<CacheSummaryResponse>(`${API_PREFIX}/summary`);
}

/** 清理指定分类缓存 */
export function clearCacheApi(data: CacheClearRequest) {
  return requestClient.post<CacheClearResponse>(`${API_PREFIX}/clear`, data);
}
