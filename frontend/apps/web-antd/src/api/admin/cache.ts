/**
 * Cache management API / 缓存管理 API
 * Backend: /admin/cache/*
 */
import { requestClient } from '#/utils/request';

const API_PREFIX = '/admin/cache';

// ── Types / 类型定义 ──

/** Cache category summary / 缓存分类摘要 */
export interface CacheCategorySummary {
  category: string;
  label: string;
  key_count: number;
  size_bytes: number;
  size_human: string;
}

/** Cache summary response / 缓存统计响应 */
export interface CacheSummaryResponse {
  categories: CacheCategorySummary[];
  total_size_bytes: number;
  total_size_human: string;
}

/** Cache clear request / 缓存清理请求 */
export interface CacheClearRequest {
  categories: string[];
}

/** Cache clear response / 缓存清理响应 */
export interface CacheClearResponse {
  cleared_categories: string[];
  cleared_keys: number;
  cleared_size_bytes: number;
  cleared_size_human: string;
  duration_ms: number;
}

// ── API Functions / API 接口 ──

/** Get cache summary / 获取缓存统计摘要 */
export function getCacheSummaryApi() {
  return requestClient.get<CacheSummaryResponse>(`${API_PREFIX}/summary`);
}

/** Clear specified category cache / 清理指定分类缓存 */
export function clearCacheApi(data: CacheClearRequest) {
  return requestClient.post<CacheClearResponse>(`${API_PREFIX}/clear`, data);
}
