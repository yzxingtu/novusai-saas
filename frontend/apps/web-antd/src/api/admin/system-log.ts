/**
 * 系统日志 API
 * 对接后端 /admin/system-logs/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 日志统计信息（后端原始格式） */
export interface SystemLogStatsRaw {
  total_files: number;
  total_size: number;
  total_size_formatted: string;
}

/** 日志统计信息（前端格式） */
export interface SystemLogStats {
  totalFiles: number;
  totalSize: number;
  totalSizeFormatted: string;
}

/** 日志分类信息（后端原始格式） */
export interface SystemLogCategoryRaw {
  name: string;
  file_count: number;
  total_size: number;
  total_size_formatted: string;
}

/** 日志分类信息（前端格式） */
export interface SystemLogCategory {
  name: string;
  fileCount: number;
  totalSize: number;
  totalSizeFormatted: string;
}

/** 日志文件信息（后端原始格式） */
export interface SystemLogFileRaw {
  filename: string;
  category: string;
  size: number;
  size_formatted: string;
  modified_at: string;
}

/** 日志文件信息（前端格式） */
export interface SystemLogFile {
  filename: string;
  category: string;
  size: number;
  sizeFormatted: string;
  modifiedAt: string;
}

/** 日志文件内容响应（后端原始格式） */
export interface SystemLogContentRaw {
  filename: string;
  lines: string[];
  total_lines: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

/** 日志文件内容响应（前端格式） */
export interface SystemLogContent {
  filename: string;
  lines: string[];
  totalLines: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}

// ============================================================
// 转换函数
// ============================================================

function transformStats(raw: SystemLogStatsRaw): SystemLogStats {
  return {
    totalFiles: raw.total_files,
    totalSize: raw.total_size,
    totalSizeFormatted: raw.total_size_formatted,
  };
}

function transformCategory(raw: SystemLogCategoryRaw): SystemLogCategory {
  return {
    name: raw.name,
    fileCount: raw.file_count,
    totalSize: raw.total_size,
    totalSizeFormatted: raw.total_size_formatted,
  };
}

function transformFile(raw: SystemLogFileRaw): SystemLogFile {
  return {
    filename: raw.filename,
    category: raw.category,
    size: raw.size,
    sizeFormatted: raw.size_formatted,
    modifiedAt: raw.modified_at,
  };
}

function transformContent(raw: SystemLogContentRaw): SystemLogContent {
  return {
    filename: raw.filename,
    lines: raw.lines,
    totalLines: raw.total_lines,
    page: raw.page,
    pageSize: raw.page_size,
    hasMore: raw.has_more,
  };
}

// ============================================================
// API 接口
// ============================================================

const API_PREFIX = '/admin/system-logs';

/**
 * 获取系统日志统计
 * GET /admin/system-logs/stats
 */
export async function getSystemLogStatsApi(
  options?: ApiRequestOptions,
): Promise<SystemLogStats> {
  const raw = await requestClient.get<SystemLogStatsRaw>(
    `${API_PREFIX}/stats`,
    options,
  );
  return transformStats(raw);
}

/**
 * 获取日志分类列表
 * GET /admin/system-logs/categories
 */
export async function getSystemLogCategoriesApi(
  options?: ApiRequestOptions,
): Promise<SystemLogCategory[]> {
  const raw = await requestClient.get<SystemLogCategoryRaw[]>(
    `${API_PREFIX}/categories`,
    options,
  );
  return raw.map(transformCategory);
}

/**
 * 获取日志文件列表
 * GET /admin/system-logs/files
 */
export async function getSystemLogFilesApi(
  params?: { category?: string },
  options?: ApiRequestOptions,
): Promise<SystemLogFile[]> {
  const raw = await requestClient.get<SystemLogFileRaw[]>(
    `${API_PREFIX}/files`,
    { params, ...options },
  );
  return raw.map(transformFile);
}

/**
 * 获取日志文件内容
 * GET /admin/system-logs/files/{filename}/content
 */
export async function getSystemLogContentApi(
  filename: string,
  params?: { page?: number; page_size?: number; reverse?: boolean },
  options?: ApiRequestOptions,
): Promise<SystemLogContent> {
  const raw = await requestClient.get<SystemLogContentRaw>(
    `${API_PREFIX}/files/${encodeURIComponent(filename)}/content`,
    { params, ...options },
  );
  return transformContent(raw);
}

/**
 * 下载日志文件
 * GET /admin/system-logs/files/{filename}/download
 */
export function getSystemLogDownloadUrl(filename: string): string {
  return `${API_PREFIX}/files/${encodeURIComponent(filename)}/download`;
}

/**
 * 删除日志文件
 * DELETE /admin/system-logs/files/{filename}
 */
export async function deleteSystemLogFileApi(
  filename: string,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(
    `${API_PREFIX}/files/${encodeURIComponent(filename)}`,
    options,
  );
}
